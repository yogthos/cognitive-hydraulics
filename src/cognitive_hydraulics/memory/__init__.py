"""Memory subsystem for learning and persistence."""

from cognitive_hydraulics.memory.unified_memory import UnifiedMemory
from cognitive_hydraulics.memory.chunk import Chunk, create_chunk_from_success
from cognitive_hydraulics.memory.context_node import ContextNode

# Backward compatibility: ChunkStore is now UnifiedMemory
ChunkStore = UnifiedMemory

__all__ = [
    "UnifiedMemory",
    "ChunkStore",  # Backward compatibility alias
    "Chunk",
    "create_chunk_from_success",
    "ContextNode",
]
