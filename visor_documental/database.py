import sqlite3
from pathlib import Path

class Catalog:
    def __init__(self, path: Path):
        # El indexador trabaja en un QThread distinto al de la interfaz.
        # La conexión se comparte de forma controlada entre ambos hilos.
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY,path TEXT UNIQUE,name TEXT,ext TEXT,size INTEGER,modified REAL,code TEXT,title TEXT,kind TEXT,version TEXT,text TEXT,error TEXT,analyzed REAL); CREATE TABLE IF NOT EXISTS sections(id INTEGER PRIMARY KEY,file_id INTEGER,parent_id INTEGER,title TEXT,level INTEGER,start_page INTEGER,end_page INTEGER,content TEXT,start_y REAL,detection_type TEXT,confidence REAL); CREATE INDEX IF NOT EXISTS idx_files_search ON files(code,title,name,kind);""");
        for column,definition in (("start_y","REAL"),("detection_type","TEXT"),("confidence","REAL")):
            try: self.db.execute(f"ALTER TABLE sections ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError: pass
        self.db.commit()
    def needs_analysis(self, path):
        row = self.db.execute("SELECT size,modified FROM files WHERE path=?", (str(path),)).fetchone(); stat = path.stat()
        if not row or row["size"] != stat.st_size or row["modified"] != stat.st_mtime: return True
        if str(row["code"] or "").upper().replace("-", "").replace("_", "").startswith("F0"): return False
        return self.db.execute("SELECT 1 FROM sections WHERE file_id=? LIMIT 1", (row["id"],)).fetchone() is None
    def save_file(self, path, data, sections, error=""):
        stat = path.stat(); self.db.execute("""INSERT INTO files(path,name,ext,size,modified,code,title,kind,version,text,error,analyzed) VALUES(?,?,?,?,?,?,?,?,?,?,?,strftime('%s','now')) ON CONFLICT(path) DO UPDATE SET name=excluded.name,ext=excluded.ext,size=excluded.size,modified=excluded.modified,code=excluded.code,title=excluded.title,kind=excluded.kind,version=excluded.version,text=excluded.text,error=excluded.error,analyzed=excluded.analyzed""", (str(path),path.name,path.suffix.lower(),stat.st_size,stat.st_mtime,data.get("code",""),data.get("title",path.stem),data.get("kind","Documento"),data.get("version",""),data.get("text",""),error)); file_id=self.db.execute("SELECT id FROM files WHERE path=?",(str(path),)).fetchone()[0]; self.db.execute("DELETE FROM sections WHERE file_id=?",(file_id,)); ids={}
        for section in sections:
            cursor=self.db.execute("INSERT INTO sections(file_id,parent_id,title,level,start_page,end_page,content,start_y,detection_type,confidence) VALUES(?,?,?,?,?,?,?,?,?,?)",(file_id,ids.get(section.get("parent")),section["title"],section["level"],section.get("start_page"),section.get("end_page"),section.get("content",""),section.get("start_y"),section.get("detection_type","explicit"),section.get("confidence",0.8))); ids[section["key"]]=cursor.lastrowid
        self.db.commit()
    def search(self, query="", root=None):
        root_filter = (str(root).rstrip("\\/") + "\\%",) if root else ("%",)
        if not query:
            return self.db.execute("SELECT * FROM files WHERE path LIKE ? ORDER BY path", root_filter).fetchall()
        value=f"%{query.lower()}%"
        return self.db.execute("SELECT DISTINCT f.* FROM files f LEFT JOIN sections s ON s.file_id=f.id WHERE lower(f.path) LIKE lower(?) AND (lower(f.name) LIKE ? OR lower(f.code) LIKE ? OR lower(f.title) LIKE ? OR lower(f.kind) LIKE ? OR lower(f.text) LIKE ? OR lower(s.title) LIKE ?) ORDER BY f.path", (root_filter[0], value, value, value, value, value, value)).fetchall()

    def remove_missing(self, root):
        prefix=str(root).rstrip("\\/")+"\\%"
        rows=self.db.execute("SELECT id,path FROM files WHERE path LIKE ?",(prefix,)).fetchall()
        existing={str(path) for path in root.rglob("*") if path.is_file()}
        for row in rows:
            if row["path"] not in existing: self.db.execute("DELETE FROM sections WHERE file_id=?",(row["id"],)); self.db.execute("DELETE FROM files WHERE id=?",(row["id"],))
        self.db.commit()
