#!/usr/bin/env python3
"""
Integration tests for CLI functionality
"""

import sys
import os
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO
from argparse import Namespace

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.main import parser, init, create_config, push


class TestCLIIntegration(unittest.TestCase):
    """Integration tests for CLI functionality."""

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

    def test_parser_help(self):
        """Test that parser shows help correctly."""
        with patch("sys.stdout", new=StringIO()) as fake_out:
            with self.assertRaises(SystemExit):
                parser.parse_args(["--help"])
            output = fake_out.getvalue()
            self.assertIn("usage:", output)
            self.assertIn("init", output)
            self.assertIn("push", output)
            self.assertIn("config", output)

    def test_init_command_help(self):
        """Test init command help."""
        with patch("sys.stdout", new=StringIO()) as fake_out:
            with self.assertRaises(SystemExit):
                parser.parse_args(["init", "--help"])
            output = fake_out.getvalue()
            self.assertIn("course-name", output)
            self.assertIn("target", output)
            self.assertIn("uoc-codes", output)
            self.assertIn("mission", output)
            self.assertIn("no-llm", output)

    def test_push_command_help(self):
        """Test push command help."""
        with patch("sys.stdout", new=StringIO()) as fake_out:
            with self.assertRaises(SystemExit):
                parser.parse_args(["push", "--help"])
            output = fake_out.getvalue()
            self.assertIn("target", output)

    def test_config_command_help(self):
        """Test config command help."""
        with patch("sys.stdout", new=StringIO()) as fake_out:
            with self.assertRaises(SystemExit):
                parser.parse_args(["config", "--help"])
            output = fake_out.getvalue()
            self.assertIn("create", output)
            self.assertIn("template", output)
            self.assertIn("output-dir", output)

    def test_init_command_required_args(self):
        """Test init command with required arguments."""
        args = parser.parse_args(
            ["init", "--course-name", "Test Course", "--target", self.temp_dir]
        )
        self.assertEqual(args.command, "init")
        self.assertEqual(args.course_name, "Test Course")
        self.assertEqual(args.target, self.temp_dir)

    def test_init_command_with_uoc_codes(self):
        """Test init command with UOC codes."""
        args = parser.parse_args(
            [
                "init",
                "--course-name",
                "Test Course",
                "--uoc-codes",
                "ICTAII401",
                "ICTAII501",
            ]
        )
        self.assertEqual(args.uoc_codes, ["ICTAII401", "ICTAII501"])

    def test_init_command_with_mission(self):
        """Test init command with mission prompt."""
        args = parser.parse_args(
            [
                "init",
                "--course-name",
                "Test Course",
                "--mission",
                "This is a test mission",
            ]
        )
        self.assertEqual(args.mission, "This is a test mission")

    def test_init_command_with_no_llm(self):
        """Test init command with no-llm flag."""
        args = parser.parse_args(["init", "--course-name", "Test Course", "--no-llm"])
        self.assertTrue(args.no_llm)

    def test_init_command_course_type_options(self):
        """Test init command with different course types."""
        course_types = ["TAFE", "COMMERCIAL", "ACCELERATED", "CUSTOM"]
        for course_type in course_types:
            args = parser.parse_args(
                ["init", "--course-name", "Test Course", "--course-type", course_type]
            )
            self.assertEqual(args.course_type, course_type)

    def test_init_command_weeks_options(self):
        """Test init command with weeks options."""
        args = parser.parse_args(
            [
                "init",
                "--course-name",
                "Test Course",
                "--num-weeks",
                "12",
                "--academic-weeks",
                "10",
                "--reassessment-weeks",
                "2",
            ]
        )
        self.assertEqual(args.num_weeks, 12)
        self.assertEqual(args.academic_weeks, 10)
        self.assertEqual(args.reassessment_weeks, 2)

    def test_init_command_delivery_options(self):
        """Test init command with delivery options."""
        args = parser.parse_args(
            [
                "init",
                "--course-name",
                "Test Course",
                "--delivery-location",
                "Perth Campus",
                "--delivery-mode",
                "hybrid",
                "--institution-name",
                "Test Institution",
                "--student-cohort",
                "Adult learners",
            ]
        )
        self.assertEqual(args.delivery_location, "Perth Campus")
        self.assertEqual(args.delivery_mode, "hybrid")
        self.assertEqual(args.institution_name, "Test Institution")
        self.assertEqual(args.student_cohort, "Adult learners")

    def test_init_command_config_file(self):
        """Test init command with config file."""
        args = parser.parse_args(
            ["init", "--course-name", "Test Course", "--config-file", "config.yaml"]
        )
        self.assertEqual(args.config_file, "config.yaml")

    def test_push_command_with_target(self):
        """Test push command with target."""
        args = parser.parse_args(["push", "--target", "/path/to/course"])
        self.assertEqual(args.command, "push")
        self.assertEqual(args.target, "/path/to/course")

    def test_push_command_without_target(self):
        """Test push command without target."""
        args = parser.parse_args(["push"])
        self.assertEqual(args.command, "push")
        self.assertIsNone(args.target)

    def test_config_command_create(self):
        """Test config command with create option."""
        args = parser.parse_args(["config", "--create", "my_config.yaml"])
        self.assertEqual(args.command, "config")
        self.assertEqual(args.create, "my_config.yaml")

    def test_config_command_template_options(self):
        """Test config command with different templates."""
        templates = ["basic", "tafe", "commercial", "accelerated", "custom"]
        for template in templates:
            args = parser.parse_args(
                ["config", "--create", "config.yaml", "--template", template]
            )
            self.assertEqual(args.template, template)

    def test_config_command_output_dir(self):
        """Test config command with output directory."""
        args = parser.parse_args(
            ["config", "--create", "config.yaml", "--output-dir", "/path/to/output"]
        )
        self.assertEqual(args.output_dir, "/path/to/output")

    def test_config_command_defaults(self):
        """Test config command defaults."""
        args = parser.parse_args(["config", "--create", "config.yaml"])
        self.assertEqual(args.template, "basic")
        self.assertEqual(args.output_dir, ".")

    @patch("src.main.init_course")
    def test_init_function_call(self, mock_init_course):
        """Test init function call with proper arguments."""
        # Configure the mock to return a valid course path
        mock_init_course.return_value = Path(self.temp_dir) / "Test Course"

        args = Namespace(
            command="init",
            course_name="Test Course",
            target=self.temp_dir,
            uoc_codes=["ICTAII401"],
            mission="Test mission",
            no_llm=False,
            course_type="TAFE",
            num_weeks=20,
            academic_weeks=18,
            reassessment_weeks=2,
            delivery_location="Perth",
            delivery_mode="face-to-face",
            institution_name="Test Institution",
            student_cohort="Adult learners",
            config_file=None,
        )

        init(args)

        mock_init_course.assert_called_once_with(
            "Test Course",
            Path(self.temp_dir),
            ["ICTAII401"],
            "Test mission",
            False,
            course_type="TAFE",
            num_weeks=20,
            academic_weeks=18,
            reassessment_weeks=2,
            delivery_location="Perth",
            delivery_mode="face-to-face",
            institution_name="Test Institution",
            student_cohort="Adult learners",
            config_file=None,
            model="gpt-4.1-nano-2025-04-14",
        )

    @patch("src.main.lap")
    @patch("src.main.assess_tool")
    @patch("src.main.mapping_matrix")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_dir")
    @patch("os.environ")
    def test_generate_function_calls(
        self, mock_env, mock_is_dir, mock_exists, mock_matrix, mock_assess, mock_lap
    ):
        """Test generate function calls with proper mocking."""
        mock_exists.return_value = True
        mock_is_dir.return_value = True
        mock_env.__getitem__.return_value = self.temp_dir

        args = Namespace(command="push", target=self.temp_dir)

        push(args)

        # Verify all document generation functions were called
        # The functions use global variables, so we check they were called without arguments
        mock_lap.assert_called_once()
        mock_assess.assert_called_once()
        mock_matrix.assert_called_once()

        # Check the actual call arguments to see what paths were used
        lap_call_args = mock_lap.call_args
        assess_call_args = mock_assess.call_args
        matrix_call_args = mock_matrix.call_args

        # The functions should be called with Path objects
        self.assertEqual(len(lap_call_args[0]), 2)  # Should have 2 arguments
        self.assertEqual(len(assess_call_args[0]), 2)  # Should have 2 arguments
        self.assertEqual(len(matrix_call_args[0]), 2)  # Should have 2 arguments

        # Verify the arguments are Path objects
        self.assertIsInstance(lap_call_args[0][0], Path)
        self.assertIsInstance(lap_call_args[0][1], Path)
        self.assertIsInstance(assess_call_args[0][0], Path)
        self.assertIsInstance(assess_call_args[0][1], Path)
        self.assertIsInstance(matrix_call_args[0][0], Path)
        self.assertIsInstance(matrix_call_args[0][1], Path)

    @patch("builtins.open", create=True)
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.mkdir")
    def test_create_config_function(self, mock_mkdir, mock_exists, mock_open):
        """Test create config function."""
        mock_exists.return_value = False
        mock_open.return_value.__enter__.return_value.write = MagicMock()

        args = Namespace(
            command="config",
            create="test_config.yaml",
            template="tafe",
            output_dir=".",
        )

        create_config(args)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_open.assert_called_once()

    def test_init_command_missing_required_args(self):
        """Test init command with missing required arguments."""
        with self.assertRaises(SystemExit):
            parser.parse_args(["init"])

    def test_init_command_invalid_course_type(self):
        """Test init command with invalid course type."""
        with self.assertRaises(SystemExit):
            parser.parse_args(
                ["init", "--course-name", "Test Course", "--course-type", "INVALID"]
            )

    def test_init_command_invalid_delivery_mode(self):
        """Test init command with invalid delivery mode."""
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "init",
                    "--course-name",
                    "Test Course",
                    "--delivery-mode",
                    "INVALID",
                ]
            )

    def test_config_command_invalid_template(self):
        """Test config command with invalid template."""
        with self.assertRaises(SystemExit):
            parser.parse_args(
                ["config", "--create", "config.yaml", "--template", "INVALID"]
            )

    def test_parser_no_command(self):
        """Test parser with no command."""
        args = parser.parse_args([])
        self.assertIsNone(args.command)

    def test_parser_unknown_command(self):
        """Test parser with unknown command."""
        with self.assertRaises(SystemExit):
            parser.parse_args(["unknown"])

    @patch(
        "builtins.input", return_value="Test mission line 1\nTest mission line 2\n<<"
    )
    def test_init_command_multiline_mission(self, mock_input):
        """Test init command with multiline mission prompt."""
        args = parser.parse_args(
            ["init", "--course-name", "Test Course", "--mission", "<<"]
        )
        self.assertEqual(args.mission, "<<")

    def test_init_command_short_options(self):
        """Test init command with short options."""
        args = parser.parse_args(
            [
                "init",
                "-c",
                "Test Course",
                "-t",
                self.temp_dir,
                "-u",
                "ICTAII401",
                "ICTAII501",
                "-m",
                "Test mission",
                "--no-llm",
                "-ct",
                "TAFE",
                "-w",
                "20",
                "-aw",
                "18",
                "-rw",
                "2",
                "-l",
                "Perth",
                "-dm",
                "face-to-face",
                "-in",
                "Test Institution",
                "-sc",
                "Adult learners",
                "-cf",
                "config.yaml",
            ]
        )
        self.assertEqual(args.course_name, "Test Course")
        self.assertEqual(args.target, self.temp_dir)
        self.assertEqual(args.uoc_codes, ["ICTAII401", "ICTAII501"])
        self.assertEqual(args.mission, "Test mission")
        self.assertTrue(args.no_llm)
        self.assertEqual(args.course_type, "TAFE")
        self.assertEqual(args.num_weeks, 20)
        self.assertEqual(args.academic_weeks, 18)
        self.assertEqual(args.reassessment_weeks, 2)
        self.assertEqual(args.delivery_location, "Perth")
        self.assertEqual(args.delivery_mode, "face-to-face")
        self.assertEqual(args.institution_name, "Test Institution")
        self.assertEqual(args.student_cohort, "Adult learners")
        self.assertEqual(args.config_file, "config.yaml")

    def test_config_command_short_options(self):
        """Test config command with short options."""
        args = parser.parse_args(
            [
                "config",
                "-c",
                "test_config.yaml",
                "-t",
                "tafe",
                "-o",
                "/path/to/output",
            ]
        )
        self.assertEqual(args.create, "test_config.yaml")
        self.assertEqual(args.template, "tafe")
        self.assertEqual(args.output_dir, "/path/to/output")


