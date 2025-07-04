"""
Test suite for validating push function and document generation.
Uses AISS-ICTSS00120 config to test against real-world example course structure.
"""

import os
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import yaml
import json

from src.main import init_course, push
from src.gptgen.content_generator import create_gpt_generator
from src.gptgen.config import CourseConfig


class TestPushValidation:
    """Test suite for validating push function against real-world course structure."""

    @pytest.fixture
    def temp_test_dir(self):
        """Create a temporary directory for test outputs."""
        temp_dir = tempfile.mkdtemp(prefix="push_validation_test_")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def aiss_config(self):
        """Load the AISS-ICTSS00120 configuration."""
        config_path = Path("aiss_ictss00120_config.yaml")
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    @pytest.fixture
    def example_course_path(self):
        """Path to the example AISS-ICTSS00120 course."""
        return Path("example/AISS-ICTSS00120")

    def test_init_course_structure_validation(self, temp_test_dir, aiss_config):
        """Test that init creates the expected directory structure."""
        # Mock GPT client to avoid API calls
        with patch("gpt.models.openai_.Chat") as mock_client:
            mock_client.return_value = MagicMock()

            # Run init with the AISS config
            init_course(
                course_name=aiss_config["course_name"],
                target_path=Path(temp_test_dir),
                course_type=aiss_config["course_type"],
                num_weeks=aiss_config["weeks"],
                delivery_mode=aiss_config["delivery_mode"],
                institution_name=aiss_config["institution"],
                student_cohort=aiss_config["student_cohort"],
                mission_prompt=aiss_config["mission"],
                uoc_codes=[u["id"] for u in aiss_config["units"]],
            )

            # Validate directory structure
            course_dir = Path(temp_test_dir) / aiss_config["course_name"]
            assert course_dir.exists(), "Course directory should be created"

            # Check for required directories
            required_dirs = ["1 Learning Materials", "2 KAD", "docs"]

            for dir_name in required_dirs:
                dir_path = course_dir / dir_name
                assert dir_path.exists(), f"Required directory {dir_name} should exist"

            # Check KAD subdirectories
            kad_dir = course_dir / "2 KAD"
            kad_subdirs = [
                "1 LAP",
                "2 Preassess Validation",
                "3 Postassess Validation",
                "4 Assess Sub and FB Form",
                "5 Assess Tool",
                "6 Marking Guide",
                "7 Assess Mapping Matrix",
            ]

            for subdir in kad_subdirs:
                subdir_path = kad_dir / subdir
                assert subdir_path.exists(), f"KAD subdirectory {subdir} should exist"

    def test_assessment_tools_structure_validation(
        self, temp_test_dir, aiss_config, example_course_path
    ):
        """Test that assessment tools are created with correct structure."""
        with patch("gpt.models.openai_.Chat") as mock_client:
            mock_client.return_value = MagicMock()

            # Run init
            init_course(
                course_name=aiss_config["course_name"],
                target_path=Path(temp_test_dir),
                course_type=aiss_config["course_type"],
                num_weeks=aiss_config["weeks"],
                delivery_mode=aiss_config["delivery_mode"],
                institution_name=aiss_config["institution"],
                student_cohort=aiss_config["student_cohort"],
                mission_prompt=aiss_config["mission"],
                uoc_codes=[u["id"] for u in aiss_config["units"]],
            )

            course_dir = Path(temp_test_dir) / aiss_config["course_name"]
            assess_tool_dir = course_dir / "2 KAD" / "5 Assess Tool"

            # Check that assessment directories are created
            expected_assessments = [
                "AT1 Identify Opportunities for AI Task Automation",
                "AT2 Knowledge Based Assessment",
                "AT3 Knowledge Based Assessment",
                "AT4 Apply Machine Learning to Task Automation",
            ]

            for assessment in expected_assessments:
                assessment_path = assess_tool_dir / assessment
                assert assessment_path.exists(), (
                    f"Assessment directory {assessment} should exist"
                )

                # Check for assessment.md file
                assessment_file = assessment_path / "assessment.md"
                assert assessment_file.exists(), (
                    f"assessment.md should exist in {assessment}"
                )

    def test_assessment_content_structure_validation(
        self, temp_test_dir, aiss_config, example_course_path
    ):
        """Test that assessment content follows expected format."""
        with patch("gpt.models.openai_.Chat") as mock_client:
            mock_client.return_value = MagicMock()

            # Run init
            init_course(
                course_name=aiss_config["course_name"],
                target_path=Path(temp_test_dir),
                course_type=aiss_config["course_type"],
                num_weeks=aiss_config["weeks"],
                delivery_mode=aiss_config["delivery_mode"],
                institution_name=aiss_config["institution"],
                student_cohort=aiss_config["student_cohort"],
                mission_prompt=aiss_config["mission"],
                uoc_codes=[u["id"] for u in aiss_config["units"]],
            )

            course_dir = Path(temp_test_dir) / aiss_config["course_name"]
            assess_tool_dir = course_dir / "2 KAD" / "5 Assess Tool"

            # Validate first assessment content structure
            at1_dir = (
                assess_tool_dir / "AT1 Identify Opportunities for AI Task Automation"
            )
            at1_file = at1_dir / "assessment.md"

            assert at1_file.exists(), "AT1 assessment.md should exist"

            # Read and validate content structure
            with open(at1_file, "r") as f:
                content = f.read()

            # Check for required frontmatter sections
            required_sections = [
                "name:",
                "description:",
                "observation_checklist:",
                "qualification_national_code_and_title:",
                "units:",
                "mapping:",
            ]

            for section in required_sections:
                assert section in content, (
                    f"Required section {section} should be in assessment content"
                )

            # Check for required content sections
            required_content = [
                "# Assessment Resources:",
                "# Assessment Instructions:",
                "# Assessment Instrument:",
                "### Task 1:",
                "### Task 2:",
                "### Task 3:",
                "### Task 4:",
            ]

            for content_section in required_content:
                assert content_section in content, (
                    f"Required content section {content_section} should be present"
                )

    def test_learning_materials_structure_validation(self, temp_test_dir, aiss_config):
        """Test that learning materials directory structure is correct."""
        with patch("gpt.models.openai_.Chat") as mock_client:
            mock_client.return_value = MagicMock()

            # Run init
            init_course(
                course_name=aiss_config["course_name"],
                target_path=Path(temp_test_dir),
                course_type=aiss_config["course_type"],
                num_weeks=aiss_config["weeks"],
                delivery_mode=aiss_config["delivery_mode"],
                institution_name=aiss_config["institution"],
                student_cohort=aiss_config["student_cohort"],
                mission_prompt=aiss_config["mission"],
                uoc_codes=[u["id"] for u in aiss_config["units"]],
            )

            course_dir = Path(temp_test_dir) / aiss_config["course_name"]
            learning_materials_dir = course_dir / "1 Learning Materials"

            # Check that week directories are created
            for week_num in range(1, aiss_config["weeks"] + 1):
                week_dir = learning_materials_dir / f"Week {week_num}"
                assert week_dir.exists(), f"Week {week_num} directory should exist"

                # Check for required files in each week
                required_files = ["slides.md", "footer.png"]
                for file_name in required_files:
                    file_path = week_dir / file_name
                    assert file_path.exists(), (
                        f"{file_name} should exist in Week {week_num}"
                    )

    def test_push_function_validation(self, temp_test_dir, aiss_config):
        """Test that push function generates all required documents."""
        with patch("gpt.models.openai_.Chat") as mock_client:
            mock_client.return_value = MagicMock()

            # Run init first
            init_course(
                course_name=aiss_config["course_name"],
                target_path=Path(temp_test_dir),
                course_type=aiss_config["course_type"],
                num_weeks=aiss_config["weeks"],
                delivery_mode=aiss_config["delivery_mode"],
                institution_name=aiss_config["institution"],
                student_cohort=aiss_config["student_cohort"],
                mission_prompt=aiss_config["mission"],
                uoc_codes=[u["id"] for u in aiss_config["units"]],
            )

            course_dir = Path(temp_test_dir) / aiss_config["course_name"]
            output_dir = Path(temp_test_dir) / f"output_{aiss_config['course_name']}"

            # Set required environment variables for push function
            os.environ["COURSE_CONTENT"] = str(course_dir)  # Source content directory
            os.environ["OUTPUT_LOCATION"] = str(output_dir)  # Output display directory
            os.environ["ROOT_DIR"] = str(Path.cwd())  # Repository root

            # Run push to generate documents
            # Create args object for generate function
            class Args:
                def __init__(self, target):
                    self.target = target

            args = Args(str(course_dir))
            push(args)

            # Validate that required documents are generated in the output directory
            required_documents = [
                "2 KAD/1 LAP/Learning and Assessment Plan (F122A14).docx",
                "2 KAD/5 Assess Tool/AT1 Identify Opportunities for AI Task Automation/Assessment Task Tool (F122A12).docx",
                "2 KAD/5 Assess Tool/AT2 Knowledge Based Assessment/Assessment Task Tool (F122A12).docx",
                "2 KAD/5 Assess Tool/AT3 Knowledge Based Assessment/Assessment Task Tool (F122A12).docx",
                "2 KAD/5 Assess Tool/AT4 Apply Machine Learning to Task Automation/Assessment Task Tool (F122A12).docx",
                "2 KAD/7 Assess Mapping Matrix/ICTAII401 Assessment Mapping Matrix (F122A8).docx",
                "2 KAD/7 Assess Mapping Matrix/ICTAII501 Assessment Mapping Matrix (F122A8).docx",
                "2 KAD/7 Assess Mapping Matrix/ICTAII502 Assessment Mapping Matrix (F122A8).docx",
            ]

            for doc_path in required_documents:
                full_path = output_dir / doc_path
                assert full_path.exists(), (
                    f"Required document {doc_path} should be generated in output directory"
                )

    def test_content_format_consistency(
        self, temp_test_dir, aiss_config, example_course_path
    ):
        """Test that generated content format matches example course format."""
        with patch("gpt.models.openai_.Chat") as mock_client:
            mock_client.return_value = MagicMock()

            # Run init
            init_course(
                course_name=aiss_config["course_name"],
                target_path=Path(temp_test_dir),
                course_type=aiss_config["course_type"],
                num_weeks=aiss_config["weeks"],
                delivery_mode=aiss_config["delivery_mode"],
                institution_name=aiss_config["institution"],
                student_cohort=aiss_config["student_cohort"],
                mission_prompt=aiss_config["mission"],
                uoc_codes=[u["id"] for u in aiss_config["units"]],
            )

            course_dir = Path(temp_test_dir) / aiss_config["course_name"]

            # Compare generated structure with example
            example_assess_tool_dir = example_course_path / "2 KAD" / "5 Assess Tool"
            generated_assess_tool_dir = course_dir / "2 KAD" / "5 Assess Tool"

            # Check that assessment directories match
            example_assessments = [
                d.name for d in example_assess_tool_dir.iterdir() if d.is_dir()
            ]
            generated_assessments = [
                d.name for d in generated_assess_tool_dir.iterdir() if d.is_dir()
            ]

            assert set(example_assessments) == set(generated_assessments), (
                "Generated assessment directories should match example structure"
            )

    def test_config_validation(self, aiss_config):
        """Test that the AISS config contains all required fields."""
        required_fields = [
            "mission",
            "course_name",
            "course_type",
            "weeks",
            "delivery_mode",
            "institution",
            "student_cohort",
            "units",
        ]

        for field in required_fields:
            assert field in aiss_config, f"Required field {field} should be in config"
            assert aiss_config[field], f"Required field {field} should not be empty"

        # Validate units structure
        assert isinstance(aiss_config["units"], list), "Units should be a list"
        for unit in aiss_config["units"]:
            assert "name" in unit, "Each unit should have a name"
            assert "id" in unit, "Each unit should have an id"

    def test_error_handling_validation(self, temp_test_dir, aiss_config):
        """Test error handling for invalid configurations."""
        # Test with invalid course type
        with pytest.raises(ValueError):
            init_course(
                course_name=aiss_config["course_name"],
                target_path=Path(temp_test_dir),
                course_type="invalid_type",
                num_weeks=aiss_config["weeks"],
                delivery_mode=aiss_config["delivery_mode"],
                institution_name=aiss_config["institution"],
                student_cohort=aiss_config["student_cohort"],
                mission_prompt=aiss_config["mission"],
                uoc_codes=[u["id"] for u in aiss_config["units"]],
            )

        # Test with invalid delivery mode
        with pytest.raises(ValueError):
            init_course(
                course_name=aiss_config["course_name"],
                target_path=Path(temp_test_dir),
                course_type=aiss_config["course_type"],
                num_weeks=aiss_config["weeks"],
                delivery_mode="invalid_mode",
                institution_name=aiss_config["institution"],
                student_cohort=aiss_config["student_cohort"],
                mission_prompt=aiss_config["mission"],
                uoc_codes=[u["id"] for u in aiss_config["units"]],
            )
