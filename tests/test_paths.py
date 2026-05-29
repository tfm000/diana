import os

from diana import paths


class TestResolverIsAbsolute:
    def test_data_dir_absolute(self):
        assert os.path.isabs(str(paths.data_dir()))

    def test_config_dir_absolute(self):
        assert os.path.isabs(str(paths.config_dir()))

    def test_db_path_absolute(self):
        assert os.path.isabs(str(paths.db_path()))

    def test_upload_dir_absolute(self):
        assert os.path.isabs(str(paths.upload_dir()))

    def test_chunk_dir_absolute(self):
        assert os.path.isabs(str(paths.chunk_dir()))

    def test_output_dir_absolute(self):
        assert os.path.isabs(str(paths.output_dir()))

    def test_model_dir_absolute(self):
        assert os.path.isabs(str(paths.model_dir()))

    def test_voices_dir_absolute(self):
        assert os.path.isabs(str(paths.voices_dir()))

    def test_config_file_absolute(self):
        assert os.path.isabs(str(paths.config_file()))


class TestResolverLayout:
    def test_db_under_data_dir(self):
        assert str(paths.db_path()).startswith(str(paths.data_dir()))

    def test_upload_under_data_dir(self):
        assert str(paths.upload_dir()).startswith(str(paths.data_dir()))

    def test_chunk_under_data_dir(self):
        assert str(paths.chunk_dir()).startswith(str(paths.data_dir()))

    def test_output_under_data_dir(self):
        assert str(paths.output_dir()).startswith(str(paths.data_dir()))

    def test_model_under_data_dir(self):
        assert str(paths.model_dir()).startswith(str(paths.data_dir()))

    def test_voices_under_data_dir(self):
        assert str(paths.voices_dir()).startswith(str(paths.data_dir()))

    def test_config_file_under_config_dir(self):
        assert str(paths.config_file()).startswith(str(paths.config_dir()))

    def test_app_name_in_data_dir(self):
        assert "Diana" in str(paths.data_dir())

    def test_db_filename(self):
        assert paths.db_path().name == "diana.db"

    def test_config_filename(self):
        assert paths.config_file().name == "config.yaml"


class TestEnsureDirs:
    def test_ensure_dirs_creates_tree(self, tmp_path, monkeypatch):
        # Redirect the resolver to a hermetic tmp_path so the test never
        # touches the real per-user dir.
        monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "data")
        monkeypatch.setattr(paths, "config_dir", lambda: tmp_path / "config")
        paths.ensure_dirs()
        assert (tmp_path / "data").is_dir()
        assert (tmp_path / "data" / "uploads").is_dir()
        assert (tmp_path / "data" / "chunks").is_dir()
        assert (tmp_path / "data" / "output").is_dir()
        assert (tmp_path / "data" / "models").is_dir()
        assert (tmp_path / "data" / "voices").is_dir()
        assert (tmp_path / "config").is_dir()
