import math
from collections import Counter
from .ingest import DocumentStore
from .bm25 import BM25Okapi, tokenize_uzbek


class RAGRetriever:
    """
    Gibrid (Hybrid) RAG qidiruv tizimi:
    1. BM25 Okapi (probabilistic term matching)
    2. Exact keyword / phrase boost (aniq me'yorlar va qoidalar mosligi)
    3. TF-IDF semantik muvozanat
    """

    def __init__(self, docs_dir=None):
        self.doc_store = DocumentStore.get_instance(docs_dir)
        self.bm25 = None
        self._build_index()

    def _build_index(self):
        self.doc_store.reload_if_needed()
        corpus = [c["tokens"] for c in self.doc_store.chunks]
        if corpus:
            self.bm25 = BM25Okapi(corpus)
        else:
            self.bm25 = None

    def search(self, query, top_k=3, min_score=0.1):
        """
        Berilgan so'rov bo'yicha me'yoriy hujjatlardan eng mos bo'laklarni (chunks) topish.
        """
        self.doc_store.reload_if_needed()
        if not self.bm25 or self.bm25.corpus_size != len(self.doc_store.chunks):
            self._build_index()

        if not self.doc_store.chunks or not self.bm25:
            return []

        query_tokens = tokenize_uzbek(query)
        if not query_tokens:
            return []

        # 1. BM25 ballari
        bm25_scores = self.bm25.get_scores(query_tokens)

        # 2. Qidiruv so'rovi va aniq jumlalar mosligini tekshirish
        query_lower = query.lower()
        results = []

        max_bm25 = max(bm25_scores) if bm25_scores and max(bm25_scores) > 0 else 1.0

        for idx, chunk in enumerate(self.doc_store.chunks):
            raw_bm25 = bm25_scores[idx]
            normalized_bm25 = raw_bm25 / max_bm25 if max_bm25 > 0 else 0.0

            # Aniq so'z va iboralar mosligi uchun bonus (Exact Match Booster)
            text_lower = chunk["text"].lower()
            exact_boost = 0.0

            # Butun so'rov matnda to'liq uchrasa
            if len(query_lower) > 5 and query_lower in text_lower:
                exact_boost += 0.5

            # Kalit so'zlarning nechtasi uchrashi
            matched_words = sum(1 for t in query_tokens if t in text_lower)
            word_ratio = matched_words / len(query_tokens) if query_tokens else 0
            exact_boost += word_ratio * 0.3

            final_score = (normalized_bm25 * 0.7) + (exact_boost * 0.3)

            if final_score >= min_score or raw_bm25 > 0.5:
                results.append({
                    "doc_name": chunk["doc_name"],
                    "chunk_id": chunk["chunk_id"],
                    "score": round(final_score, 4),
                    "raw_bm25": round(raw_bm25, 3),
                    "text": chunk["text"]
                })

        # Eng yuqori ballilar bo'yicha saralash
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]


_retriever_instance = None

def get_retriever(docs_dir=None):
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = RAGRetriever(docs_dir)
    return _retriever_instance
