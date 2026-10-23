import html
from pathlib import Path
from PySide6.QtCore import QThread, Qt, QSettings, QDir, QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QCheckBox,QHBoxLayout,QLineEdit,QMainWindow,QPushButton,QSplitter,QStatusBar,QTextBrowser,QTreeWidget,QTreeWidgetItem,QVBoxLayout,QWidget,QFileDialog,QMessageBox,QStackedWidget,QScrollArea,QLabel,QListWidget,QListWidgetItem
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
        self.choose=QPushButton("Seleccionar carpeta"); self.choose.clicked.connect(self.choose_folder); self.index=QPushButton("Actualizar catálogo"); self.index.clicked.connect(lambda: self.start_index(True))
        bar=QHBoxLayout(); bar.addWidget(self.choose); bar.addWidget(self.index); bar.addWidget(self.search); bar.addWidget(self.quick_view)
        self.tree=QTreeWidget(); self.tree.setHeaderLabel("Biblioteca documental"); self.tree.itemClicked.connect(self.show_document); self.preview=QTextBrowser(); self.full_preview=QTextBrowser(); self.full_preview.setReadOnly(True); self.page_widget=QWidget(); self.page_layout=QVBoxLayout(self.page_widget); scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(self.page_widget); self.pdf_scroll=scroll; self.preview_stack=QStackedWidget(); self.preview_stack.addWidget(self.preview); self.preview_stack.addWidget(self.full_preview); self.preview_stack.addWidget(scroll); split=QSplitter(); split.addWidget(self.tree); split.addWidget(self.preview_stack)
        central=QWidget(); layout=QVBoxLayout(central); layout.addLayout(bar); layout.addWidget(split); self.setCentralWidget(central); self.setStatusBar(QStatusBar()); self.load_tree()
        if self.root:
            QTimer.singleShot(300, self.start_index)
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
        self.index.setEnabled(False); self.thread=QThread(self); self.worker=IndexWorker(self.root,self.catalog,force); self.worker.moveToThread(self.thread); self.thread.started.connect(self.worker.run); self.worker.progress.connect(lambda p,n:self.statusBar().showMessage(f"{p}% — {n}")); self.worker.completed.connect(self.thread.quit); self.worker.failed.connect(self.thread.quit); self.worker.completed.connect(self.worker.deleteLater); self.worker.failed.connect(self.worker.deleteLater); self.thread.finished.connect(self.finished); self.thread.finished.connect(self.thread.deleteLater); self.thread.start()
    def finished(self): self.index.setEnabled(True); self.load_tree(); self.statusBar().showMessage("Indexación completada")
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
        row=self.catalog.db.execute("SELECT * FROM files WHERE id=?",(file_id,)).fetchone(); self.current_row=row; self.current_section=section; self.refresh_preview()
        if section and str(row["ext"]).lower()==".pdf" and self.quick_view.isChecked():
            self.quick_view.setChecked(False)

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

    def render_original(self, row, body, text, section=None):
        extension=Path(row["path"]).suffix.lower()
        if extension==".pdf" and fitz:
            document=fitz.open(row["path"])
            while self.page_layout.count(): self.page_layout.takeAt(0).widget().deleteLater()
            target_text=self._normalize(section["title"]) if section else ""; target_widget=None
            for page_number,page in enumerate(document):
                pixmap=page.get_pixmap(matrix=fitz.Matrix(1.25,1.25), alpha=False)
                image=QImage(pixmap.samples,pixmap.width,pixmap.height,pixmap.stride,QImage.Format.Format_RGB888).copy()
                label=QLabel(); label.setAlignment(Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignHCenter); from PySide6.QtGui import QPixmap; label.setPixmap(QPixmap.fromImage(image)); self.page_layout.addWidget(label)
                if section and section["start_page"] and page_number+1 == section["start_page"]: target_widget=label
                elif target_text and target_text in self._normalize(page.get_text()) and target_widget is None: target_widget=label
            self.page_layout.addStretch(); self.preview_stack.setCurrentIndex(2)
            if target_widget:
                def move_to_target():
                    self.pdf_scroll.verticalScrollBar().setValue(max(0, target_widget.y()-20))
                QTimer.singleShot(250, move_to_target)
            return
        # Word y Excel se muestran con estructura legible de solo lectura.
        self.preview_stack.setCurrentIndex(1); self.full_preview.setHtml(body+"<div style='font-family:Segoe UI;font-size:11pt;white-space:pre-wrap'>"+html.escape(text)+"</div>")

    @staticmethod
    def _normalize(value):
        return "".join(character.lower() for character in str(value) if character.isalnum())
