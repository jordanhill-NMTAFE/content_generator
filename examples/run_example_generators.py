#!/usr/bin/env python3
"""
Demonstration script showing how to use all document generators with the examples.

This script demonstrates:
1. Using the examples structure for testing and development
2. Running all document generators in sequence
3. Validating outputs and providing feedback
4. Best practices for content generation workflow

Usage:
    python examples/run_example_generators.py
"""

import sys
from pathlib import Path
import tempfile
import shutil
import os

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from content_generator.assessment_tools import assess_tool
from content_generator.marking_guide import marking_guide_generator
from content_generator.lap import lap
from content_generator.oo_mapping_matrix import mapping_matrix


def setup_environment(examples_path: Path, output_path: Path):
    """Set up environment variables for generators."""
    os.environ["ROOT_DIR"] = str(Path.cwd())
    os.environ["COURSE_CONTENT"] = str(examples_path)
    os.environ["OUTPUT_LOCATION"] = str(output_path)


def validate_examples_structure(examples_path: Path) -> bool:
    """Validate that examples structure is complete."""
    print("🔍 Validating examples structure...")

    required_paths = [
        "2 KAD/1 LAP/fields.md",
        "2 KAD/5 Assess Tool/AT1 Example Assessment/assessment.md",
        "2 KAD/6 Marking Guide/AT1 Example Assessment/marking_guide.md",
    ]

    missing_paths = []
    for path in required_paths:
        full_path = examples_path / path
        if not full_path.exists():
            missing_paths.append(path)

    if missing_paths:
        print(f"❌ Missing required files:")
        for path in missing_paths:
            print(f"   - {path}")
        return False

    print("✅ Examples structure validated successfully")
    return True


def run_generator(
    name: str, generator_func, examples_path: Path, output_path: Path
) -> bool:
    """Run a single generator with error handling."""
    print(f"\n🔧 Running {name} generator...")

    try:
        generator_func(examples_path, output_path)
        print(f"✅ {name} generator completed successfully")
        return True
    except Exception as e:
        print(f"❌ {name} generator failed: {e}")
        return False


def validate_outputs(output_path: Path) -> bool:
    """Validate that all expected outputs were generated."""
    print("\n🔍 Validating generated outputs...")

    expected_outputs = [
        ("LAP", "2 KAD/1 LAP/Learning and Assessment Plan (F122A14).docx"),
        (
            "Assessment Tool",
            "2 KAD/5 Assess Tool/AT1 Example Assessment/Assessment Task Tool (F122A12).docx",
        ),
        (
            "Marking Guide",
            "2 KAD/6 Marking Guide/AT1 Example Assessment/Instructions to Assessors and Marking Guide (F122A13).docx",
        ),
        (
            "Mapping Matrix",
            "2 KAD/7 Assess Mapping Matrix/Assessment Mapping Matrix (F122A8).docx",
        ),
    ]

    all_valid = True
    for name, output_file in expected_outputs:
        full_path = output_path / output_file

        if not full_path.exists():
            print(f"❌ {name}: Output file not found - {output_file}")
            all_valid = False
        elif full_path.stat().st_size == 0:
            print(f"❌ {name}: Output file is empty - {output_file}")
            all_valid = False
        else:
            size_kb = full_path.stat().st_size / 1024
            print(f"✅ {name}: Generated successfully ({size_kb:.1f} KB)")

    return all_valid


def demonstrate_examples_usage():
    """Main demonstration function."""
    print("🚀 Document Generator Examples Demonstration")
    print("=" * 50)

    # Set up paths
    examples_path = Path("examples/course_samples/full_course_structure")

    if not examples_path.exists():
        print(f"❌ Examples path not found: {examples_path}")
        print(
            "Please ensure you're running this script from the project root directory."
        )
        return False

    # Validate examples structure
    if not validate_examples_structure(examples_path):
        return False

    # Create temporary output directory
    output_path = Path(tempfile.mkdtemp(prefix="example_outputs_"))
    print(f"\n📁 Output directory: {output_path}")

    try:
        # Set up environment
        setup_environment(examples_path, output_path)

        # Run all generators
        generators = [
            ("Learning and Assessment Plan (LAP)", lap),
            ("Assessment Tools", assess_tool),
            ("Marking Guides", marking_guide_generator),
            ("Mapping Matrix", mapping_matrix),
        ]

        successful_generators = 0
        for name, generator_func in generators:
            if run_generator(name, generator_func, examples_path, output_path):
                successful_generators += 1

        # Validate outputs
        print(
            f"\n📊 Generator Results: {successful_generators}/{len(generators)} successful"
        )

        if validate_outputs(output_path):
            print("\n🎉 All document generators completed successfully!")
            print(f"\n📂 Generated documents available in: {output_path}")
            print("\nGenerated files:")
            for file_path in output_path.rglob("*.docx"):
                relative_path = file_path.relative_to(output_path)
                print(f"   - {relative_path}")

            # Option to keep outputs
            keep_outputs = (
                input("\n❓ Keep generated outputs? (y/N): ").lower().startswith("y")
            )
            if keep_outputs:
                permanent_path = Path.cwd() / "example_outputs"
                if permanent_path.exists():
                    shutil.rmtree(permanent_path)
                shutil.move(str(output_path), str(permanent_path))
                print(f"📁 Outputs saved to: {permanent_path}")
                return True

            return True
        else:
            print("\n❌ Output validation failed")
            return False

    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return False

    finally:
        # Cleanup temporary directory if it still exists
        if output_path.exists():
            try:
                shutil.rmtree(output_path)
            except:
                pass  # Ignore cleanup errors


def show_usage_examples():
    """Show examples of how to use individual generators."""
    print("\n📚 Individual Generator Usage Examples")
    print("=" * 40)

    examples = [
        (
            "Assessment Tools",
            """
from src.content_generator.assessment_tools import assess_tool
from pathlib import Path

course_path = Path("examples/course_samples/full_course_structure")
output_path = Path("output")

assess_tool(course_path, output_path)
""",
        ),
        (
            "Marking Guides",
            """
from src.content_generator.marking_guide import marking_guide_generator
from pathlib import Path

course_path = Path("examples/course_samples/full_course_structure")
output_path = Path("output")

marking_guide_generator(course_path, output_path)
""",
        ),
        (
            "LAP Generation",
            """
from src.content_generator.lap import lap
from pathlib import Path

course_path = Path("examples/course_samples/full_course_structure")
output_path = Path("output")

lap(course_path, output_path)
""",
        ),
        (
            "Mapping Matrix",
            """
from src.content_generator.oo_mapping_matrix import mapping_matrix
from pathlib import Path

course_path = Path("examples/course_samples/full_course_structure")
output_path = Path("output")

mapping_matrix(course_path, output_path)
""",
        ),
    ]

    for name, code in examples:
        print(f"\n### {name}")
        print("```python" + code + "```")


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "--examples":
        show_usage_examples()
        return

    success = demonstrate_examples_usage()

    if success:
        print("\n🎯 Next Steps:")
        print("1. Examine the generated Word documents")
        print("2. Compare with the markdown source files")
        print(
            "3. Run the test suite: `uv run python -m pytest tests/integration/test_examples_integration.py -v`"
        )
        print("4. Use `--examples` flag to see individual generator usage examples")
        sys.exit(0)
    else:
        print("\n🔄 Troubleshooting:")
        print("1. Ensure you're in the project root directory")
        print("2. Check that all example files exist in examples/course_samples/")
        print("3. Run the test suite to identify specific issues")
        sys.exit(1)


if __name__ == "__main__":
    main()
