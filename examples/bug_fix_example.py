"""
Example: Finding and fixing a bug using Cognitive Hydraulics.

This example demonstrates:
1. Reading a buggy file (sort.py)
2. Analyzing the code structure
3. Identifying the bug
4. Suggesting a fix
"""

import asyncio
from pathlib import Path
from cognitive_hydraulics.engine import CognitiveAgent
from cognitive_hydraulics.core.state import EditorState, Goal, FileContent
from cognitive_hydraulics.safety import SafetyConfig
from datetime import datetime


async def main():
    print("=" * 70)
    print("🐛 COGNITIVE HYDRAULICS - BUG FINDING EXAMPLE")
    print("=" * 70)
    
    # Get the example directory
    example_dir = Path(__file__).parent
    
    # Read the buggy file
    sort_file = example_dir / "sort.py"
    if not sort_file.exists():
        print(f"❌ Error: {sort_file} not found")
        return
    
    print(f"\n📄 Reading buggy file: {sort_file}")
    with open(sort_file, "r") as f:
        file_content = f.read()
    
    print(f"✓ File read ({len(file_content)} characters)")
    
    # Create agent with dry-run mode
    print("\n📦 Creating cognitive agent...")
    config = SafetyConfig(
        dry_run=True,  # Simulate without executing
        require_approval_for_destructive=False,  # Auto-approve for demo
    )
    
    agent = CognitiveAgent(
        safety_config=config,
        enable_learning=True,  # Enable learning for better suggestions
        max_cycles=50,  # Allow more cycles for complex analysis
    )
    print("✓ Agent created")
    
    # Create initial state with the buggy file
    print("\n📄 Creating initial state...")
    initial_state = EditorState(
        working_directory=str(example_dir),
        open_files={
            "sort.py": FileContent(
                path="sort.py",
                content=file_content,
                language="python",
                last_modified=datetime.now(),
            )
        },
    )
    print(f"✓ State created with buggy file")
    
    # Define goal to find and fix the bug
    print("\n🎯 Setting goal...")
    goal = Goal(
        description=(
            "Find the bug in sort.py. The function sort_numbers() is supposed to "
            "sort numbers in ascending order but produces incorrect results. "
            "Analyze the code, identify the bug, and suggest a fix."
        )
    )
    print(f"✓ Goal: Find and fix bug in sort.py")
    
    # Run agent
    print("\n🚀 Running cognitive agent to find the bug...")
    print("-" * 70)
    
    try:
        success, final_state = await agent.solve(
            goal=goal,
            initial_state=initial_state,
            verbose=True,
        )
        
        print("-" * 70)
        
        if success:
            print("\n✅ SUCCESS: Bug analysis complete!")
            
            # Show what was found
            if final_state.open_files.get("sort.py"):
                print("\n📝 Final file state:")
                print(final_state.open_files["sort.py"].content)
            
            if final_state.last_output:
                print("\n💡 Analysis output:")
                print(final_state.last_output)
        else:
            print("\n⚠️  Analysis incomplete (max cycles reached or impasse)")
        
        # Show statistics
        print(f"\n📊 Statistics:")
        print(f"   - Decision cycles: {agent.cycle_count}")
        if agent.chunk_store:
            stats = agent.chunk_store.get_stats()
            print(f"   - Chunks learned: {stats['total_chunks']}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    print("\n" + "=" * 70)
    print("✓ Example complete")
    print("=" * 70)
    print("\n💡 TIP: The bug is in the bubble sort loop - it goes out of bounds!")
    print("   The fix: Change 'range(0, n - i)' to 'range(0, n - i - 1)'")


if __name__ == "__main__":
    asyncio.run(main())

