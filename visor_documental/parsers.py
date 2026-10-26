import re
import logging
import os
if os.environ.get("VISOR_DEBUG_PDF") == "1":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
import warnings
warnings.filterwarnings("ignore", message="Cannot parse header or footer so it will be ignored", module="openpyxl")
try: import pymupdf as fitz
except ImportError:
    try: import fitz
    except ImportError: fitz = None
try: from docx import Document
except ImportError: Document = None
try: from openpyxl import load_workbook
except ImportError: load_workbook = None

HEADING=re.compile(r"^(\d+(?:\.\d+)*)(?:[.)])?\s+(.+)$")
DOCUMENT_CODE=re.compile(r"^(?:PR|FO|F0|IN|MA|RG|ACD)[-_ ]?[A-Z0-9]+[-_ ]?\d{2,}$", re.I)
logger=logging.getLogger("visor_documental.pdf")

_OP_HEADER = re.compile(r"\bresponsable\b.*\bop\b.*\bactividad\b", re.I)
_OP_NUMBER = re.compile(r"^(\d{1,3})[.)]?$")

def _operation_description(words):
    """Devuelve una etiqueta corta sin modificar el texto que se indexa."""
    value=" ".join(words).strip(" -:;,.\t")
    value=re.sub(r"\s+", " ", value)
    if len(value) > 90:
        value=value[:87].rsplit(" ",1)[0]+"..."
    return value or "Operación"

def _pdf_development_operations(document, development, next_main_page=None):
    """Extrae operaciones únicamente de la tabla Responsable/Op/Actividad."""
    start_page=development["start_page"]
    end_page=(next_main_page-1 if next_main_page else len(document))
    found=[]; seen=set(); header_columns=None
    for page_number in range(start_page, min(end_page, len(document))+1):
        page=document[page_number-1]
        words=page.get_text("words") or []
        rows={}
        for word in words:
            if len(word) < 5: continue
            x0,y0,x1,y1,text=word[:5]
            key=round(float(y0)/3)*3
            rows.setdefault(key,[]).append((float(x0),float(y0),float(x1),float(y1),str(text)))
        for row in sorted(rows.values(), key=lambda value:min(item[1] for item in value)):
            row.sort(key=lambda item:item[0]); line=" ".join(item[4] for item in row)
            if _OP_HEADER.search(line.lower()):
                # Las columnas se estiman a partir de las palabras del encabezado;
                # esto tolera tablas sin líneas visibles y cambios de escala.
                positions={item[4].lower():item[0] for item in row}
                if "op" in positions and "actividad" in positions:
                    header_columns=(positions["op"],positions["actividad"])
                continue
            if not header_columns: continue
            op_x, activity_x=header_columns
            op_words=[item for item in row if item[0] <= op_x+35 and item[2] >= op_x-8]
            match=next((_OP_NUMBER.match(item[4]) for item in op_words),None)
            if not match: continue
            number=int(match.group(1))
            if number < 1 or number > 999: continue
            activity=[item[4] for item in row if item[0] >= activity_x-12]
            if not activity: continue
            # Una fila continuada no contiene un número en la columna Op;
            # solo se acumula en la operación abierta.
            if number in seen:
                continue
            item={"operation":number,"page":page_number,"y":min(x[1] for x in op_words),"activity":_operation_description(activity)}
            found.append(item); seen.add(number)
        # No se usa texto de páginas posteriores para crear operaciones nuevas:
        # los números deben aparecer en la columna Op después de su encabezado.
    return found

