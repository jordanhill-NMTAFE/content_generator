"""
Integration tests using the examples structure to validate all document generators.

This test suite validates that all document generators work correctly with
the comprehensive examples provided in the examples/ directory.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
import os

from src.content_generator.assessment_tools import assess_tool
from src.content_generator.marking_guide import marking_guide_generator
from src.content_generator.lap import lap
from src.content_generator.oo_mapping_matrix import mapping_matrix


class TestExamplesIntegration:
    """Test all document generators using the examples structure."""

    @pytest.fixture
    def examples_path(self):
        """Path to the examples course structure."""
        return Path("examples/course_samples/full_course_structure")

    @pytest.fixture
    def temp_output_dir(self):
        """Create temporary output directory for test outputs."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        # Cleanup after test
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_environment(self, examples_path, temp_output_dir):
        """Mock environment variables for testing."""
        with patch.dict(
            os.environ,
            {
                "ROOT_DIR": str(Path.cwd()),
                "COURSE_CONTENT": str(examples_path),
                "OUTPUT_LOCATION": str(temp_output_dir),
            },
        ):
            yield

    def test_examples_structure_exists(self, examples_path):
        """Verify that the examples structure exists and is complete."""
        assert examples_path.exists(), f"Examples path does not exist: {examples_path}"

        # Check for key directories
        expected_dirs = [
            "2 KAD/1 LAP",
            "2 KAD/5 Assess Tool",
            "2 KAD/6 Marking Guide",
        ]

        for dir_path in expected_dirs:
            full_path = examples_path / dir_path
            assert full_path.exists(), f"Expected directory missing: {full_path}"

    def test_assessment_tool_generation_with_examples(
        self, mock_environment, examples_path, temp_output_dir
    ):
        """Test assessment tool generation using examples."""
        # Verify input file exists
        assessment_file = (
            examples_path / "2 KAD/5 Assess Tool/AT1 Example Assessment/assessment.md"
        )
        assert assessment_file.exists(), (
            f"Assessment example not found: {assessment_file}"
        )

        # Run assessment tool generator
        assess_tool(examples_path, temp_output_dir)

        # Verify output was created
        output_file = (
            temp_output_dir
            / "2 KAD/5 Assess Tool/AT1 Example Assessment/Assessment Task Tool (F122A12).docx"
        )
        assert output_file.exists(), (
            f"Assessment tool output not generated: {output_file}"
        )
        assert output_file.stat().st_size > 0, "Assessment tool output file is empty"

    def test_marking_guide_generation_with_examples(
        self, mock_environment, examples_path, temp_output_dir
    ):
        """Test marking guide generation using examples."""
        # Verify input file exists
        marking_guide_file = (
            examples_path
            / "2 KAD/6 Marking Guide/AT1 Example Assessment/marking_guide.md"
        )
        assert marking_guide_file.exists(), (
            f"Marking guide example not found: {marking_guide_file}"
        )

        # Run marking guide generator
        marking_guide_generator(examples_path, temp_output_dir)

        # Verify output was created
        output_file = (
            temp_output_dir
            / "2 KAD/6 Marking Guide/AT1 Example Assessment/Instructions to Assessors and Marking Guide (F122A13).docx"
        )
        assert output_file.exists(), (
            f"Marking guide output not generated: {output_file}"
        )
        assert output_file.stat().st_size > 0, "Marking guide output file is empty"

    def test_lap_generation_with_examples(
        self, mock_environment, examples_path, temp_output_dir
    ):
        """Test LAP generation using examples."""
        # Verify input file exists
        lap_file = examples_path / "2 KAD/1 LAP/fields.md"
        assert lap_file.exists(), f"LAP example not found: {lap_file}"

        # Run LAP generator
        lap(examples_path, temp_output_dir)

        # Verify output was created
        output_file = (
            temp_output_dir / "2 KAD/1 LAP/Learning and Assessment Plan (F122A14).docx"
        )
        assert output_file.exists(), f"LAP output not generated: {output_file}"
        assert output_file.stat().st_size > 0, "LAP output file is empty"

    def test_mapping_matrix_generation_with_examples(
        self, mock_environment, examples_path, temp_output_dir
    ):
        """Test mapping matrix generation using examples."""
        # Run mapping matrix generator
        mapping_matrix(examples_path, temp_output_dir)

        # Verify output was created
        output_file = (
            temp_output_dir
            / "2 KAD/7 Assess Mapping Matrix/Assessment Mapping Matrix (F122A8).docx"
        )
        assert output_file.exists(), (
            f"Mapping matrix output not generated: {output_file}"
        )
        assert output_file.stat().st_size > 0, "Mapping matrix output file is empty"

    def test_all_generators_integration(
        self, mock_environment, examples_path, temp_output_dir
    ):
        """Test all generators together to ensure compatibility."""
        # Run all generators in sequence
        generators = [
            ("LAP", lambda: lap(examples_path, temp_output_dir)),
            ("Assessment Tools", lambda: assess_tool(examples_path, temp_output_dir)),
            (
                "Marking Guides",
                lambda: marking_guide_generator(examples_path, temp_output_dir),
            ),
            ("Mapping Matrix", lambda: mapping_matrix(examples_path, temp_output_dir)),
        ]

        for generator_name, generator_func in generators:
            try:
                generator_func()
            except Exception as e:
                pytest.fail(f"{generator_name} generator failed: {e}")

        # Verify all expected outputs exist
        expected_outputs = [
            "2 KAD/1 LAP/Learning and Assessment Plan (F122A14).docx",
            "2 KAD/5 Assess Tool/AT1 Example Assessment/Assessment Task Tool (F122A12).docx",
            "2 KAD/6 Marking Guide/AT1 Example Assessment/Instructions to Assessors and Marking Guide (F122A13).docx",
            "2 KAD/7 Assess Mapping Matrix/Assessment Mapping Matrix (F122A8).docx",
        ]

        for output_path in expected_outputs:
            full_path = temp_output_dir / output_path
            assert full_path.exists(), f"Expected output not found: {full_path}"
            assert full_path.stat().st_size > 0, f"Output file is empty: {full_path}"

    def test_example_assessment_yaml_frontmatter(self, examples_path):
        """Test that example assessment has valid YAML frontmatter."""
        from src.utils.markdownit import parse_md

        assessment_file = (
            examples_path / "2 KAD/5 Assess Tool/AT1 Example Assessment/assessment.md"
        )
        parsed = parse_md(assessment_file)

        # Verify required frontmatter fields
        required_fields = [
            "name",
            "qualification_national_code_and_title",
            "units",
            "mapping",
        ]
        for field in required_fields:
            assert field in parsed, (
                f"Required field '{field}' missing from assessment frontmatter"
            )

        # Verify units structure
        assert isinstance(parsed["units"], list), "Units should be a list"
        assert len(parsed["units"]) > 0, "At least one unit should be specified"

        for unit in parsed["units"]:
            assert "id" in unit, "Unit should have 'id' field"
            assert "name" in unit, "Unit should have 'name' field"

        # Verify mapping structure
        assert isinstance(parsed["mapping"], list), "Mapping should be a list"
        assert len(parsed["mapping"]) > 0, "At least one mapping entry should exist"

        for mapping_entry in parsed["mapping"]:
            # Should have at least one of these competency components
            competency_components = [
                "criteria",
                "knowledge",
                "skills",
                "foundation_skills",
            ]
            has_component = any(comp in mapping_entry for comp in competency_components)
            assert has_component, (
                "Mapping entry should have at least one competency component"
            )

    def test_example_marking_guide_yaml_frontmatter(self, examples_path):
        """Test that example marking guide has valid YAML frontmatter."""
        from src.utils.markdownit import parse_md

        marking_guide_file = (
            examples_path
            / "2 KAD/6 Marking Guide/AT1 Example Assessment/marking_guide.md"
        )
        parsed = parse_md(marking_guide_file)

        # Verify required frontmatter fields
        required_fields = ["name", "qualification_national_code_and_title", "units"]
        for field in required_fields:
            assert field in parsed, (
                f"Required field '{field}' missing from marking guide frontmatter"
            )

        # Verify units structure matches assessment
        assert isinstance(parsed["units"], list), "Units should be a list"
        assert len(parsed["units"]) > 0, "At least one unit should be specified"

    def test_example_lap_fields(self, examples_path):
        """Test that example LAP fields are comprehensive."""
        from src.utils.markdownit import parse_md

        lap_file = examples_path / "2 KAD/1 LAP/fields.md"
        parsed = parse_md(lap_file)

        # Verify key LAP configuration sections exist
        expected_sections = [
            "course_name",
            "course_code",
            "institution_name",
            "units",
            "target_audience",
            "industry_focus",
            "assessment_strategy",
        ]

        for section in expected_sections:
            assert section in parsed, f"Expected LAP field '{section}' not found"

    def test_course_configuration_example(self):
        """Test that course configuration example is valid."""
        import yaml

        config_file = Path("examples/course_samples/course_config/basic_course.yaml")
        assert config_file.exists(), f"Course config example not found: {config_file}"

        with open(config_file, "r") as f:
            config = yaml.safe_load(f)

        # Verify required configuration sections
        required_sections = ["course", "institution", "students", "units"]
        for section in required_sections:
            assert section in config, f"Required config section '{section}' missing"

        # Verify course section structure
        course_config = config["course"]
        course_fields = ["type", "num_weeks", "academic_weeks", "reassessment_weeks"]
        for field in course_fields:
            assert field in course_config, f"Required course field '{field}' missing"

        # Verify units structure
        units = config["units"]
        assert isinstance(units, list), "Units should be a list"
        assert len(units) > 0, "At least one unit should be specified"

        for unit in units:
            assert "id" in unit, "Unit should have 'id' field"
            assert "name" in unit, "Unit should have 'name' field"

    def test_mapping_matrix_example(self):
        """Test that mapping matrix example is valid."""
        import yaml

        matrix_file = Path("examples/course_samples/mapping_matrix/example_matrix.yaml")
        assert matrix_file.exists(), f"Mapping matrix example not found: {matrix_file}"

        with open(matrix_file, "r") as f:
            matrix = yaml.safe_load(f)

        # Verify required sections
        required_sections = ["name", "qualification", "units", "assessments", "mapping"]
        for section in required_sections:
            assert section in matrix, f"Required matrix section '{section}' missing"

        # Verify mapping structure integrity
        mapping = matrix["mapping"]
        assert isinstance(mapping, list), "Mapping should be a list"

        for assessment_mapping in mapping:
            assert "assessment" in assessment_mapping, (
                "Assessment mapping should have 'assessment' field"
            )
            assert "questions" in assessment_mapping, (
                "Assessment mapping should have 'questions' field"
            )

            questions = assessment_mapping["questions"]
            assert isinstance(questions, list), "Questions should be a list"

            for question in questions:
                # Each question should have competency mappings
                competency_types = [
                    "criteria",
                    "knowledge",
                    "skills",
                    "foundation_skills",
                ]
                has_competency = any(
                    comp_type in question for comp_type in competency_types
                )
                assert has_competency, (
                    "Question should have at least one competency mapping"
                )


