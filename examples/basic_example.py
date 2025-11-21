"""
Basic example demonstrating Cognitive Hydraulics architecture.

This example shows:
1. Creating a cognitive agent
2. Defining a simple goal
3. Running the Soar decision cycle
4. Observing operator selection
"""

import asyncio
from cognitive_hydraulics.engine import CognitiveAgent
from cognitive_hydraulics.core.state import EditorState, Goal, FileContent
from cognitive_hydraulics.safety import SafetyConfig
from datetime import datetime


async def main():
    print("=" * 70)
    print("🧠 COGNITIVE HYDRAULICS - BASIC EXAMPLE")
    print("=" * 70)

    # 1. Create agent with dry-run mode (no actual file operations)
    print("\n📦 Creating cognitive agent...")
    from cognitive_hydraulics.config import load_config

    # Optionally load config (will create default if doesn't exist)
    app_config = load_config()

    safety_config = SafetyConfig(
        dry_run=True,  # Simulate without executing
        require_approval_for_destructive=False,  # Auto-approve for demo
    )

    agent = CognitiveAgent(
        safety_config=safety_config,
        enable_learning=False,  # Disable for simple demo
        max_cycles=10,  # Override config for demo
        config=app_config,  # Use loaded config
    )
    print("✓ Agent created")

    # 2. Create initial state with a file
    print("\n📄 Creating initial state...")
    initial_state = EditorState(
        working_directory="/example/project",
        open_files={
            "main.py": FileContent(
                path="main.py",
                content="def hello():\n    print('world')\n",
                language="python",
                last_modified=datetime.now(),
            )
        },
    )
    print(f"✓ State created with {len(initial_state.open_files)} file(s)")

    # 3. Define goal
    print("\n🎯 Setting goal...")
    goal = Goal(description="Understand the code structure")
    print(f"✓ Goal: {goal.description}")

    # 4. Run agent
    print("\n🚀 Running cognitive agent...")
    print("-" * 70)

    try:
        # Verbosity levels: 0=silent, 1=basic, 2=thinking (default), 3=debug
        success, final_state = await agent.solve(
            goal=goal,
            initial_state=initial_state,
            verbose=2,  # Thinking mode - shows reasoning
        )

        print("-" * 70)
        if success:
            print("\n✅ SUCCESS: Goal achieved!")
        else:
            print("\n⚠️  Goal not fully achieved (max cycles reached or impasse)")

        # Show final state
        print(f"\n📊 Final State:")
        print(f"   - Open files: {len(final_state.open_files)}")
        print(f"   - Working directory: {final_state.working_directory}")
        if final_state.last_output:
            print(f"   - Last output: {final_state.last_output[:100]}...")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise

    print("\n" + "=" * 70)
    print("✓ Example complete")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