class TestCLIIntegrationWorkflows(unittest.TestCase):
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
    def test_full_init_workflow(self, mock_init_course):
        """Test complete init workflow."""
        # Configure the mock to return a valid course path
        mock_init_course.return_value = Path(self.temp_dir) / "Test Course"

        args = Namespace(
            command="init",
            course_name="Test Course",
            target=self.temp_dir,
            uoc_codes=["ICTAII401", "ICTAII501"],
            mission="Test mission for AI course development",
            no_llm=False,
            course_type="TAFE",
            num_weeks=20,
            academic_weeks=18,
            reassessment_weeks=2,
            delivery_location="Perth Campus",
            delivery_mode="face-to-face",
            institution_name="Test Institution",
            student_cohort="Adult learners",
            config_file=None,
        )

        init(args)

        mock_init_course.assert_called_once_with(
            "Test Course",
            Path(self.temp_dir),
            ["ICTAII401", "ICTAII501"],
            "Test mission for AI course development",
            False,
            course_type="TAFE",
            num_weeks=20,
            academic_weeks=18,
            reassessment_weeks=2,
            delivery_location="Perth Campus",
            delivery_mode="face-to-face",
            institution_name="Test Institution",
            student_cohort="Adult learners",
            config_file=None,
            model="gpt-4.1-nano-2025-04-14",
        )

    @patch("builtins.open", create=True)
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.mkdir")
    def test_full_config_workflow(self, mock_mkdir, mock_exists, mock_open):
        """Test complete config creation workflow."""
        mock_exists.return_value = False
        mock_open.return_value.__enter__.return_value.write = MagicMock()

        args = Namespace(
            command="config",
            create="test_config.yaml",
            template="tafe",
            output_dir=".",
        )

        create_config(args)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
