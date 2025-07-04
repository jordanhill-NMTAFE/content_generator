#!/usr/bin/env python3
"""
Integration tests for CLI workflows.
Tests complete end-to-end functionality including file system operations.
"""

import sys
import os
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from argparse import Namespace

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.main import init, push, create_config


class TestCLIWorkflows(unittest.TestCase):
    """Integration tests for complete CLI workflows."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        # Set required environment variables
        os.environ["COURSE_CONTENT"] = self.temp_dir
        os.environ["OUTPUT_LOCATION"] = self.temp_dir

    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("src.main.init_course")
    def test_init_workflow_basic(self, mock_init_course):
        """Test basic init workflow."""
        # Set up mock
        course_path = Path(self.temp_dir) / "Test Course"
        mock_init_course.return_value = course_path

        # Create args
        args = Namespace(
            course_name="Test Course",
            target=self.temp_dir,
            uoc_codes=["ICTAII401"],
            mission="Test mission",
            no_llm=False,
            course_type="TAFE",
            num_weeks=None,
            academic_weeks=None,
            reassessment_weeks=None,
            delivery_location=None,
            delivery_mode="face-to-face",
            institution_name=None,
            student_cohort=None,
            config_file=None,
        )

        # Execute init workflow
        with patch("builtins.print"):
            init(args)

        # Verify init_course was called with correct parameters
        mock_init_course.assert_called_once_with(
            "Test Course",
            Path(self.temp_dir),
            ["ICTAII401"],
            "Test mission",
            False,
            course_type="TAFE",
            num_weeks=None,
            academic_weeks=None,
            reassessment_weeks=None,
            delivery_location=None,
            delivery_mode="face-to-face",
            institution_name=None,
            student_cohort=None,
            config_file=None,
        )

    @patch("src.main.init_course")
    def test_init_workflow_with_all_options(self, mock_init_course):
        """Test init workflow with all options."""
        course_path = Path(self.temp_dir) / "Advanced Course"
        mock_init_course.return_value = course_path

        args = Namespace(
            course_name="Advanced Course",
            target=self.temp_dir,
            uoc_codes=["ICTAII401", "ICTAII501"],
            mission="Advanced AI course mission",
            no_llm=False,
            course_type="COMMERCIAL",
            num_weeks=12,
            academic_weeks=10,
            reassessment_weeks=2,
            delivery_location="Perth Campus",
            delivery_mode="hybrid",
            institution_name="Test Institution",
            student_cohort="Adult learners",
            config_file=None,
        )

        with patch("builtins.print"):
            init(args)

        # Verify all parameters were passed correctly
        mock_init_course.assert_called_once_with(
            "Advanced Course",
            Path(self.temp_dir),
            ["ICTAII401", "ICTAII501"],
            "Advanced AI course mission",
            False,
            course_type="COMMERCIAL",
            num_weeks=12,
            academic_weeks=10,
            reassessment_weeks=2,
            delivery_location="Perth Campus",
            delivery_mode="hybrid",
            institution_name="Test Institution",
            student_cohort="Adult learners",
            config_file=None,
        )

    @patch("src.main.lap")
    @patch("src.main.assess_tool")
    @patch("src.main.mapping_matrix")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_dir")
    @patch("os.environ")
    def test_push_workflow_basic(
        self, mock_env, mock_is_dir, mock_exists, mock_matrix, mock_assess, mock_lap
    ):
        """Test basic push workflow."""
        # Set up mocks
        mock_exists.return_value = True
        mock_is_dir.return_value = True
        mock_env.__getitem__.side_effect = lambda key: {
            "COURSE_CONTENT": self.temp_dir,
            "OUTPUT_LOCATION": self.temp_dir,
        }[key]

        # Mock document generation functions
        mock_lap.return_value = None
        mock_assess.return_value = None
        mock_matrix.return_value = None

        # Create args
        args = Namespace(target=self.temp_dir)

        # Execute push workflow
        with patch("builtins.print"):
            push(args)

        # Verify all document generators were called
        mock_lap.assert_called_once()
        mock_assess.assert_called_once()
        mock_matrix.assert_called_once()

    @patch("builtins.open", create=True)
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.mkdir")
    def test_config_workflow_basic(self, mock_mkdir, mock_exists, mock_open):
        """Test basic config creation workflow."""
        # Set up mocks
        mock_exists.return_value = False
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        # Create args
        args = Namespace(
            create="test_config.yaml", template="tafe", output_dir=self.temp_dir
        )

        # Execute config workflow
        with patch("builtins.print"):
            create_config(args)

        # Verify file operations
        mock_open.assert_called()
        mock_file.write.assert_called()

    @patch("src.main.init_course")
    @patch("src.main.lap")
    @patch("src.main.assess_tool")
    @patch("src.main.mapping_matrix")
    def test_full_init_to_push_workflow(
        self, mock_matrix, mock_assess, mock_lap, mock_init_course
    ):
        """Test complete workflow from init to push."""
        # Set up course directory structure
        course_dir = Path(self.temp_dir) / "Full Test Course"
        course_dir.mkdir(parents=True)

        # Create basic course structure
        (course_dir / "course_config.yaml").touch()
        (course_dir / "1 Learning Materials").mkdir()
        (course_dir / "2 KAD").mkdir()

        mock_init_course.return_value = course_dir

        # Step 1: Init course
        init_args = Namespace(
            course_name="Full Test Course",
            target=self.temp_dir,
            uoc_codes=["ICTAII401"],
            mission="Full workflow test",
            no_llm=True,  # Skip LLM to avoid API calls
            course_type="TAFE",
            num_weeks=None,
            academic_weeks=None,
            reassessment_weeks=None,
            delivery_location=None,
            delivery_mode="face-to-face",
            institution_name=None,
            student_cohort=None,
            config_file=None,
        )

        with patch("builtins.print"):
            init(init_args)

        mock_init_course.assert_called_once_with(
            "Full Test Course",
            Path(self.temp_dir),
            ["ICTAII401"],
            "Full workflow test",
            True,
            course_type="TAFE",
            num_weeks=None,
            academic_weeks=None,
            reassessment_weeks=None,
            delivery_location=None,
            delivery_mode="face-to-face",
            institution_name=None,
            student_cohort=None,
            config_file=None,
        )

        # Step 2: Push documents
        mock_lap.return_value = None
        mock_assess.return_value = None
        mock_matrix.return_value = None

        push_args = Namespace(target=str(course_dir))

        with patch("builtins.print"):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.is_dir", return_value=True):
                    with patch("os.environ") as mock_env:
                        mock_env.__getitem__.side_effect = lambda key: {
                            "COURSE_CONTENT": str(course_dir),
                            "OUTPUT_LOCATION": str(course_dir),
                        }[key]
                        push(push_args)

        # Verify push operations were called
        mock_lap.assert_called_once()
        mock_assess.assert_called_once()
        mock_matrix.assert_called_once()

    def test_config_template_variations(self):
        """Test config creation with different templates."""
        templates = ["basic", "tafe", "commercial", "accelerated", "custom"]

        for template in templates:
            with self.subTest(template=template):
                with patch("builtins.open", create=True) as mock_open:
                    with patch("pathlib.Path.exists", return_value=False):
                        with patch("pathlib.Path.mkdir"):
                            mock_file = MagicMock()
                            mock_open.return_value.__enter__.return_value = mock_file

                            args = Namespace(
                                create=f"{template}_config.yaml",
                                template=template,
                                output_dir=self.temp_dir,
                            )

                            with patch("builtins.print"):
                                create_config(args)

                            # Verify file was written
                            mock_file.write.assert_called()

    @patch("src.main.init_course")
    def test_init_with_config_file(self, mock_init_course):
        """Test init workflow with configuration file."""
        # Create a test config file
        config_path = Path(self.temp_dir) / "test_config.yaml"
        config_content = """
