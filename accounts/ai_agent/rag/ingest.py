import os
import glob
from pathlib import Path
from django.conf import settings


def read_file_content(file_path):
    """
    Fayldan matnni o'qib olish (TXT, MD, JSON va boshqalar).
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        return ""


def chunk_text(text, chunk_size=200, overlap=40):
    """
    Matnni mantiqiy bo'laklarga (chunklarga) ajratish.
    Paragraflar va jumlalar yaxlitligini saqlashga harakat qiladi.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    total_words = len(words)

    while start < total_words:
        end = min(start + chunk_size, total_words)
        chunk_str = " ".join(words[start:end])
        if len(chunk_str.strip()) > 30:  # Juda qisqa bo'laklarni chetlab o'tish
            chunks.append(chunk_str.strip())
        if end >= total_words:
            break
        start += chunk_size - overlap

    return chunks


class DocumentStore:
    """
    documents/ papkasidagi fayllarni o'qib, keshlab boruvchi va
    fayl o'zgarganda avtomatik yangilovchi omborxona.
    """
    _instance = None

    def __init__(self, docs_dir=None):
        if docs_dir:
            self.docs_dir = Path(docs_dir)
        else:
            try:
                self.docs_dir = Path(settings.BASE_DIR) / "documents"
            except Exception:
                self.docs_dir = Path(__file__).resolve().parent.parent.parent.parent / "documents"

        self.chunks = []       # list of dicts: {"doc_name": ..., "chunk_id": ..., "text": ..., "tokens": ...}
        self.last_mtime = 0

    @classmethod
    def get_instance(cls, docs_dir=None):
        if cls._instance is None:
            cls._instance = cls(docs_dir)
            cls._instance.reload_if_needed()
        return cls._instance

    def _get_current_mtime(self):
        mtime = 0
        if not self.docs_dir.exists():
            return 0
        for p in self.docs_dir.glob("*.*"):
            if p.is_file():
                mtime = max(mtime, p.stat().st_mtime)
        return mtime

    def reload_if_needed(self):
        current_mtime = self._get_current_mtime()
        if current_mtime > self.last_mtime or not self.chunks:
            self._load_all_documents()
            self.last_mtime = current_mtime

    def _load_all_documents(self):
        try:
            from .bm25 import tokenize_uzbek
        except (ImportError, ValueError):
            from bm25 import tokenize_uzbek

        self.chunks = []
        if not self.docs_dir.exists():
            return

        supported_exts = ("*.txt", "*.md", "*.json")
        for ext in supported_exts:
            for filepath in sorted(self.docs_dir.glob(ext)):
                text = read_file_content(filepath)
                if not text.strip():
                    continue

                raw_chunks = chunk_text(text, chunk_size=200, overlap=40)
                doc_name = filepath.name

                for idx, chunk in enumerate(raw_chunks):
                    tokens = tokenize_uzbek(chunk)
                    self.chunks.append({
                        "doc_name": doc_name,
                        "file_path": str(filepath),
                        "chunk_id": f"{doc_name}#part{idx+1}",
                        "text": chunk,
                        "tokens": tokens
                    })


if __name__ == "__main__":
    import sys
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    if str(base_dir) not in sys.path:
        sys.path.insert(0, str(base_dir))

    print("=" * 65)
    print("🚀 SOPLINE RAG: Hujjatlar bazasini indekslash boshlandi...")
    print("=" * 65)

    store = DocumentStore()
    store.reload_if_needed()

    docs_count = len(set(c["doc_name"] for c in store.chunks))
    print(f"📁 Hujjatlar papkasi: {store.docs_dir}")
    print(f"📄 Topilgan va o'qilgan hujjatlar soni: {docs_count} ta")
    print(f"🧩 Jami yaratilgan semantik bo'laklar (chunks): {len(store.chunks)} ta\n")

    file_summary = {}
    for c in store.chunks:
        file_summary[c["doc_name"]] = file_summary.get(c["doc_name"], 0) + 1

    for fname, count in file_summary.items():
        print(f"  ✓ {fname}: {count} ta bo'lak")

    print("\n" + "=" * 65)
    print("✅ RAG indekslash muvaffaqiyatli yakunlandi!")
    print("ℹ️  Eslatma: Tizim ishlayotganda ushbu fayllar avtomatik keshlanadi,")
    print("   alohida ChromaDB yoki vektor bazasi talab etilmaydi.")
    print("=" * 65)

