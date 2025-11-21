"""Unit tests for LLM client."""

import pytest
from unittest.mock import Mock, MagicMock
from cognitive_hydraulics.llm.client import LLMClient
from cognitive_hydraulics.llm.schemas import UtilityEvaluation, UtilityEstimate


class TestLLMClient:
    """Tests for LLMClient."""

    def test_create_client(self):
        """Test creating LLM client."""
        client = LLMClient(model="llama2:7b", host="http://localhost:11434")

        assert client.model == "llama2:7b"
        assert client.host == "http://localhost:11434"

    def test_create_client_defaults(self):
        """Test creating client with defaults."""
        client = LLMClient()

        assert client.model == "qwen3:8b"
        assert "localhost" in client.host

    def test_lazy_client_initialization(self):
        """Test that Ollama client is lazily initialized."""
        client = LLMClient()

        # Client should be None until first use
        assert client._client is None

    def test_repr(self):
        """Test string representation."""
        client = LLMClient(model="test:1b", host="http://test:1234")

        repr_str = repr(client)

        assert "LLMClient" in repr_str
        assert "test:1b" in repr_str
        assert "http://test:1234" in repr_str

    @pytest.mark.asyncio
    async def test_structured_query_validates_schema(self):
        """Test that structured_query validates response against schema."""
        client = LLMClient()

        # Mock the Ollama client
        mock_ollama = Mock()
        mock_ollama.chat.return_value = {
            "message": {
                "content": """
                {
                    "evaluations": [
                        {
                            "operator_name": "test_op",
                            "probability_of_success": 0.8,
                            "estimated_cost": 3.0,
                            "reasoning": "Quick operation"
                        }
                    ],
                    "recommendation": "Use test_op"
                }
                """
            }
        }
        client._client = mock_ollama

        result = await client.structured_query(
            prompt="Test prompt",
            response_schema=UtilityEvaluation,
            system_prompt="System",
        )

        assert result is not None
        assert isinstance(result, UtilityEvaluation)
        assert len(result.evaluations) == 1
        assert result.evaluations[0].operator_name == "test_op"

    @pytest.mark.asyncio
    async def test_structured_query_retries_on_invalid_json(self):
        """Test that client retries on invalid JSON."""
        client = LLMClient()

        # Mock to return invalid JSON first, then valid
        mock_ollama = Mock()
        mock_ollama.chat.side_effect = [
            {"message": {"content": "not valid json"}},  # First attempt
            {
                "message": {
                    "content": """
                    {
                        "evaluations": [{
                            "operator_name": "test",
                            "probability_of_success": 0.5,
                            "estimated_cost": 5.0,
                            "reasoning": "Test"
                        }],
                        "recommendation": "Test"
                    }
                    """
                }
            },  # Second attempt
        ]
        client._client = mock_ollama

        result = await client.structured_query(
            prompt="Test",
            response_schema=UtilityEvaluation,
            max_retries=1,
        )

        assert result is not None
        assert mock_ollama.chat.call_count == 2  # Should retry once

    @pytest.mark.asyncio
    async def test_structured_query_returns_none_on_failure(self):
        """Test that client returns None after exhausting retries."""
        client = LLMClient()

        # Mock to always fail
        mock_ollama = Mock()
        mock_ollama.chat.return_value = {"message": {"content": "invalid json"}}
        client._client = mock_ollama

        result = await client.structured_query(
            prompt="Test",
            response_schema=UtilityEvaluation,
            max_retries=1,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_structured_query_uses_temperature(self):
        """Test that temperature is passed to Ollama."""
        client = LLMClient()

        mock_ollama = Mock()
        mock_ollama.chat.return_value = {
            "message": {
                "content": """
                {
                    "evaluations": [{
                        "operator_name": "test",
                        "probability_of_success": 0.5,
                        "estimated_cost": 5.0,
                        "reasoning": "Test"
                    }],
                    "recommendation": "Test"
                }
                """
            }
        }
        client._client = mock_ollama

        await client.structured_query(
            prompt="Test",
            response_schema=UtilityEvaluation,
            temperature=0.7,
        )

        # Check that temperature was passed
        call_kwargs = mock_ollama.chat.call_args[1]
        assert call_kwargs["options"]["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_structured_query_requests_json_format(self):
        """Test that JSON format is requested from Ollama."""
        client = LLMClient()

        mock_ollama = Mock()
        mock_ollama.chat.return_value = {
            "message": {
                "content": """
                {
                    "evaluations": [{
                        "operator_name": "test",
                        "probability_of_success": 0.5,
                        "estimated_cost": 5.0,
                        "reasoning": "Test"
                    }],
                    "recommendation": "Test"
                }
                """
            }
        }
        client._client = mock_ollama

        await client.structured_query(
            prompt="Test",
            response_schema=UtilityEvaluation,
        )

        # Check that JSON format was requested
        call_kwargs = mock_ollama.chat.call_args[1]
        assert call_kwargs["format"] == "json"

    def test_check_connection_with_mock(self):
        """Test connection check with mocked client."""
        client = LLMClient()

        # Mock successful connection
        mock_ollama = Mock()
        mock_ollama.list.return_value = []
        client._client = mock_ollama

        assert client.check_connection() is True

    def test_check_connection_failure(self):
        """Test connection check when Ollama is unavailable."""
        client = LLMClient()

        # Mock failed connection
        mock_ollama = Mock()
        mock_ollama.list.side_effect = Exception("Connection failed")
        client._client = mock_ollama

        assert client.check_connection() is False