def _pdf_development_operations(document, development, next_main_page=None):
    """Detector robusto en dos fases: candidatos Op y descripciones."""
    start=development["start_page"]; end=next_main_page-1 if next_main_page else len(document)
    pages=[]; headers=[]
    for page_number in range(start, min(end, len(document))+1):
        rows={}
        for word in document[page_number-1].get_text("words") or []:
            if len(word)<5: continue
            x0,y0,x1,y1,text=word[:5]; rows.setdefault(round(float(y0)/3)*3,[]).append((float(x0),float(y0),float(x1),float(y1),str(text)))
        ordered=sorted(rows.values(),key=lambda row:min(item[1] for item in row)); pages.append((page_number,ordered))
        for row in ordered:
            labels={item[4].lower().strip(".:;"):item for item in row}
            if "op" in labels and "actividad" in labels:
                op=labels["op"]; act=labels["actividad"]
                left=max((item[2] for item in row if item[0]<op[0]),default=op[0]-40)
                right=min((item[0] for item in row if item[0]>op[2]),default=act[0])
                headers.append((page_number,(left+op[0])/2,(op[2]+right)/2,act[0]))
    if not headers:
        logger.warning("No se encontró encabezado Op entre p.%s y p.%s",start,end); return []
    found=[]; seen=set(); column=None
    for page_number,rows in pages:
        prior=[header for header in headers if header[0]<=page_number]
        if prior: column=prior[-1][1:]
        if not column: continue
        left,right,activity_x=column
        for row in rows:
            row.sort(key=lambda item:item[0])
            for x0,y0,x1,y1,text in row:
                match=_OP_NUMBER.fullmatch(text.strip()); reason=None
                if not match: reason="no es entero aislado"
                elif not left <= (x0+x1)/2 <= right: reason="fuera de columna Op"
                else:
                    number=int(match.group(1))
                    if number<1 or number>999: reason="fuera de rango"
                    elif number in seen: reason="duplicado/encabezado repetido"
                logger.debug("Candidato Op p.%s x=%.1f y=%.1f texto=%r: %s",page_number,x0,y0,text,reason or "aceptado")
                if reason: continue
                activity=[item[4] for item in row if item[0]>=activity_x-8 and item[4]!=text]
                found.append({"operation":number,"page":page_number,"y":y0,"activity":_operation_description(activity)}); seen.add(number)
    missing=[n for n in range(1,max(seen or [0])+1) if n not in seen]
    if missing: logger.warning("Secuencia incompleta; faltan %s",missing)
    return found

def _pdf_development_operations(document, development, next_main_page=None):
    """Detecta tablas independientes dentro de Desarrollo por coordenadas."""
    start=development["start_page"]; end=next_main_page-1 if next_main_page else len(document)
    pages=[]
    for page_number in range(start,min(end,len(document))+1):
        rows={}
        for word in document[page_number-1].get_text("words") or []:
            if len(word)<5: continue
            x0,y0,x1,y1,text=word[:5]; rows.setdefault(round(float(y0)/3)*3,[]).append((float(x0),float(y0),float(x1),float(y1),str(text)))
        pages.append((page_number,sorted(rows.values(),key=lambda row:min(item[1] for item in row))))
    found=[]; table=None; table_no=0
    for page_number,rows in pages:
        for row in rows:
            row.sort(key=lambda item:item[0]); labels={item[4].lower().strip(".:;"):item for item in row}
            if "op" in labels and "actividad" in labels and "responsable" in labels:
                op=labels["op"]; act=labels["actividad"]
                left=max((item[2] for item in row if item[0]<op[0]),default=op[0]-40); right=min((item[0] for item in row if item[0]>op[2]),default=act[0])
                if table is None or table["closed"]:
                    table_no+=1; table={"id":table_no,"left":(left+op[0])/2,"right":(op[2]+right)/2,"activity":act[0],"closed":False,"seen":set()}
                    logger.debug("Tabla %s iniciada p.%s Op %.1f..%.1f",table_no,page_number,table["left"],table["right"])
                else: logger.debug("Encabezado repetido de tabla %s p.%s",table["id"],page_number)
                continue
            if "fin del procedimiento" in " ".join(item[4].lower() for item in row):
                if table: table["closed"]=True; logger.debug("Tabla %s cerrada p.%s",table["id"],page_number)
                continue
            if not table: continue
            for x0,y0,x1,y1,text in row:
                match=_OP_NUMBER.fullmatch(text.strip())
                if not match: continue
                if not table["left"] <= (x0+x1)/2 <= table["right"]:
                    logger.debug("Op descartada p.%s x=%.1f y=%.1f: fuera de columna",page_number,x0,y0); continue
                number=int(match.group(1))
                if number in table["seen"]:
                    logger.debug("Op descartada tabla %s p.%s: duplicada",table["id"],page_number); continue
                activity=[item[4] for item in row if item[0]>=table["activity"]-8 and item[4]!=text]
                table["seen"].add(number); found.append({"operation":number,"table":table["id"],"page":page_number,"y":y0,"activity":_operation_description(activity)})
                logger.debug("Op encontrada tabla %s: paso %s p.%s x=%.1f y=%.1f",table["id"],number,page_number,x0,y0)
    return found

