"""Local FLAN-T5 inference. Run this module to download the configured model."""
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from threading import Event, Lock
from time import monotonic
from typing import Callable

from huggingface_hub import snapshot_download, try_to_load_from_cache
from huggingface_hub.errors import HFValidationError

from app.core.config import Settings
from app.core.errors import KnowledgeError
from app.schemas.status import AIStatus
from app.rag.embeddings import embedding_files_available

logger = logging.getLogger(__name__)
MODEL_FILES = ("config.json", "tokenizer.json", "model.safetensors")
DOWNLOAD_FILES = (*MODEL_FILES, "tokenizer_config.json", "special_tokens_map.json", "generation_config.json")


class LocalLLM:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cache_dir = settings.model_cache_dir or settings.storage_dir / "models"
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="flan-t5")
        self._slot = Lock()
        self._state_lock = Lock()
        self._closing = Event()
        self._loading = False
        self._error: str | None = None
        self._model = None
        self._tokenizer = None

    def _cached_path(self) -> Path | None:
        local = Path(self.settings.llm_model)
        if local.is_dir():
            return local if all((local / file).is_file() for file in MODEL_FILES) else None
        try:
            paths = [
                try_to_load_from_cache(self.settings.llm_model, file, cache_dir=self.cache_dir)
                for file in MODEL_FILES
            ]
        except HFValidationError:
            return None
        if all(isinstance(path, str) for path in paths):
            return Path(paths[0]).parent
        return None

    def status(self) -> AIStatus:
        with self._state_lock:
            loading, loaded, error = self._loading, self._model is not None, self._error
        files = self._cached_path() is not None
        if loading:
            state, detail = "loading", "Loading the local model into memory."
        elif loaded:
            state, detail = "ready", "Local CPU inference is ready."
        elif error:
            state, detail = "error", error
        elif files:
            state, detail = "cached", "Model files are cached. The first question loads the model."
        else:
            state, detail = "unavailable", "Download the model with python -m app.rag.llm before asking questions."
        return AIStatus(status=state, detail=detail, model=self.settings.llm_model,
                        files_available=files, embedding_files_available=embedding_files_available(self.settings),
                        loaded=loaded, ready=state == "ready" and not self._closing.is_set(),
                        busy=self._slot.locked(), error=error)

    def download(self) -> Path:
        cached = self._cached_path()
        if cached:
            return cached
        return Path(snapshot_download(
            self.settings.llm_model, cache_dir=self.cache_dir, token=False,
            allow_patterns=DOWNLOAD_FILES, local_files_only=self.settings.offline,
            max_workers=2,
        ))

    def _load_files(self, path: Path):
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        torch.set_num_threads(min(torch.get_num_threads(), self.settings.llm_cpu_threads))
        tokenizer = AutoTokenizer.from_pretrained(
            path, local_files_only=True, trust_remote_code=False, token=False, use_fast=True,
        )
        model = AutoModelForSeq2SeqLM.from_pretrained(
            path, local_files_only=True, trust_remote_code=False, token=False,
            use_safetensors=True, dtype=torch.float32,
        ).eval()
        return tokenizer, model

    def _load(self):
        if self._model is not None:
            return self._tokenizer, self._model
        with self._state_lock:
            self._loading = True
            self._error = None
        try:
            path = self._cached_path()
            if path is None:
                raise KnowledgeError(503, "model_unavailable", "Download the local model with python -m app.rag.llm, then retry.")
            tokenizer, model = self._load_files(path)
            with self._state_lock:
                self._tokenizer, self._model = tokenizer, model
            return tokenizer, model
        except Exception as exc:
            logger.exception("Local generation model initialization failed")
            error = exc if isinstance(exc, KnowledgeError) else KnowledgeError(
                503, "model_initialization_failed", "The cached model could not load. Check the model files and backend logs.",
            )
            with self._state_lock:
                self._error = error.message
            if error is exc:
                raise
            raise error from exc
        finally:
            with self._state_lock:
                self._loading = False

    @staticmethod
    def _timeout() -> KnowledgeError:
        return KnowledgeError(504, "inference_timeout", "Local inference took too long. Retry or increase DOCUMIND_LLM_TIMEOUT_SECONDS.")

    def _run(self, prepare: Callable, cancelled: Event, deadline: float):
        tokenizer, model = self._load()
        if cancelled.is_set() or self._closing.is_set() or monotonic() >= deadline:
            raise self._timeout()
        try:
            input_limit = min(512, tokenizer.model_max_length)
            prompt, context = prepare(tokenizer, input_limit)
            if not context:
                return "", context
            import torch
            from transformers import StoppingCriteria, StoppingCriteriaList

            closing = self._closing

            class Deadline(StoppingCriteria):
                def __call__(self, _input_ids, _scores, **_kwargs):
                    return cancelled.is_set() or closing.is_set() or monotonic() >= deadline

            encoded = tokenizer(prompt, return_tensors="pt", verbose=False)
            with torch.inference_mode():
                output = model.generate(
                    **encoded, max_new_tokens=self.settings.llm_max_new_tokens,
                    do_sample=False, num_beams=1, stopping_criteria=StoppingCriteriaList([Deadline()]),
                )
            if cancelled.is_set() or self._closing.is_set() or monotonic() >= deadline:
                raise self._timeout()
            return tokenizer.decode(output[0], skip_special_tokens=True).strip(), context
        except KnowledgeError:
            raise
        except Exception as exc:
            logger.exception("Local generation failed")
            raise KnowledgeError(503, "inference_failed", "The local model failed to generate an answer. Retry the question.") from exc

    def generate(self, prepare: Callable):
        if self._closing.is_set() or not self._slot.acquire(blocking=False):
            raise KnowledgeError(503, "model_busy", "The local model is busy. Retry in a moment.")
        cancelled = Event()
        deadline = monotonic() + self.settings.llm_timeout_seconds
        try:
            future = self._executor.submit(self._run, prepare, cancelled, deadline)
        except RuntimeError as exc:
            self._slot.release()
            raise KnowledgeError(503, "model_unavailable", "The local model worker is shutting down.") from exc
        future.add_done_callback(lambda _: self._slot.release())
        try:
            return future.result(timeout=self.settings.llm_timeout_seconds)
        except TimeoutError as exc:
            cancelled.set()
            raise self._timeout() from exc

    def close(self):
        self._closing.set()
        self._executor.shutdown(wait=True, cancel_futures=True)
        with self._state_lock:
            self._model = None
            self._tokenizer = None


if __name__ == "__main__":
    service = LocalLLM(Settings())
    try:
        print(service.download())
        if not service.status().files_available:
            raise SystemExit("The configured model must provide config.json, tokenizer.json and model.safetensors.")
    finally:
        service.close()
