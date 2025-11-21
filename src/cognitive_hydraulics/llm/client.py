"""LLM client with structured output support."""

from __future__ import annotations

import json
import asyncio
from typing import Type, TypeVar, Optional, TYPE_CHECKING

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from cognitive_hydraulics.config.settings import Config

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """
    Client for interacting with Ollama LLM with JSON schema enforcement.

    This is a lightweight wrapper that enforces structured output.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        host: Optional[str] = None,
        config: Optional["Config"] = None,
    ):
        """
        Initialize LLM client.

        Args:
            model: Ollama model name (overrides config if provided)
            host: Ollama server URL (overrides config if provided)
            config: Configuration object (if None, uses defaults)
        """
        if config:
            self.model = model if model is not None else config.llm_model
            self.host = host if host is not None else config.llm_host
            self._config = config
        else:
            # Backward compatibility: use defaults if no config
            self.model = model if model is not None else "qwen3:8b"
            self.host = host if host is not None else "http://localhost:11434"
            self._config = None
        self._client = None

    def _get_client(self):
        """Lazy-load Ollama client."""
        if self._client is None:
            try:
                import ollama
                # Note: Client initialization doesn't actually connect,
                # connection happens on first API call
                self._client = ollama.Client(host=self.host)
            except ImportError:
                raise ImportError(
                    "ollama package required. Install with: pip install ollama"
                )
        return self._client
    
    async def check_connection_async(self, timeout: float = 2.0) -> bool:
        """
        Asynchronously check if Ollama server is reachable with timeout.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            client = self._get_client()
            await asyncio.wait_for(
                asyncio.to_thread(client.list),
                timeout=timeout
            )
            return True
        except (asyncio.TimeoutError, Exception):
            return False

    async def structured_query(
        self,
        prompt: str,
        response_schema: Type[T],
        system_prompt: str = "",
        temperature: Optional[float] = None,
        max_retries: Optional[int] = None,
        verbose: bool = False,
    ) -> Optional[T]:
        """
        Query LLM with enforced JSON schema.

        Args:
            prompt: User prompt
            response_schema: Pydantic model for response validation
            system_prompt: System prompt for context
            temperature: Sampling temperature (0.0 = deterministic). Uses config if None.
            max_retries: Number of retry attempts if parsing fails. Uses config if None.

        Returns:
            Validated response or None if all retries failed
        """
        # Use config values if not explicitly provided
        if temperature is None:
            temperature = self._config.llm_temperature if self._config else 0.3
        if max_retries is None:
            max_retries = self._config.llm_max_retries if self._config else 2

        # Quick connection check to avoid hanging
        is_connected = await self.check_connection_async(timeout=2.0)
        if not is_connected:
            if verbose:
                print(f"   ✗ Ollama server not reachable at {self.host}")
                print(f"   💡 Start Ollama with: ollama serve")
            return None
        
        client = self._get_client()

        for attempt in range(max_retries + 1):
            try:
                # Call Ollama (run in executor to avoid blocking, with timeout)
                # Use asyncio.to_thread if available (Python 3.9+), otherwise run_in_executor
                try:
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            client.chat,
                            model=self.model,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": prompt},
                            ],
                            format="json",  # Request JSON format
                            options={"temperature": temperature},
                        ),
                        timeout=60.0,  # 60 second timeout for LLM response
                    )
                except AttributeError:
                    # Fallback for Python < 3.9
                    loop = asyncio.get_event_loop()
                    response = await asyncio.wait_for(
                        loop.run_in_executor(
                            None,
                            lambda: client.chat(
                                model=self.model,
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": prompt},
                                ],
                                format="json",
                                options={"temperature": temperature},
                            ),
                        ),
                        timeout=60.0,
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

            except asyncio.TimeoutError:
                if attempt < max_retries:
                    if verbose:
                        print(f"   ⚠️  Attempt {attempt + 1} timed out, retrying...")
                    continue
                if verbose:
                    print(f"   ✗ LLM query timed out after {max_retries + 1} attempts")
                return None
            except Exception as e:
                if attempt < max_retries:
                    if verbose:
                        print(f"   ⚠️  Attempt {attempt + 1} failed: {e}, retrying...")
                    continue
                # Return None on final failure rather than crashing
                if verbose:
                    print(f"   ✗ LLM query failed after {max_retries + 1} attempts: {e}")
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

