"""LLM client with structured output support."""

from __future__ import annotations

import json
from typing import Type, TypeVar, Optional

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """
    Client for interacting with Ollama LLM with JSON schema enforcement.

    This is a lightweight wrapper that enforces structured output.
    """

    def __init__(self, model: str = "qwen3:8b", host: str = "http://localhost:11434"):
        """
        Initialize LLM client.

        Args:
            model: Ollama model name
            host: Ollama server URL
        """
        self.model = model
        self.host = host
        self._client = None

    def _get_client(self):
        """Lazy-load Ollama client."""
        if self._client is None:
            try:
                import ollama
                self._client = ollama.Client(host=self.host)
            except ImportError:
                raise ImportError(
                    "ollama package required. Install with: pip install ollama"
                )
        return self._client

    async def structured_query(
        self,
        prompt: str,
        response_schema: Type[T],
        system_prompt: str = "",
        temperature: float = 0.3,
        max_retries: int = 2,
    ) -> Optional[T]:
        """
        Query LLM with enforced JSON schema.

        Args:
            prompt: User prompt
            response_schema: Pydantic model for response validation
            system_prompt: System prompt for context
            temperature: Sampling temperature (0.0 = deterministic)
            max_retries: Number of retry attempts if parsing fails

        Returns:
            Validated response or None if all retries failed
        """
        client = self._get_client()

        for attempt in range(max_retries + 1):
            try:
                # Call Ollama
                response = client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    format="json",  # Request JSON format
                    options={"temperature": temperature},
                )

                # Extract response text
                response_text = response["message"]["content"]

                # Parse and validate JSON
                try:
                    response_json = json.loads(response_text)
                except json.JSONDecodeError as e:
                    if attempt < max_retries:
                        continue  # Retry
                    raise ValueError(f"Invalid JSON from LLM: {e}")

                # Validate against schema
                validated = response_schema.model_validate(response_json)
                return validated

            except ValidationError as e:
                if attempt < max_retries:
                    # Try again with more explicit prompt
                    prompt += (
                        f"\n\nPrevious attempt failed validation. "
                        f"Ensure response matches schema exactly."
                    )
                    continue
                else:
                    raise ValueError(
                        f"LLM response failed validation after {max_retries} attempts: {e}"
                    )

            except Exception as e:
                if attempt < max_retries:
                    continue
                # Return None on final failure rather than crashing
                print(f"LLM query failed: {e}")
                return None

        return None

    def check_connection(self) -> bool:
        """
        Check if Ollama server is reachable.

        Returns:
            True if connection successful
        """
        try:
            client = self._get_client()
            # Try to list models as a health check
            client.list()
            return True
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"LLMClient(model={self.model}, host={self.host})"