def _pdf_development_operations(document, development, next_main_page=None, all_sections=None):
    """Extrae operaciones aisladas por subtítulo y por tabla."""
    start=development["start_page"]; end=next_main_page-1 if next_main_page else len(document)
    subsections=[item for item in (all_sections or []) if item.get("level",0)>1 and item.get("title","").strip().startswith("4.")]
    pages=[]
    for page_number in range(start,min(end,len(document))+1):
        rows={}
        for word in document[page_number-1].get_text("words") or []:
            if len(word)<5: continue
            x0,y0,x1,y1,text=word[:5]; rows.setdefault(round(float(y0)/3)*3,[]).append((float(x0),float(y0),float(x1),float(y1),str(text)))
        pages.append((page_number,sorted(rows.values(),key=lambda row:min(item[1] for item in row))))
    found=[]; state=None; table_id=0; active_subprocess=None
    for page_number,rows in pages:
        for row in rows:
            row.sort(key=lambda item:item[0]); labels={item[4].lower().strip(".:;"):item for item in row}
            row_y=min(item[1] for item in row)
            candidates=[s for s in subsections if s.get("start_page") and (s["start_page"]<page_number or (s["start_page"]==page_number and (s.get("start_y") is None or s["start_y"]<=row_y)))]
            subprocess=max(candidates,key=lambda s:(s["start_page"],s.get("start_y") or 0,s.get("level",0))) if candidates else None
            subprocess_key=subprocess["key"] if subprocess else None
            if subprocess_key!=active_subprocess:
                if state: logger.debug("Tabla %s cerrada por nuevo subproceso en p.%s",state["id"],page_number)
                state=None; active_subprocess=subprocess_key
            line=" ".join(item[4].lower() for item in row)
            if "fin del procedimiento" in line:
                if state: logger.debug("Tabla %s cerrada por fin en p.%s",state["id"],page_number)
                state=None; continue
            if "op" in labels and "actividad" in labels and "responsable" in labels:
                op=labels["op"]; act=labels["actividad"]
                # Los límites son los puntos medios entre encabezados contiguos.
                responsible=labels["responsable"]
                left=(responsible[2]+op[0])/2; right=(op[2]+act[0])/2
                table_id+=1 if state is None else 0
                state={"id":table_id,"left":left,"right":right,"activity_left":right,"seen":set(),"expected":1}
                logger.debug("Subproceso %s tabla %s: columna Op %.1f..%.1f",subprocess_key,table_id,left,right)
                continue
            if state is None: continue
            for x0,y0,x1,y1,text in row:
                match=_OP_NUMBER.fullmatch(text.strip())
                if not match: continue
                center=(x0+x1)/2
                if not state["left"]<=center<=state["right"]:
                    logger.debug("Descartado subproceso %s p.%s x=%.1f y=%.1f %r: fuera de Op",subprocess_key,page_number,x0,y0,text); continue
                number=int(match.group(1))
                if number>99:
                    logger.debug("Descartado subproceso %s p.%s %r: cantidad/porcentaje",subprocess_key,page_number,text); continue
                if number in state["seen"]:
                    logger.debug("Descartado subproceso %s tabla %s p.%s paso %s: duplicado",subprocess_key,state["id"],page_number,number); continue
                if number != state["expected"]:
                    logger.debug("Descartado subproceso %s tabla %s p.%s paso %s: fuera de secuencia; se esperaba %s",subprocess_key,state["id"],page_number,number,state["expected"]); continue
                activity=[item[4] for item in row if item[0]>=state["activity_left"]-4 and item[4]!=text]
                state["seen"].add(number); state["expected"]+=1
                found.append({"operation":number,"table":state["id"],"subprocess":subprocess_key,"page":page_number,"y":y0,"activity":_operation_description(activity)})
                logger.debug("Encontrado subproceso %s tabla %s: paso %s p.%s x=%.1f y=%.1f",subprocess_key,state["id"],number,page_number,x0,y0)
    for key in {item["subprocess"] for item in found}:
        sequence=sorted(item["operation"] for item in found if item["subprocess"]==key)
        missing=[n for n in range(1,max(sequence)+1) if n not in sequence] if sequence else []
        logger.debug("Secuencia subproceso %s: %s; faltantes=%s",key,sequence,missing)
    return found

