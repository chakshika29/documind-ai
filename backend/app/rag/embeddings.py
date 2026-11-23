import logging
from pathlib import Path
from threading import Lock

import numpy as np

from app.core.config import Settings
from app.core.errors import KnowledgeError

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
MODEL_FILES = (
    "1_Pooling/config.json", "config.json", "config_sentence_transformers.json",
    "model.safetensors", "modules.json", "sentence_bert_config.json",
    "special_tokens_map.json", "tokenizer.json", "tokenizer_config.json", "vocab.txt",
)
DIMENSIONS = 384
logger = logging.getLogger(__name__)


def embedding_files_available(settings: Settings) -> bool:
    from huggingface_hub import try_to_load_from_cache

    cache_dir = settings.model_cache_dir or settings.storage_dir / "models"
    return all(isinstance(try_to_load_from_cache(
        MODEL_ID, filename, revision=MODEL_REVISION, cache_dir=cache_dir,
    ), str) for filename in MODEL_FILES)


def cache_model(settings: Settings) -> Path:
    from huggingface_hub import hf_hub_download

    cache_dir = settings.model_cache_dir or settings.storage_dir / "models"
    paths = {
        filename: hf_hub_download(
            MODEL_ID, filename, revision=MODEL_REVISION, cache_dir=cache_dir,
            token=False, local_files_only=settings.offline,
        )
        for filename in MODEL_FILES
    }
    return Path(paths["config.json"]).parent


class Embeddings:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None
        self._lock = Lock()

    def _load(self):
        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(min(torch.get_num_threads(), 4))
        return SentenceTransformer(
            str(cache_model(self.settings)), device="cpu", trust_remote_code=False,
            local_files_only=True, token=False, model_kwargs={"use_safetensors": True},
        )

    def encode(self, texts: list[str]) -> np.ndarray:
        with self._lock:
            if self._model is None:
                try:
                    self._model = self._load()
                except Exception as exc:
                    logger.exception("Could not load the CPU embedding model")
                    raise KnowledgeError(
                        503, "embedding_model_unavailable",
                        "MiniLM could not be loaded. Check the CPU dependencies and download the public model while online before using offline mode.",
                    ) from exc
            try:
                vectors = np.asarray(self._model.encode(
                    texts, batch_size=self.settings.embedding_batch_size,
                    normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False,
                ), dtype=np.float32)
                if vectors.shape != (len(texts), DIMENSIONS) or not np.isfinite(vectors).all():
                    raise ValueError("Invalid MiniLM embedding output")
                return vectors
            except Exception as exc:
                logger.exception("Embedding inference failed")
                raise KnowledgeError(503, "embedding_failed", "Local embedding generation failed. Retry the request.") from exc
