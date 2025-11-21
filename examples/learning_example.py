"""
Learning example demonstrating chunking system.

This example shows:
1. Agent encounters a problem
2. ACT-R resolves it (slow, uses LLM)
3. Chunk is created
4. Second encounter uses chunk (fast, no LLM)
"""

import asyncio
import tempfile
import shutil
from pathlib import Path
from cognitive_hydraulics.engine import CognitiveAgent
from cognitive_hydraulics.core.state import EditorState, Goal
from cognitive_hydraulics.safety import SafetyConfig


async def main():
    print("=" * 70)
    print("🧠 COGNITIVE HYDRAULICS - LEARNING EXAMPLE")
    print("=" * 70)

    # Create temporary directory for chunk storage
    temp_dir = tempfile.mkdtemp()
    print(f"\n💾 Chunk storage: {temp_dir}")

    try:
        # 1. Create agent with learning enabled
        print("\n📦 Creating cognitive agent with learning...")
        config = SafetyConfig(
            dry_run=True,
            require_approval_for_destructive=False,
        )

        agent = CognitiveAgent(
            safety_config=config,
            enable_learning=True,  # ← Enable learning
            chunk_store_path=temp_dir,
            max_cycles=5,
        )
        print("✓ Agent created with learning enabled")

        # 2. First attempt - will be slow (learning)
        print("\n" + "=" * 70)
        print("📝 FIRST ATTEMPT (Learning)")
        print("=" * 70)

        initial_state = EditorState(
            working_directory="/project",
            error_log=["NameError: name 'x' is not defined"],
        )
        goal = Goal(description="Fix the NameError")

        print("\n🚀 Running agent (this will use ACT-R if it hits an impasse)...")
        success1, _ = await agent.solve(goal, initial_state, verbose=True)

        # Check if chunk was created
        stats = agent.chunk_store.get_stats()
        print(f"\n📊 Chunks after first attempt: {stats['total_chunks']}")

        # 3. Second attempt - should be faster (using chunk)
        print("\n" + "=" * 70)
        print("💡 SECOND ATTEMPT (Using Memory)")
        print("=" * 70)

        # Similar state
        initial_state2 = EditorState(
            working_directory="/project",
            error_log=["NameError: name 'y' is not defined"],
        )
        goal2 = Goal(description="Fix the NameError")

        print("\n🚀 Running agent (should find similar chunk)...")
        success2, _ = await agent.solve(goal2, initial_state2, verbose=True)

        # Final stats
        stats = agent.chunk_store.get_stats()
        print(f"\n📊 Final chunk statistics:")
        print(f"   - Total chunks: {stats['total_chunks']}")
        print(f"   - Collection: {stats['collection_name']}")

        print("\n✅ Learning example complete!")
        print("\n💡 Key Insight:")
        print("   - First attempt: Slow (ACT-R + LLM)")
        print("   - Second attempt: Fast (Memory retrieval)")
        print("   - This is how the agent learns from experience!")

    finally:
        # Cleanup
        shutil.rmtree(temp_dir)
        print(f"\n🧹 Cleaned up temporary directory")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