def _add_development_operations(document, sections):
    for index, section in enumerate(sections):
        if section["level"] != 1 or section["title"].strip().lower() != "4 desarrollo":
            continue
        next_page=None
        for following in sections[index+1:]:
            if following["level"] == 1:
                next_page=following.get("start_page")
                break
        original_sections=list(sections)
        original_sections=list(sections)
        for operation in _pdf_development_operations(document, section, next_page, original_sections):
            candidates=[item for item in original_sections if item.get("level",0)>1 and item.get("title","").strip().startswith("4.") and item.get("start_page") and item["start_page"]<=operation["page"]]
            parent=max(candidates,key=lambda item:(item["start_page"],item["level"])) if candidates else section
            key=f"{parent['key']}-table-{operation['table']}-op-{operation['operation']}"
            sections.append({"key":key,"parent":parent["key"],"title":f"Paso {operation['operation']} – {operation['activity']}","level":parent["level"]+1,"content":"","start_page":operation["page"],"start_y":operation["y"],"detection_type":"development_operation","confidence":0.9})
        break
    return sections

def extract_pdf_sections(document):
    """Detecta únicamente encabezados de bloques, excluyendo tablas y márgenes repetidos."""
    candidates=[]; repeated={}
    for page_number,page in enumerate(document,1):
        table_rects=[]
        try:
            finder=page.find_tables()
            table_rects=[table.bbox for table in finder.tables]
        except Exception:
            pass
        page_height=page.rect.height
        for block in page.get_text("dict").get("blocks",[]):
            if block.get("type") != 0 or not block.get("lines"): continue
            x0,y0,x1,y1=block["bbox"]
            if y0 < page_height*.08 or y1 > page_height*.92: continue
            if any(not (x1 < rect[0] or x0 > rect[2] or y1 < rect[1] or y0 > rect[3]) for rect in table_rects): continue
            # Cada línea se reconstruye uniendo TODOS sus spans. No se evalúa
            # únicamente la primera línea del bloque.
            for line in block["lines"]:
                spans=line.get("spans",[]); first="".join(span.get("text","") for span in spans).strip()
                if not first: continue
                line_y=line.get("bbox",(x0,y0,x1,y1))[1]
                match=HEADING.match(first)
                if not match:
                    logger.debug("PDF p.%s rechazado: no comienza con numeración: %r", page_number, first)
                    continue
                if len(first)>140:
                    logger.debug("PDF p.%s rechazado: línea demasiado larga: %r", page_number, first)
                    continue
                number,title=match.groups(); title=title.strip().rstrip(".")
                if DOCUMENT_CODE.match(title) or DOCUMENT_CODE.match(first):
                    logger.debug("PDF p.%s rechazado: código documental: %r", page_number, first)
                    continue
                bold=any("bold" in span.get("font","").lower() for span in spans)
                size=max((float(span.get("size",0)) for span in spans),default=0)
                normalized=" ".join(first.lower().split()); repeated.setdefault(normalized,[]).append(page_number)
                candidates.append({"number":number,"title":f"{number} {title}","page":page_number,"y":line_y,"bold":bold,"size":size,"text":normalized})
    repeated_text={text for text,pages in repeated.items() if len(set(pages))>=2}
    candidates=[item for item in candidates if item["text"] not in repeated_text]
    sections=[]; stack=[]; accepted=set(); last_top=0
    for index,item in enumerate(candidates):
        number=item["number"]; level=number.count(".")+1; parts=number.split(".")
        if level==1:
            top=int(parts[0])
            if top<1 or (last_top and top>last_top+1):
                logger.debug("PDF p.%s rechazado: salto jerárquico: %s", item["page"], item["title"]); continue
            last_top=max(last_top,top)
        elif ".".join(parts[:-1]) not in accepted:
            logger.debug("PDF p.%s rechazado: padre inexistente: %s", item["page"], item["title"]); continue
        while len(stack)>=level: stack.pop()
        key=f"{number}-{index}"
        sections.append({"key":key,"parent":stack[-1] if stack else None,"title":item["title"],"level":level,"content":"","start_page":item["page"],"start_y":item["y"],"detection_type":"explicit","confidence":0.95 if item["bold"] or item["size"]>=12 else 0.8})
        logger.debug("PDF p.%s aceptado: %s (x/y aproximado: %.1f/%.1f)", item["page"], item["title"], 0, item["y"])
        stack.append(key); accepted.add(number)
    return _add_development_operations(document, sections)
