import os
import time
from pathlib import Path
from typing import Any

import sherpa_onnx
from huggingface_hub import hf_hub_download

from app.audio_preprocess import preprocess_audio_bytes
from app.config import STT_MODEL_DIR, STT_NUM_THREADS, STT_REPO_ID, STT_USE_INT8
from app.vi_financial_itn import normalize_vietnamese_financial_itn


class GipformerSTTService:
    def __init__(
        self,
        repo_id: str = STT_REPO_ID,
        model_dir: str = STT_MODEL_DIR,
        use_int8: bool = STT_USE_INT8,
        num_threads: int = STT_NUM_THREADS,
    ):
        self.repo_id = repo_id
        self.model_dir = Path(model_dir)
        self.use_int8 = use_int8
        self.num_threads = num_threads
        self.recognizer: sherpa_onnx.OfflineRecognizer | None = None

    def _required_files(self) -> tuple[str, str, str, str]:
        if self.use_int8:
            return (
                "tokens.txt",
                "encoder.int8.onnx",
                "decoder.int8.onnx",
                "joiner.int8.onnx",
            )
        return ("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx")

    def download_model_if_needed(self) -> tuple[str, str, str, str]:
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        self.model_dir.mkdir(parents=True, exist_ok=True)
        files = self._required_files()
        paths = []
        for fname in files:
            local_path = self.model_dir / fname
            if not local_path.exists():
                hf_hub_download(
                    repo_id=self.repo_id,
                    filename=fname,
                    local_dir=str(self.model_dir),
                )
            paths.append(str(local_path))
        return tuple(paths)  # type: ignore[return-value]

    def load(self) -> None:
        if self.recognizer is not None:
            return
        tokens, encoder, decoder, joiner = self.download_model_if_needed()
        self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            tokens=tokens,
            encoder=encoder,
            decoder=decoder,
            joiner=joiner,
            num_threads=self.num_threads,
            sample_rate=16000,
            feature_dim=80,
            decoding_method="greedy_search",
            provider="cpu",
        )

    def transcribe_audio_bytes(self, audio_bytes: bytes) -> tuple[str, str, float, dict[str, Any]]:
        """Run audio preprocessing + Gipformer ASR + Vietnamese Financial ITN.

        Returns:
            (raw_transcript, normalized_transcript, elapsed_ms, audio_stats)
        """
        if self.recognizer is None:
            self.load()
        assert self.recognizer is not None

        t0 = time.perf_counter()
        samples, stats = preprocess_audio_bytes(audio_bytes, target_sr=16000)

        if stats.get("is_silent") or len(samples) == 0:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            return "", "", elapsed_ms, stats

        stream = self.recognizer.create_stream()
        stream.accept_waveform(16000, samples)
        self.recognizer.decode_stream(stream)
        raw_text = stream.result.text.strip()
        normalized_text = normalize_vietnamese_financial_itn(raw_text)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        return raw_text, normalized_text, elapsed_ms, stats
