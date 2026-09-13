import math
import re
from collections import Counter


def tokenize_uzbek(text):
    """
    O'zbek tili uchun so'zlarni tozalash, kichik harfga o'tkazish va tokenizatsiya qilish.
    """
    if not text:
        return []
    # Kichik harfga o'tkazish
    text = text.lower()
    # O'zbek tutuq belgilari va apostroflarni standartlashtirish
    text = text.replace("‘", "'").replace("’", "'").replace("`", "'")
    # Harflar va raqamlarni ajratib olish (lotin, kirill va o'zbek harflari)
    tokens = re.findall(r"[a-z0-9а-яёўқғҳ']+", text)
    # Stop words (eng ko'p uchraydigan yuklamalar va bog'lovchilar)
    stop_words = {
        "va", "hamda", "yoki", "bilan", "uchun", "orqali", "bo'yicha", "haqida",
        "esa", "u", "bu", "shu", "o'sha", "deb", "ham", "eng", "har", "bir", "barcha",
        "lozim", "kerak", "shart", "mumkin", "etadi", "qilinadi", "bo'ladi"
    }
    return [t for t in tokens if len(t) > 1 and t not in stop_words]


class BM25Okapi:
    """
    BM25Okapi axborot qidiruv algoritmi.
    Formula:
    IDF(q) = ln((N - n(q) + 0.5) / (n(q) + 0.5) + 1)
    Score = sum( IDF(q) * (f(q, D) * (k1 + 1)) / (f(q, D) + k1 * (1 - b + b * (|D| / avgdl))) )
    """
    def __init__(self, corpus, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.avgdl = 0
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        self.nd = {}

        self._initialize(corpus)

    def _initialize(self, corpus):
        total_tokens = 0
        for document in corpus:
            self.doc_len.append(len(document))
            total_tokens += len(document)

            frequencies = Counter(document)
            self.doc_freqs.append(frequencies)

            for word in frequencies.keys():
                self.nd[word] = self.nd.get(word, 0) + 1

        self.avgdl = total_tokens / self.corpus_size if self.corpus_size > 0 else 0

        # IDF ni oldindan hisoblash
        for word, freq in self.nd.items():
            idf = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1)
            self.idf[word] = max(idf, 0.05)  # Salbiy yoki 0 qiymatlarning oldini olish

    def get_scores(self, query):
        """
        Berilgan so'rov uchun har bir hujjat bo'yicha BM25 ballarini hisoblash.
        """
        scores = [0.0] * self.corpus_size
        doc_len = self.doc_len
        avgdl = self.avgdl
        k1 = self.k1
        b = self.b

        for token in query:
            if token not in self.idf:
                continue
            token_idf = self.idf[token]

            for index, doc_freq in enumerate(self.doc_freqs):
                if token in doc_freq:
                    freq = doc_freq[token]
                    len_norm = 1.0 - b + b * (doc_len[index] / avgdl) if avgdl > 0 else 1.0
                    score = token_idf * ((freq * (k1 + 1.0)) / (freq + k1 * len_norm))
                    scores[index] += score

        return scores