def detect_sections(lines, page_numbers=None):
    sections=[]; stack=[]; normalized=[]; index=0
    lines=list(lines)
    while index < len(lines):
        current=str(lines[index]).strip()
        if re.fullmatch(r"\d+(?:\.\d+)*[.)]?", current) and index+1 < len(lines):
            normalized.append(current+" "+str(lines[index+1]).strip()); index+=2
        else:
            normalized.append(current); index+=1
    accepted=set(); last_top=0
    for index,value in enumerate(normalized):
        candidate=str(value).strip()
        # Solo se consideran títulos breves que comienzan con numeración.
        # Las líneas largas se tratan como contenido normal.
        match=HEADING.match(candidate) if len(candidate) <= 140 else None
        if not match: continue
        number,title=match.groups(); level=number.count(".")+1
        parts=number.split(".")
        if level == 1:
            top=int(parts[0])
            if top < 1 or (last_top and top > last_top+1): continue
            last_top=max(last_top,top)
        else:
            parent_number=".".join(parts[:-1])
            if parent_number not in accepted: continue
        while len(stack)>=level: stack.pop()
        key=f"{number}-{index}"; page=page_numbers[index] if page_numbers and index < len(page_numbers) else None; sections.append({"key":key,"parent":stack[-1] if stack else None,"title":f"{number} {title}","level":level,"content":"","start_page":page}); stack.append(key)
        accepted.add(number)
    return sections

def parse_document(path):
    ext=path.suffix.lower(); data={"title":path.stem,"kind":ext[1:].upper()}
    if ext==".pdf":
        if not fitz: raise RuntimeError("Instale PyMuPDF para leer PDF")
        document=fitz.open(path); data["text"]="\n".join(page.get_text() for page in document); sections=extract_pdf_sections(document)
    elif ext==".docx":
        if not Document: raise RuntimeError("Instale python-docx para leer Word")
        document=Document(path); lines=[p.text for p in document.paragraphs if p.text.strip()]; data["text"]="\n".join(lines)
        sections=[]; stack=[]
        for index, paragraph in enumerate(document.paragraphs):
            title=paragraph.text.strip(); style=paragraph.style.name.lower() if paragraph.style else ""
            if not title or not ("heading" in style or "título" in style or "titulo" in style): continue
            match=HEADING.match(title); level=(int(re.search(r"\d+",style).group()) if re.search(r"\d+",style) else 1)
            number=match.group(1) if match else ""; label=f"{number} {match.group(2) if match else title}".strip(); key=f"{number or 'heading'}-{index}"
            while len(stack)>=level: stack.pop()
            sections.append({"key":key,"parent":stack[-1] if stack else None,"title":label,"level":level,"content":""}); stack.append(key)
        if not sections:
            sections=detect_sections(lines)
    elif ext in {".xlsx",".xlsm"}:
        if not load_workbook: raise RuntimeError("Instale openpyxl para leer Excel")
        book=load_workbook(path,read_only=True,data_only=True); data["text"]="\n".join(f"{s}: "+" | ".join(str(c or "") for row in book[s].iter_rows(values_only=True) for c in row) for s in book.sheetnames); sections=[{"key":s,"parent":None,"title":s,"level":1,"content":""} for s in book.sheetnames]
    else: raise RuntimeError(f"Formato no soportado: {ext}")
    found=re.search(r"\b[A-Z]{2,5}[-_ ]?\d{2,}\b",path.stem,re.I); data["code"]=found.group(0) if found else ""
    return data, sections