class TestExamplesValidation:
    """Additional validation tests for examples quality and consistency."""

    def test_examples_documentation_exists(self):
        """Verify that examples documentation exists and is complete."""
        readme_file = Path("examples/README.md")
        assert readme_file.exists(), "Examples README.md not found"

        with open(readme_file, "r") as f:
            content = f.read()

        # Verify key documentation sections
        required_sections = [
            "Directory Structure",
            "Document Types and Generators",
            "File Format Standards",
            "Testing Integration",
            "Quality Assurance",
        ]

        for section in required_sections:
            assert section in content, (
                f"Required documentation section '{section}' missing"
            )

    def test_examples_structure_consistency(self):
        """Test that examples follow consistent structure and naming."""
        examples_base = Path("examples/course_samples")

        # Verify course configuration examples
        config_dir = examples_base / "course_config"
        assert config_dir.exists(), "Course config examples directory missing"

        basic_config = config_dir / "basic_course.yaml"
        assert basic_config.exists(), "Basic course configuration example missing"

        # Verify full course structure
        full_structure = examples_base / "full_course_structure"
        assert full_structure.exists(), "Full course structure example missing"

        # Verify KAD structure
        kad_dir = full_structure / "2 KAD"
        assert kad_dir.exists(), "KAD directory missing from full structure"

        # Verify assessment examples
        assessment_dir = kad_dir / "5 Assess Tool" / "AT1 Example Assessment"
        assert assessment_dir.exists(), "Assessment example directory missing"
        assert (assessment_dir / "assessment.md").exists(), (
            "Assessment example file missing"
        )

        # Verify marking guide examples
        marking_dir = kad_dir / "6 Marking Guide" / "AT1 Example Assessment"
        assert marking_dir.exists(), "Marking guide example directory missing"
        assert (marking_dir / "marking_guide.md").exists(), (
            "Marking guide example file missing"
        )

    def test_examples_yaml_validity(self):
        """Test that all YAML files in examples are valid."""
        import yaml

        examples_dir = Path("examples")
        yaml_files = list(examples_dir.rglob("*.yaml")) + list(
            examples_dir.rglob("*.yml")
        )

        assert len(yaml_files) > 0, "No YAML files found in examples"

        for yaml_file in yaml_files:
            try:
                with open(yaml_file, "r") as f:
                    yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {yaml_file}: {e}")

    def test_examples_markdown_frontmatter_validity(self):
        """Test that markdown files with frontmatter are valid."""
        import yaml

        examples_dir = Path("examples")
        md_files = list(examples_dir.rglob("*.md"))

        # Filter to files that should have frontmatter
        frontmatter_files = [
            f
            for f in md_files
            if any(
                pattern in str(f)
                for pattern in ["assessment.md", "marking_guide.md", "fields.md"]
            )
        ]

        assert len(frontmatter_files) > 0, "No markdown files with frontmatter found"

        for md_file in frontmatter_files:
            try:
                with open(md_file, "r") as f:
                    content = f.read()

                if content.startswith("---"):
                    # Extract frontmatter
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = parts[1]
                        yaml.safe_load(frontmatter)
            except (yaml.YAMLError, Exception) as e:
                pytest.fail(f"Invalid frontmatter in {md_file}: {e}")


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
