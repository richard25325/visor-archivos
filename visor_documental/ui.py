import html
import os
from pathlib import Path
from PySide6.QtCore import QThread, Qt, QSettings, QDir, QTimer
from PySide6.QtGui import QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import QCheckBox,QHBoxLayout,QLineEdit,QMainWindow,QPushButton,QSplitter,QStatusBar,QTextBrowser,QTreeWidget,QTreeWidgetItem,QVBoxLayout,QWidget,QFileDialog,QMessageBox,QStackedWidget,QScrollArea,QLabel,QListWidget,QListWidgetItem,QDialog,QInputDialog,QMenu
try:
    import pymupdf as fitz
except ImportError:
    try: import fitz
    except ImportError: fitz=None
from .config import database_path
from .database import Catalog
from .indexer import IndexWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Visor documental institucional"); self.resize(1200,760); self.catalog=Catalog(database_path()); self.settings=QSettings("VisorDocumental", "VisorDocumental"); saved=self.settings.value("root_folder", ""); self.root=Path(saved) if saved and Path(saved).is_dir() else None
        self.search=QLineEdit(); self.search.setPlaceholderText("Buscar documento o subíndice…"); self.search.textChanged.connect(self.load_tree)
        self.quick_view=QCheckBox("Vista rápida"); self.quick_view.setChecked(True); self.quick_view.toggled.connect(self.refresh_preview)
        self.choose=QPushButton("Seleccionar carpeta"); self.choose.clicked.connect(self.choose_folder); self.index=QPushButton("Actualizar catálogo"); self.index.clicked.connect(lambda: self.start_index(True)); self.open_original=QPushButton("Abrir documento original"); self.open_original.setEnabled(False); self.open_original.clicked.connect(self.open_original_document)
        self.add_subtitle=QPushButton("Agregar subtítulo"); self.add_subtitle.clicked.connect(self.add_subtitle_item)
        self.add_operation=QPushButton("Agregar operación"); self.add_operation.clicked.connect(self.add_operation_item)
        self.delete_index=QPushButton("Eliminar índice"); self.delete_index.clicked.connect(self.delete_index_item)
        bar=QHBoxLayout(); bar.addWidget(self.choose); bar.addWidget(self.index); bar.addWidget(self.open_original); bar.addWidget(self.add_subtitle); bar.addWidget(self.add_operation); bar.addWidget(self.delete_index); bar.addWidget(self.search); bar.addWidget(self.quick_view)
        self.tree=QTreeWidget(); self.tree.setHeaderLabel("Biblioteca documental"); self.tree.itemClicked.connect(self.show_document); self.preview=QTextBrowser(); self.full_preview=QTextBrowser(); self.full_preview.setReadOnly(True); self.page_widget=QWidget(); self.page_layout=QVBoxLayout(self.page_widget); scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(self.page_widget); self.pdf_scroll=scroll; self.preview_stack=QStackedWidget(); self.preview_stack.addWidget(self.preview); self.preview_stack.addWidget(self.full_preview); self.preview_stack.addWidget(scroll); split=QSplitter(); split.addWidget(self.tree); split.addWidget(self.preview_stack)
        self.tree.setColumnCount(1); self.tree.setHeaderLabel("Biblioteca documental"); self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.tree.customContextMenuRequested.connect(self.show_index_menu)
        central=QWidget(); layout=QVBoxLayout(central); layout.addLayout(bar); layout.addWidget(split); self.setCentralWidget(central); self.loader=QLabel("Procesando catálogo…",central); self.loader.setAlignment(Qt.AlignmentFlag.AlignCenter); self.loader.setStyleSheet("background:rgba(20,35,55,225); color:white; font-size:24px; font-weight:bold;"); self.loader.hide(); self.setStatusBar(QStatusBar()); self.load_tree()
        if self.root:
            QTimer.singleShot(300, self.start_index)
        self.search_box_shortcut=QShortcut(QKeySequence("Ctrl+F"),self)
        self.search_box_shortcut.activated.connect(self.open_global_search)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,"loader"): self.loader.setGeometry(self.centralWidget().rect())

    def choose_folder(self):
        start="F:/" if QDir("F:/").exists() else QDir.rootPath()
        dialog=QFileDialog(self,"Seleccionar carpeta raíz",start)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly,True)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog,True)
        dialog.setLabelText(QFileDialog.DialogLabel.Accept,"Usar esta carpeta")
        if dialog.exec():
            folder=dialog.selectedFiles()[0]
            self.root=Path(folder); self.settings.setValue("root_folder",str(self.root)); self.start_index(True)
    def start_index(self, force=False):
        if not self.root: return self.choose_folder()
        self.loader.setGeometry(self.centralWidget().rect()); self.loader.show(); self.loader.raise_()
        self.index.setEnabled(False); self.thread=QThread(self); self.worker=IndexWorker(self.root,self.catalog,force); self.worker.moveToThread(self.thread); self.thread.started.connect(self.worker.run); self.worker.progress.connect(lambda p,n:self.statusBar().showMessage(f"{p}% — {n}")); self.worker.completed.connect(self.thread.quit); self.worker.failed.connect(self.thread.quit); self.worker.completed.connect(self.worker.deleteLater); self.worker.failed.connect(self.worker.deleteLater); self.thread.finished.connect(self.finished); self.thread.finished.connect(self.thread.deleteLater); self.thread.start()
    def finished(self): self.index.setEnabled(True); self.load_tree(); self.loader.hide(); self.statusBar().showMessage("Indexación completada")
    def load_tree(self):
        self.tree.clear(); folders={}
        for row in self.catalog.search(self.search.text(), self.root):
            full_path=Path(row["path"])
            try:
                display_path=full_path.relative_to(self.root) if self.root else full_path
            except ValueError:
                display_path=full_path
            parent=self.tree.invisibleRootItem(); prefix=""
            for folder in display_path.parts[:-1]:
                prefix+=folder+"\\"; item=folders.setdefault(prefix,QTreeWidgetItem([folder]))
                if item.parent() is None: parent.addChild(item)
                parent=item
            doc=QTreeWidgetItem([f"{row['code']} — {row['title']}" if row['code'] else row['title']]); doc.setData(0,Qt.ItemDataRole.UserRole,row["id"]); parent.addChild(doc)
            # Los formularios F0 se muestran como documentos simples para mantener
            # el árbol ligero; los demás documentos muestran sus subíndices.
            if not str(row["code"]).upper().replace("-", "").replace("_", "").startswith("F0"):
                section_items={}
                for section in self.catalog.db.execute("SELECT * FROM sections WHERE file_id=? ORDER BY id",(row["id"],)).fetchall():
                    section_item=QTreeWidgetItem([section["title"]]); section_item.setData(0,Qt.ItemDataRole.UserRole,"section:"+str(section["id"])); section_items[section["id"]]=section_item; section_items.get(section["parent_id"],doc).addChild(section_item)
    def show_document(self,item):
        value=item.data(0,Qt.ItemDataRole.UserRole)
        if not value: return
        section=None; file_id=value
        if isinstance(value,str) and value.startswith("section:"):
            section_id=int(value.split(":",1)[1]); section=self.catalog.db.execute("SELECT * FROM sections WHERE id=?",(section_id,)).fetchone(); file_id=section["file_id"]
        row=self.catalog.db.execute("SELECT * FROM files WHERE id=?",(file_id,)).fetchone(); self.current_row=row; self.current_section=section; self.open_original.setEnabled(bool(row and Path(row["path"]).exists())); self.refresh_preview()
        if section and str(row["ext"]).lower()==".pdf" and self.quick_view.isChecked():
            self.quick_view.setChecked(False)

    def show_index_menu(self,position):
        item=self.tree.itemAt(position)
        if not item: return
        self.tree.setCurrentItem(item)
        value=item.data(0,Qt.ItemDataRole.UserRole)
        menu=QMenu(self)
        section=self._selected_section()
        if section:
            edit=menu.addAction("Editar"); edit.triggered.connect(lambda: self.edit_index(section["id"]))
            add=menu.addAction("Agregar subtítulo u operación"); add.triggered.connect(lambda: self.add_child_index(section["id"]))
            menu.addSeparator(); remove=menu.addAction("Eliminar"); remove.triggered.connect(lambda: self.remove_index(section["id"]))
        elif isinstance(value,int):
            add=menu.addAction("Agregar subtítulo"); add.triggered.connect(self.add_subtitle_item)
        if menu.actions(): menu.exec(self.tree.viewport().mapToGlobal(position))

    def _add_index_actions(self,item,section):
        panel=QWidget(); layout=QHBoxLayout(panel); layout.setContentsMargins(0,0,0,0)
        edit=QPushButton("Editar"); add=QPushButton("+"); remove=QPushButton("Eliminar")
        edit.clicked.connect(lambda: self.edit_index(section["id"]))
        add.clicked.connect(lambda: self.add_child_index(section["id"]))
        remove.clicked.connect(lambda: self.remove_index(section["id"]))
        layout.addWidget(edit); layout.addWidget(add); layout.addWidget(remove); self.tree.setItemWidget(item,1,panel)

    def edit_index(self,section_id):
        row=self.catalog.db.execute("SELECT title FROM sections WHERE id=?",(section_id,)).fetchone()
        if not row: return
        title,ok=QInputDialog.getText(self,"Editar índice","Título:",text=row["title"])
        if ok and title.strip(): self.catalog.update_section_title(section_id,title.strip()); self.load_tree()

    def add_child_index(self,parent_id):
        row=self.catalog.db.execute("SELECT * FROM sections WHERE id=?",(parent_id,)).fetchone()
        if not row: return
        title,ok=QInputDialog.getText(self,"Agregar índice","Título o Paso N:")
        if ok and title.strip(): self.catalog.add_section(row["file_id"],parent_id,title,row["level"]+1); self.load_tree()

    def remove_index(self,section_id):
        row=self.catalog.db.execute("SELECT title FROM sections WHERE id=?",(section_id,)).fetchone()
        if row and QMessageBox.question(self,"Confirmar eliminación",f"¿Eliminar '{row['title']}' y sus hijos?")==QMessageBox.StandardButton.Yes: self.catalog.delete_section(section_id); self.load_tree()

    def _selected_section(self):
        item=self.tree.currentItem(); value=item.data(0,Qt.ItemDataRole.UserRole) if item else None
        if not isinstance(value,str) or not value.startswith("section:"): return None
        return self.catalog.db.execute("SELECT * FROM sections WHERE id=?",(int(value.split(":",1)[1]),)).fetchone()

    def add_subtitle_item(self):
        parent=self._selected_section(); item=self.tree.currentItem()
        if parent: file_id,parent_id,level=parent["file_id"],parent["id"],parent["level"]+1
        elif item and isinstance(item.data(0,Qt.ItemDataRole.UserRole),int): file_id,parent_id,level=item.data(0,Qt.ItemDataRole.UserRole),None,1
        else: QMessageBox.information(self,"Agregar subtítulo","Seleccione un documento o subtítulo."); return
        title,ok=QInputDialog.getText(self,"Agregar subtítulo","Título:")
        if ok and title.strip(): self.catalog.add_section(file_id,parent_id,title.strip(),level); self.load_tree()

    def add_operation_item(self):
        parent=self._selected_section()
        if not parent: QMessageBox.information(self,"Agregar operación","Seleccione el subtítulo padre."); return
        number,ok=QInputDialog.getInt(self,"Número de operación","Paso:",1,1,999)
        if not ok: return
        description,ok=QInputDialog.getText(self,"Descripción","Descripción (opcional):")
        if not ok: return
        title=f"Paso {number}" + (f" – {description.strip()}" if description.strip() else "")
        self.catalog.add_section(parent["file_id"],parent["id"],title,parent["level"]+1,detection_type="manual_operation"); self.load_tree()

    def delete_index_item(self):
        section=self._selected_section()
        if not section: QMessageBox.information(self,"Eliminar índice","Seleccione un subtítulo u operación."); return
        if QMessageBox.question(self,"Confirmar eliminación",f"¿Eliminar '{section['title']}' y sus hijos?") != QMessageBox.StandardButton.Yes: return
        self.catalog.delete_section(section["id"]); self.load_tree()
        if self.tree.topLevelItemCount(): self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def open_global_search(self):
        dialog=QDialog(self); dialog.setWindowTitle("Buscar en documentos"); dialog.resize(620,420)
        query=QLineEdit(dialog); query.setPlaceholderText("Escriba una palabra o frase..."); results=QListWidget(dialog)
        layout=QVBoxLayout(dialog); layout.addWidget(query); layout.addWidget(results)
        def update_results(text):
            results.clear()
            for row in self.catalog.search(text,self.root):
                item=QListWidgetItem(f"{row['title']}  —  {row['path']}"); item.setData(Qt.ItemDataRole.UserRole,row["id"]); results.addItem(item)
        def open_result(item):
            row=self.catalog.db.execute("SELECT * FROM files WHERE id=?",(item.data(Qt.ItemDataRole.UserRole),)).fetchone()
            if row:
                self.current_row=row; self.current_section=None; self.open_original.setEnabled(Path(row["path"]).exists()); self.refresh_preview(); dialog.accept()
        query.textChanged.connect(update_results); results.itemClicked.connect(open_result); query.setFocus(); dialog.exec()

    def refresh_preview(self):
        row=getattr(self,"current_row",None)
        if not row: return
        section=getattr(self,"current_section",None); title=section["title"] if section else row["title"]
        body=f"<h2>{html.escape(title)}</h2><p><b>Tipo:</b> {row['kind']}<br><b>Ruta:</b> {html.escape(row['path'])}</p>"
        if row["error"]: body+=f"<p style='color:red'>{html.escape(row['error'])}</p>"
        text=row["text"] or "Sin texto extraído"
        if section:
            text=f"Apartado seleccionado: {section['title']}\n\n"+text
        if self.quick_view.isChecked():
            self.preview_stack.setCurrentIndex(0); self.preview.setHtml(body+"<pre>"+html.escape(text)+"</pre>")
        else:
            self.render_original(row, body, text, section)

    def open_original_document(self):
        row=getattr(self,"current_row",None)
        if not row or not Path(row["path"]).exists():
            QMessageBox.warning(self,"Documento no disponible","El archivo original no existe en su ubicación.")
            return
        try:
            os.startfile(row["path"])
        except OSError as error:
            QMessageBox.critical(self,"No se pudo abrir",str(error))

    def render_original(self, row, body, text, section=None):
        extension=Path(row["path"]).suffix.lower()
        if extension==".pdf" and fitz:
            document=fitz.open(row["path"])
            while self.page_layout.count(): self.page_layout.takeAt(0).widget().deleteLater()
            target_text=self._normalize(section["title"]) if section else ""; target_widget=None
            target_y=float(section["start_y"] or 0) if section and section["start_y"] is not None else 0
            for page_number,page in enumerate(document):
                pixmap=page.get_pixmap(matrix=fitz.Matrix(1.25,1.25), alpha=False)
                image=QImage(pixmap.samples,pixmap.width,pixmap.height,pixmap.stride,QImage.Format.Format_RGB888).copy()
                label=QLabel(); label.setAlignment(Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignHCenter); from PySide6.QtGui import QPixmap; label.setPixmap(QPixmap.fromImage(image)); self.page_layout.addWidget(label)
                if section and section["start_page"] and page_number+1 == section["start_page"]: target_widget=label
                elif target_text and target_text in self._normalize(page.get_text()) and target_widget is None: target_widget=label
            self.page_layout.addStretch(); self.preview_stack.setCurrentIndex(2)
            if target_widget:
                def move_to_target():
                    # start_y se obtiene del PDF en puntos; la imagen se renderiza
                    # a 1.25x, por lo que también permite ubicar una operación
                    # dentro de la página y no solo al inicio de esta.
                    self.pdf_scroll.verticalScrollBar().setValue(max(0, target_widget.y()+int(target_y*1.25)-20))
                QTimer.singleShot(250, move_to_target)
            return
        # Word y Excel se muestran con estructura legible de solo lectura.
        self.preview_stack.setCurrentIndex(1); self.full_preview.setHtml(body+"<div style='font-family:Segoe UI;font-size:11pt;white-space:pre-wrap'>"+html.escape(text)+"</div>")

    @staticmethod
    def _normalize(value):
        return "".join(character.lower() for character in str(value) if character.isalnum())