course_name: "Config Test Course"
course_type: "COMMERCIAL"
num_weeks: 16
units:
  - id: "ICTAII401"
    name: "Test Unit"
mission: "Config file mission"
"""
        config_path.write_text(config_content)

        course_path = Path(self.temp_dir) / "Config Test Course"
        mock_init_course.return_value = course_path

        args = Namespace(
            course_name="Config Test Course",
            target=self.temp_dir,
            uoc_codes=None,
            mission=None,
            no_llm=False,
            course_type="TAFE",  # Should be overridden by config
            num_weeks=None,
            academic_weeks=None,
            reassessment_weeks=None,
            delivery_location=None,
            delivery_mode="face-to-face",
            institution_name=None,
            student_cohort=None,
            config_file=str(config_path),
        )

        with patch("builtins.print"):
            init(args)

        mock_init_course.assert_called_once_with(
            "Config Test Course",
            Path(self.temp_dir),
            None,
            None,
            False,
            course_type="TAFE",
            num_weeks=None,
            academic_weeks=None,
            reassessment_weeks=None,
            delivery_location=None,
            delivery_mode="face-to-face",
            institution_name=None,
            student_cohort=None,
            config_file=str(config_path),
        )

    def test_error_handling_missing_target(self):
        """Test error handling for missing target directory."""
        args = Namespace(target="/nonexistent/directory")

        with patch("builtins.print"):
            with patch("pathlib.Path.exists", return_value=False):
                # Should handle missing directory gracefully
                try:
                    push(args)
                except SystemExit:
                    pass  # Expected for missing directory

    def test_error_handling_invalid_config(self):
        """Test error handling for invalid configuration file."""
        # Create invalid config file
        config_path = Path(self.temp_dir) / "invalid_config.yaml"
        config_path.write_text("invalid: yaml: content:")

        args = Namespace(
            course_name="Test Course",
            target=self.temp_dir,
            config_file=str(config_path),
            uoc_codes=None,
            mission=None,
            no_llm=False,
            course_type="TAFE",
            num_weeks=None,
            academic_weeks=None,
            reassessment_weeks=None,
            delivery_location=None,
            delivery_mode="face-to-face",
            institution_name=None,
            student_cohort=None,
        )

        with patch("builtins.print"):
            # Should handle invalid YAML gracefully
            try:
                init(args)
            except Exception:
                pass  # Expected for invalid config

    @patch("src.main.init_course")
    def test_init_with_multiline_mission(self, mock_init_course):
        """Test init workflow with multiline mission prompt."""
        course_path = Path(self.temp_dir) / "Mission Test Course"
        mock_init_course.return_value = course_path

        multiline_mission = """This is a multiline mission prompt
