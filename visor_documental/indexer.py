from PySide6.QtCore import QObject, Signal
from .config import SUPPORTED_EXTENSIONS
from .parsers import parse_document

class IndexWorker(QObject):
    progress=Signal(int,str); completed=Signal(); failed=Signal(str)
    def __init__(self,root,catalog,force=False): super().__init__(); self.root=root; self.catalog=catalog; self.force=force
    def run(self):
        try:
            self.catalog.remove_missing(self.root)
            files=[p for p in self.root.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
            for n,path in enumerate(files,1):
                self.progress.emit(int(n*100/max(1,len(files))),path.name)
                if not self.force and not self.catalog.needs_analysis(path): continue
                try: data,sections=parse_document(path); self.catalog.save_file(path,data,sections)
                except Exception as error: self.catalog.save_file(path,{},[],str(error))
            self.completed.emit()
        except Exception as error: self.failed.emit(str(error))
