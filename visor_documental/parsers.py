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
    return sections
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