that spans multiple lines
and includes detailed course objectives."""

        args = Namespace(
            course_name="Mission Test Course",
            target=self.temp_dir,
            uoc_codes=["ICTAII401"],
            mission=multiline_mission,
            no_llm=False,
            course_type="TAFE",
            num_weeks=None,
            academic_weeks=None,
            reassessment_weeks=None,
            delivery_location=None,
            delivery_mode="face-to-face",
            institution_name=None,
            student_cohort=None,
            config_file=None,
        )

        with patch("builtins.print"):
            init(args)

        # Verify mission was passed correctly
        mock_init_course.assert_called_once_with(
            "Mission Test Course",
            Path(self.temp_dir),
            ["ICTAII401"],
            multiline_mission,
            False,
            course_type="TAFE",
            num_weeks=None,
            academic_weeks=None,
            reassessment_weeks=None,
            delivery_location=None,
            delivery_mode="face-to-face",
            institution_name=None,
            student_cohort=None,
            config_file=None,
        )


class TestCLIIntegrationErrors(unittest.TestCase):
    """Integration tests for CLI error handling."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_push_without_environment_variables(self):
        """Test push command without required environment variables."""
        args = Namespace(target=self.temp_dir)

        # Remove environment variables
        old_course_content = os.environ.pop("COURSE_CONTENT", None)
        old_output_location = os.environ.pop("OUTPUT_LOCATION", None)

        try:
            with patch("builtins.print"):
                # Should handle missing environment variables
                push(args)
        except (KeyError, SystemExit, FileNotFoundError):
            pass  # Expected behavior
        finally:
            # Restore environment variables
            if old_course_content:
                os.environ["COURSE_CONTENT"] = old_course_content
            if old_output_location:
                os.environ["OUTPUT_LOCATION"] = old_output_location

    def test_config_file_permissions(self):
        """Test config creation with permission issues."""
        # Create read-only directory
        readonly_dir = Path(self.temp_dir) / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)

        args = Namespace(
            create="test_config.yaml", template="basic", output_dir=str(readonly_dir)
        )

        try:
            with patch("builtins.print"):
                create_config(args)
        except (PermissionError, OSError):
            pass  # Expected for permission issues
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)


if __name__ == "__main__":
    unittest.main()
