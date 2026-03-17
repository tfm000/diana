import os

from diana.config import (
    DianaConfig,
    DashboardConfig,
    _env_substitute,
    load_config,
    save_config,
)


class TestEnvSubstitute:
    def test_replaces_env_var(self, monkeypatch):
        monkeypatch.setenv("MY_VAR", "hello")
        assert _env_substitute("${MY_VAR}") == "hello"

    def test_leaves_unknown_var(self):
        result = _env_substitute("${UNLIKELY_VAR_XYZ_123}")
        assert result == "${UNLIKELY_VAR_XYZ_123}"

    def test_no_substitution_needed(self):
        assert _env_substitute("plain text") == "plain text"


class TestLoadConfig:
    def test_defaults_when_no_file(self, tmp_path):
        config = load_config(tmp_path / "nonexistent.yaml")
        assert config.tts.engine == "kokoro"
        assert config.tts.voice == "af_heart"
        assert config.tts.speed == 1.0
        assert config.dashboard.theme == "device"
        assert config.processing.chunk_max_chars == 4000

    def test_loads_from_yaml(self, tmp_path):
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(
            "tts:\n"
            "  engine: piper\n"
            "  voice: en_US-lessac\n"
            "dashboard:\n"
            "  max_upload_mb: 512\n"
        )
        config = load_config(yaml_file)
        assert config.tts.engine == "piper"
        assert config.tts.voice == "en_US-lessac"
        assert config.dashboard.max_upload_mb == 512
        # Unspecified values keep defaults
        assert config.tts.speed == 1.0

    def test_ignores_unknown_keys(self, tmp_path):
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(
            "tts:\n"
            "  engine: kokoro\n"
            "  unknown_key: some_value\n"
        )
        config = load_config(yaml_file)
        assert config.tts.engine == "kokoro"


class TestSaveConfig:
    def test_round_trip(self, tmp_path):
        yaml_file = tmp_path / "config.yaml"
        config = DianaConfig()
        config.tts.engine = "piper"
        config.dashboard.max_upload_mb = 2048
        config.dashboard.theme = "dark"
        save_config(config, yaml_file)

        loaded = load_config(yaml_file)
        assert loaded.tts.engine == "piper"
        assert loaded.dashboard.max_upload_mb == 2048
        assert loaded.dashboard.theme == "dark"

    def test_preserves_nested_config(self, tmp_path):
        yaml_file = tmp_path / "config.yaml"
        config = DianaConfig()
        config.tts.kokoro.model_path = "/custom/path.onnx"
        save_config(config, yaml_file)

        loaded = load_config(yaml_file)
        assert loaded.tts.kokoro.model_path == "/custom/path.onnx"
