"""Configuration settings model."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class Config(BaseModel):
    """Configuration model for Cognitive Hydraulics."""

    # LLM settings
    llm_model: str = Field(default="qwen3:8b", description="Ollama model name")
    llm_host: str = Field(
        default="http://localhost:11434", description="Ollama server URL"
    )
    llm_temperature: float = Field(
        default=0.3, ge=0.0, le=2.0, description="LLM sampling temperature"
    )
    llm_max_retries: int = Field(
        default=2, ge=0, description="Maximum retry attempts for LLM queries"
    )
    llm_timeout: float = Field(
        default=5.0, ge=0.1, le=300.0, description="Timeout for LLM HTTP requests (seconds)"
    )

    # ACT-R settings
    actr_goal_value: float = Field(
        default=10.0, ge=0.0, description="Goal value G in utility equation"
    )
    actr_noise_stddev: float = Field(
        default=0.5, ge=0.0, description="Standard deviation for utility noise"
    )

    # Cognitive agent settings
    cognitive_depth_threshold: int = Field(
        default=3, ge=1, description="Max sub-goal depth before fallback"
    )
    cognitive_time_threshold_ms: float = Field(
        default=500.0, ge=0.0, description="Max time in state before fallback (ms)"
    )
    cognitive_max_cycles: int = Field(
        default=100, ge=1, description="Maximum decision cycles"
    )

    @classmethod
    def create_default(cls) -> Config:
        """Create a default configuration instance."""
        return cls()

    @classmethod
    def from_file(cls, path: Path) -> Config:
        """
        Load configuration from a JSON file.

        Args:
            path: Path to the config JSON file

        Returns:
            Config instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If JSON is invalid or validation fails
        """
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}") from e

        try:
            return cls.model_validate(data)
        except Exception as e:
            raise ValueError(f"Config validation failed: {e}") from e

    def save_to_file(self, path: Path) -> None:
        """
        Save configuration to a JSON file.

        Args:
            path: Path where to save the config
        """
        # Create parent directory if it doesn't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2)

    def __repr__(self) -> str:
        return f"Config(model={self.llm_model}, host={self.llm_host})"

