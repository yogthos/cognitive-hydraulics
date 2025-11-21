"""Unit tests for configuration system."""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from cognitive_hydraulics.config import Config, load_config, get_config_path
from cognitive_hydraulics.config.settings import Config as ConfigModel


class TestConfigModel:
    """Tests for Config Pydantic model."""

    def test_default_config(self):
        """Test creating default config."""
        config = Config.create_default()
        assert config.llm_model == "qwen3:8b"
        assert config.llm_host == "http://localhost:11434"
        assert config.llm_temperature == 0.3
        assert config.llm_max_retries == 2
        assert config.actr_goal_value == 10.0
        assert config.actr_noise_stddev == 0.5
        assert config.cognitive_depth_threshold == 3
        assert config.cognitive_time_threshold_ms == 500.0
        assert config.cognitive_max_cycles == 100

    def test_config_validation(self):
        """Test config validation."""
        # Valid config
        config = Config(
            llm_model="test:model",
            llm_temperature=0.5,
            cognitive_max_cycles=50,
        )
        assert config.llm_model == "test:model"
        assert config.cognitive_max_cycles == 50

    def test_config_validation_fails_invalid_temperature(self):
        """Test that invalid temperature is rejected."""
        with pytest.raises(Exception):  # Pydantic validation error
            Config(llm_temperature=3.0)  # > 2.0

    def test_config_from_file(self):
        """Test loading config from file."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_data = {
                "llm_model": "custom:model",
                "llm_host": "http://custom:11434",
                "cognitive_max_cycles": 200,
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            config = Config.from_file(config_path)
            assert config.llm_model == "custom:model"
            assert config.llm_host == "http://custom:11434"
            assert config.cognitive_max_cycles == 200
            # Other values should use defaults
            assert config.llm_temperature == 0.3

    def test_config_from_file_invalid_json(self):
        """Test loading invalid JSON raises error."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            with open(config_path, "w") as f:
                f.write("invalid json {")

            with pytest.raises(ValueError, match="Invalid JSON"):
                Config.from_file(config_path)

    def test_config_save_to_file(self):
        """Test saving config to file."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config = Config(llm_model="test:model", cognitive_max_cycles=150)
            config.save_to_file(config_path)

            assert config_path.exists()
            with open(config_path, "r") as f:
                data = json.load(f)
            assert data["llm_model"] == "test:model"
            assert data["cognitive_max_cycles"] == 150


class TestConfigLoader:
    """Tests for config loader functions."""

    def test_get_config_path_default(self, monkeypatch):
        """Test getting default config path."""
        # Mock home directory
        with TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            monkeypatch.setattr(Path, "home", lambda: home)

            config_path = get_config_path()
            expected = home / ".cognitive-hydraulics" / "config.json"
            assert config_path == expected

    def test_get_config_path_custom(self):
        """Test getting custom config path."""
        custom = Path("/custom/path/config.json")
        config_path = get_config_path(custom_path=custom)
        assert config_path == custom

    def test_load_config_creates_default(self, monkeypatch, tmp_path):
        """Test that load_config creates default config if file doesn't exist."""
        # Mock home directory to use temp dir
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config_path = tmp_path / ".cognitive-hydraulics" / "config.json"
        assert not config_path.exists()

        config = load_config()
        assert config_path.exists()
        assert config.llm_model == "qwen3:8b"

        # Verify file contents
        with open(config_path, "r") as f:
            data = json.load(f)
        assert data["llm_model"] == "qwen3:8b"

    def test_load_config_loads_existing(self, monkeypatch, tmp_path):
        """Test loading existing config file."""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config_dir = tmp_path / ".cognitive-hydraulics"
        config_dir.mkdir()
        config_path = config_dir / "config.json"

        # Create custom config
        custom_config = {
            "llm_model": "custom:model",
            "cognitive_max_cycles": 250,
        }
        with open(config_path, "w") as f:
            json.dump(custom_config, f)

        config = load_config()
        assert config.llm_model == "custom:model"
        assert config.cognitive_max_cycles == 250

    def test_load_config_handles_invalid_file(self, monkeypatch, tmp_path):
        """Test that load_config handles invalid JSON gracefully."""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config_dir = tmp_path / ".cognitive-hydraulics"
        config_dir.mkdir()
        config_path = config_dir / "config.json"

        # Create invalid JSON
        with open(config_path, "w") as f:
            f.write("invalid json {")

        # Should create new default config
        config = load_config()
        assert config.llm_model == "qwen3:8b"

        # File should be overwritten with valid JSON
        with open(config_path, "r") as f:
            data = json.load(f)
        assert data["llm_model"] == "qwen3:8b"

    def test_load_config_custom_path(self, tmp_path):
        """Test loading config from custom path."""
        custom_path = tmp_path / "custom_config.json"
        custom_config = {
            "llm_model": "custom:model",
            "cognitive_max_cycles": 300,
        }
        with open(custom_path, "w") as f:
            json.dump(custom_config, f)

        config = load_config(custom_path=custom_path)
        assert config.llm_model == "custom:model"
        assert config.cognitive_max_cycles == 300

