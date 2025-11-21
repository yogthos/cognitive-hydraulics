"""Unit tests for evolution-related config settings."""

import pytest
from pathlib import Path
import tempfile
import json
from cognitive_hydraulics.config.settings import Config
from cognitive_hydraulics.config.loader import load_config


class TestConfigEvolution:
    """Test evolution configuration settings."""

    def test_default_evolution_settings(self):
        """Test that default evolution settings are correct."""
        config = Config()

        assert config.evolution_enabled is True
        assert config.evolution_population_size == 3
        assert config.evolution_max_generations == 3
        assert config.cognitive_history_penalty_multiplier == 2.0

    def test_custom_evolution_settings(self):
        """Test creating config with custom evolution settings."""
        config = Config(
            evolution_enabled=False,
            evolution_population_size=5,
            evolution_max_generations=5,
            cognitive_history_penalty_multiplier=3.0,
        )

        assert config.evolution_enabled is False
        assert config.evolution_population_size == 5
        assert config.evolution_max_generations == 5
        assert config.cognitive_history_penalty_multiplier == 3.0

    def test_evolution_settings_validation(self):
        """Test that evolution settings have proper validation."""
        # Population size should be >= 2
        with pytest.raises(Exception):  # Pydantic validation error
            Config(evolution_population_size=1)

        # Population size should be <= 10
        with pytest.raises(Exception):  # Pydantic validation error
            Config(evolution_population_size=11)

        # Max generations should be >= 1
        with pytest.raises(Exception):  # Pydantic validation error
            Config(evolution_max_generations=0)

        # Max generations should be <= 10
        with pytest.raises(Exception):  # Pydantic validation error
            Config(evolution_max_generations=11)

    def test_config_save_and_load_evolution_settings(self):
        """Test that evolution settings are saved and loaded correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # Create config with custom evolution settings
            config = Config(
                evolution_enabled=False,
                evolution_population_size=4,
                evolution_max_generations=2,
                cognitive_history_penalty_multiplier=2.5,
            )

            # Save config
            config.save_to_file(config_path)

            # Load config
            loaded_config = Config.from_file(config_path)

            assert loaded_config.evolution_enabled is False
            assert loaded_config.evolution_population_size == 4
            assert loaded_config.evolution_max_generations == 2
            assert loaded_config.cognitive_history_penalty_multiplier == 2.5

    def test_load_config_with_evolution_settings(self):
        """Test loading config from JSON with evolution settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # Create JSON config
            config_data = {
                "evolution_enabled": True,
                "evolution_population_size": 5,
                "evolution_max_generations": 4,
                "cognitive_history_penalty_multiplier": 3.0,
            }

            with open(config_path, "w") as f:
                json.dump(config_data, f)

            # Load using loader
            config = load_config(config_path)

            assert config.evolution_enabled is True
            assert config.evolution_population_size == 5
            assert config.evolution_max_generations == 4
            assert config.cognitive_history_penalty_multiplier == 3.0

