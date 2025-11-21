"""Configuration loader utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from cognitive_hydraulics.config.settings import Config


def get_config_path(custom_path: Optional[Path] = None) -> Path:
    """
    Get the path to the configuration file.

    Args:
        custom_path: Optional custom path. If None, uses default location.

    Returns:
        Path to config.json file
    """
    if custom_path:
        return custom_path

    # Default: ~/.cognitive-hydraulics/config.json
    home = Path.home()
    config_dir = home / ".cognitive-hydraulics"
    return config_dir / "config.json"


def load_config(custom_path: Optional[Path] = None) -> Config:
    """
    Load configuration from file, or create default if it doesn't exist.

    Args:
        custom_path: Optional custom config file path

    Returns:
        Config instance (loaded from file or default)
    """
    config_path = get_config_path(custom_path)

    if config_path.exists():
        try:
            return Config.from_file(config_path)
        except (ValueError, FileNotFoundError) as e:
            # If config file is invalid, create a new default one
            print(f"Warning: Could not load config from {config_path}: {e}")
            print("Creating new default configuration...")
            config = Config.create_default()
            config.save_to_file(config_path)
            return config
    else:
        # Config doesn't exist - create default
        config = Config.create_default()
        config.save_to_file(config_path)
        return config

