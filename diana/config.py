import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


def _env_substitute(value: str) -> str:
    """Replace ${VAR} patterns with environment variable values."""
    def replacer(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))
    return re.sub(r"\$\{(\w+)\}", replacer, value)


def _substitute_recursive(obj):
    """Walk a nested dict/list and apply env substitution to strings."""
    if isinstance(obj, str):
        return _env_substitute(obj)
    if isinstance(obj, dict):
        return {k: _substitute_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute_recursive(v) for v in obj]
    return obj


@dataclass
class KokoroConfig:
    model_path: str = "data/models/kokoro-v1.0.onnx"
    voices_path: str = "data/models/voices-v1.0.bin"


@dataclass
class PiperConfig:
    model_path: str = "data/models/en_US-lessac-medium.onnx"


@dataclass
class TTSConfig:
    engine: str = "kokoro"
    voice: str = "af_heart"
    speed: float = 1.0
    language: str = "en-us"
    kokoro: KokoroConfig = field(default_factory=KokoroConfig)
    piper: PiperConfig = field(default_factory=PiperConfig)


@dataclass
class ProcessingConfig:
    chunk_max_chars: int = 4000
    max_concurrent_chunks: int = 2
    output_bitrate: str = "192k"
    gap_ms: int = 500


@dataclass
class StorageConfig:
    upload_dir: str = "data/uploads"
    chunk_dir: str = "data/chunks"
    output_dir: str = "data/output"
    model_dir: str = "data/models"
    database_path: str = "data/diana.db"


@dataclass
class DashboardConfig:
    page_title: str = "Diana"
    max_upload_mb: int = 200


@dataclass
class DianaConfig:
    tts: TTSConfig = field(default_factory=TTSConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)


def _build_dataclass(cls, data: dict):
    """Recursively build a dataclass from a dict, ignoring unknown keys."""
    if data is None:
        return cls()
    field_names = {f.name for f in cls.__dataclass_fields__.values()}
    filtered = {}
    for k, v in data.items():
        if k not in field_names:
            continue
        f = cls.__dataclass_fields__[k]
        if hasattr(f.type, "__dataclass_fields__") if isinstance(f.type, type) else False:
            filtered[k] = _build_dataclass(f.type, v if isinstance(v, dict) else {})
        else:
            filtered[k] = v
    return cls(**filtered)


def load_config(path: str | Path = "config.yaml") -> DianaConfig:
    """Load configuration from a YAML file, falling back to defaults."""
    path = Path(path)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        raw = _substitute_recursive(raw)
    else:
        raw = {}

    return DianaConfig(
        tts=_build_dataclass(TTSConfig, raw.get("tts", {})),
        processing=_build_dataclass(ProcessingConfig, raw.get("processing", {})),
        storage=_build_dataclass(StorageConfig, raw.get("storage", {})),
        dashboard=_build_dataclass(DashboardConfig, raw.get("dashboard", {})),
    )


_config: DianaConfig | None = None


def get_config(path: str | Path = "config.yaml") -> DianaConfig:
    """Get the singleton config instance."""
    global _config
    if _config is None:
        _config = load_config(path)
    return _config


def save_config(config: DianaConfig, path: str | Path = "config.yaml") -> None:
    """Save the current config back to YAML."""
    data = {
        "tts": {
            "engine": config.tts.engine,
            "voice": config.tts.voice,
            "speed": config.tts.speed,
            "language": config.tts.language,
            "kokoro": {
                "model_path": config.tts.kokoro.model_path,
                "voices_path": config.tts.kokoro.voices_path,
            },
            "piper": {
                "model_path": config.tts.piper.model_path,
            },
        },
        "processing": {
            "chunk_max_chars": config.processing.chunk_max_chars,
            "max_concurrent_chunks": config.processing.max_concurrent_chunks,
            "output_bitrate": config.processing.output_bitrate,
            "gap_ms": config.processing.gap_ms,
        },
        "storage": {
            "upload_dir": config.storage.upload_dir,
            "chunk_dir": config.storage.chunk_dir,
            "output_dir": config.storage.output_dir,
            "model_dir": config.storage.model_dir,
            "database_path": config.storage.database_path,
        },
        "dashboard": {
            "page_title": config.dashboard.page_title,
            "max_upload_mb": config.dashboard.max_upload_mb,
        },
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
