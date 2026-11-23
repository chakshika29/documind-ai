import faiss
import numpy as np

from app.rag.embeddings import DIMENSIONS


class VectorIndex:
    def __init__(self, snapshot: bytes | None = None):
        faiss.omp_set_num_threads(2)
        self.index = (
            faiss.deserialize_index(np.frombuffer(snapshot, dtype=np.uint8))
            if snapshot is not None
            else faiss.IndexIDMap2(faiss.IndexFlatIP(DIMENSIONS))
        )

    def add(self, ids: list[int], vectors: np.ndarray) -> None:
        self.index.add_with_ids(vectors, np.asarray(ids, dtype=np.int64))

    def remove(self, ids: list[int]) -> None:
        if ids:
            self.index.remove_ids(np.asarray(ids, dtype=np.int64))

    def serialize(self) -> bytes:
        return faiss.serialize_index(self.index).tobytes()

    def search(self, query: np.ndarray, top_k: int) -> list[tuple[int, float]]:
        if not self.index.ntotal:
            return []
        scores, ids = self.index.search(query, min(top_k, self.index.ntotal))
        return [(int(chunk_id), float(score)) for chunk_id, score in zip(ids[0], scores[0])]
