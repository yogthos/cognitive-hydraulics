"""ChromaDB integration for chunk storage and retrieval."""

from __future__ import annotations

from typing import List, Optional
import json
import warnings

# Suppress ChromaDB Pydantic V1 compatibility warnings for Python 3.14+
warnings.filterwarnings("ignore", category=UserWarning, module="chromadb")

from cognitive_hydraulics.memory.chunk import Chunk, create_state_signature
from cognitive_hydraulics.core.state import EditorState


class ChunkStore:
    """
    Persistent storage for learned chunks using ChromaDB.

    Stores chunks with semantic embeddings for similarity search.
    """

    def __init__(self, collection_name: str = "cognitive_chunks", persist_directory: Optional[str] = None):
        """
        Initialize chunk store.

        Args:
            collection_name: Name of ChromaDB collection
            persist_directory: Directory for persistent storage (None = in-memory)
        """
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self._client = None
        self._collection = None

    def _get_client(self):
        """Lazy-load ChromaDB client."""
        if self._client is None:
            try:
                from chromadb import Client, Settings

                if self.persist_directory:
                    settings = Settings(
                        persist_directory=self.persist_directory,
                        anonymized_telemetry=False,
                    )
                    self._client = Client(settings)
                else:
                    # In-memory for testing
                    self._client = Client()

            except ImportError:
                raise ImportError(
                    "chromadb-client package required. Install with: pip install chromadb-client"
                )
            except Exception as e:
                # Handle Python 3.14+ compatibility issues with ChromaDB
                error_msg = (
                    f"ChromaDB is not compatible with Python 3.14+. "
                    f"Error: {type(e).__name__}: {e}\n"
                    f"Please use Python 3.10, 3.11, or 3.12 for full functionality, "
                    f"or wait for ChromaDB to update their Pydantic V1 dependencies."
                )
                raise RuntimeError(error_msg) from e
        return self._client

    def _get_collection(self):
        """Get or create collection."""
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "Learned chunks from successful resolutions"},
            )
        return self._collection

    def store_chunk(self, chunk: Chunk) -> bool:
        """
        Store a chunk in ChromaDB.

        Args:
            chunk: Chunk to store

        Returns:
            True if successfully stored
        """
        try:
            collection = self._get_collection()

            # Create embedding text (for semantic search)
            embedding_text = self._chunk_to_embedding_text(chunk)

            # Store metadata
            metadata = {
                "operator_name": chunk.operator_name,
                "goal": chunk.goal_description,
                "success_count": chunk.success_count,
                "failure_count": chunk.failure_count,
                "utility": chunk.utility or 0.0,
                "created_at": chunk.created_at.isoformat(),
                "last_used": chunk.last_used.isoformat(),
            }

            # Store in ChromaDB
            collection.add(
                ids=[chunk.id],
                documents=[embedding_text],
                metadatas=[metadata],
            )

            return True

        except Exception as e:
            print(f"Failed to store chunk: {e}")
            return False

    def retrieve_similar_chunks(
        self,
        state: EditorState,
        goal: str,
        top_k: int = 5,
        min_success_rate: float = 0.5,
    ) -> List[Chunk]:
        """
        Retrieve chunks similar to current state.

        Args:
            state: Current state
            goal: Current goal
            top_k: Number of chunks to retrieve
            min_success_rate: Minimum success rate filter

        Returns:
            List of similar chunks, sorted by relevance
        """
        try:
            collection = self._get_collection()

            # Create query text from current state
            signature = create_state_signature(state, goal)
            query_text = self._signature_to_query_text(signature)

            # Query ChromaDB
            results = collection.query(
                query_texts=[query_text],
                n_results=top_k * 2,  # Get extra for filtering
            )

            if not results["ids"] or not results["ids"][0]:
                return []

            # Reconstruct chunks and filter
            chunks = []
            for i, chunk_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i]

                # Filter by success rate
                success_count = metadata.get("success_count", 1)
                failure_count = metadata.get("failure_count", 0)
                total = success_count + failure_count
                success_rate = success_count / total if total > 0 else 0.0

                if success_rate >= min_success_rate:
                    # Reconstruct chunk (simplified - doesn't include all fields)
                    chunk = Chunk(
                        id=chunk_id,
                        state_signature=signature,  # Approximation
                        operator_name=metadata["operator_name"],
                        operator_params={},  # Would need full serialization
                        goal_description=metadata["goal"],
                        success_count=success_count,
                        failure_count=failure_count,
                        utility=metadata.get("utility"),
                    )
                    chunks.append(chunk)

            return chunks[:top_k]

        except Exception as e:
            print(f"Failed to retrieve chunks: {e}")
            return []

    def update_chunk_success(self, chunk_id: str, succeeded: bool) -> bool:
        """
        Update chunk statistics after use.

        Args:
            chunk_id: ID of chunk that was used
            succeeded: Whether the chunk succeeded

        Returns:
            True if successfully updated
        """
        try:
            collection = self._get_collection()

            # Get current metadata
            result = collection.get(ids=[chunk_id])
            if not result["ids"]:
                return False

            metadata = result["metadatas"][0]

            # Update counts
            if succeeded:
                metadata["success_count"] = metadata.get("success_count", 0) + 1
            else:
                metadata["failure_count"] = metadata.get("failure_count", 0) + 1

            metadata["last_used"] = datetime.now().isoformat()

            # Update in ChromaDB
            collection.update(
                ids=[chunk_id],
                metadatas=[metadata],
            )

            return True

        except Exception as e:
            print(f"Failed to update chunk: {e}")
            return False

    def _chunk_to_embedding_text(self, chunk: Chunk) -> str:
        """Convert chunk to text for embedding."""
        parts = [
            f"Goal: {chunk.goal_description}",
            f"Operator: {chunk.operator_name}",
        ]

        if chunk.state_signature.get("recent_error"):
            parts.append(f"Error: {chunk.state_signature['recent_error']}")

        if chunk.state_signature.get("open_files"):
            files = ", ".join(chunk.state_signature["open_files"])
            parts.append(f"Files: {files}")

        return " | ".join(parts)

    def _signature_to_query_text(self, signature: dict) -> str:
        """Convert state signature to query text."""
        parts = [f"Goal: {signature.get('goal', '')}"]

        if signature.get("recent_error"):
            parts.append(f"Error: {signature['recent_error']}")

        if signature.get("open_files"):
            files = ", ".join(signature["open_files"])
            parts.append(f"Files: {files}")

        return " | ".join(parts)

    def get_stats(self) -> dict:
        """Get storage statistics."""
        try:
            collection = self._get_collection()
            count = collection.count()

            return {
                "total_chunks": count,
                "collection_name": self.collection_name,
            }
        except Exception:
            return {"total_chunks": 0, "collection_name": self.collection_name}

    def clear(self):
        """Clear all chunks (for testing)."""
        try:
            client = self._get_client()
            client.delete_collection(name=self.collection_name)
            self._collection = None
        except Exception as e:
            print(f"Failed to clear chunks: {e}")

    def __repr__(self) -> str:
        stats = self.get_stats()
        return f"ChunkStore(collection={self.collection_name}, chunks={stats['total_chunks']})"


# Import datetime for update_chunk_success
from datetime import datetime

