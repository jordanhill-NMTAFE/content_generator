#!/usr/bin/env python3
"""
Unit tests for CLI argument parsing.
Tests individual parser functionality in isolation.
"""

import sys
import os
import unittest
from unittest.mock import patch
from io import StringIO

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.main import parser


class TestCLIParser(unittest.TestCase):
    """Unit tests for CLI argument parser."""

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
            ["init", "--course-name", "Test Course", "--target", "/tmp/test"]
        )
        self.assertEqual(args.command, "init")
        self.assertEqual(args.course_name, "Test Course")
        self.assertEqual(args.target, "/tmp/test")

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
                [
                    "init",
                    "--course-name",
                    "Test Course",
                    "--course-type",
                    course_type,
                ]
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
            [
                "init",
                "--course-name",
                "Test Course",
                "--config-file",
                "config.yaml",
            ]
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
            args = parser.parse_args(["config", "--template", template])
            self.assertEqual(args.template, template)

    def test_config_command_output_dir(self):
        """Test config command with output directory."""
        args = parser.parse_args(["config", "--output-dir", "/custom/output"])
        self.assertEqual(args.output_dir, "/custom/output")

    def test_config_command_defaults(self):
        """Test config command defaults."""
        args = parser.parse_args(["config"])
        self.assertEqual(args.command, "config")
        self.assertIsNone(args.create)
        self.assertEqual(args.template, "basic")
        self.assertEqual(args.output_dir, ".")

    def test_init_command_short_options(self):
        """Test init command with short option names."""
        args = parser.parse_args(
            [
                "init",
                "-c",
                "Test Course",
                "-t",
                "/tmp/test",
                "-u",
                "ICTAII401",
                "ICTAII501",
                "-m",
                "Test mission",
                "-ct",
                "COMMERCIAL",
                "-w",
                "10",
                "-aw",
                "8",
                "-rw",
                "2",
                "-l",
                "Perth",
                "-dm",
                "online",
                "-in",
                "Test Institution",
                "-sc",
                "Adult learners",
                "-cf",
                "config.yaml",
            ]
        )
        self.assertEqual(args.course_name, "Test Course")
        self.assertEqual(args.target, "/tmp/test")
        self.assertEqual(args.uoc_codes, ["ICTAII401", "ICTAII501"])
        self.assertEqual(args.mission, "Test mission")
        self.assertEqual(args.course_type, "COMMERCIAL")
        self.assertEqual(args.num_weeks, 10)
        self.assertEqual(args.academic_weeks, 8)
        self.assertEqual(args.reassessment_weeks, 2)
        self.assertEqual(args.delivery_location, "Perth")
        self.assertEqual(args.delivery_mode, "online")
        self.assertEqual(args.institution_name, "Test Institution")
        self.assertEqual(args.student_cohort, "Adult learners")
        self.assertEqual(args.config_file, "config.yaml")

    def test_config_command_short_options(self):
        """Test config command with short option names."""
        args = parser.parse_args(
            ["config", "-c", "my_config.yaml", "-t", "tafe", "-o", "/custom/output"]
        )
        self.assertEqual(args.create, "my_config.yaml")
        self.assertEqual(args.template, "tafe")
        self.assertEqual(args.output_dir, "/custom/output")

    def test_init_command_missing_required_args(self):
        """Test init command with missing required arguments."""
        with self.assertRaises(SystemExit):
            parser.parse_args(["init"])

    def test_init_command_invalid_course_type(self):
        """Test init command with invalid course type."""
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "init",
                    "--course-name",
                    "Test Course",
                    "--course-type",
                    "INVALID",
                ]
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
                    "invalid",
                ]
            )

    def test_config_command_invalid_template(self):
        """Test config command with invalid template."""
        with self.assertRaises(SystemExit):
            parser.parse_args(["config", "--template", "invalid"])

    def test_parser_no_command(self):
        """Test parser with no command specified."""
        args = parser.parse_args([])
        self.assertIsNone(args.command)

    def test_parser_unknown_command(self):
        """Test parser with unknown command."""
        with self.assertRaises(SystemExit):
            parser.parse_args(["unknown"])

    def test_init_defaults(self):
        """Test init command with default values."""
        args = parser.parse_args(
            ["init", "--course-name", "Test Course", "--target", "/tmp/test"]
        )

        # Test default values
        self.assertEqual(args.course_type, "TAFE")
        self.assertEqual(args.delivery_mode, "face-to-face")
        self.assertIsNone(args.num_weeks)
        self.assertIsNone(args.academic_weeks)
        self.assertIsNone(args.reassessment_weeks)
        self.assertIsNone(args.uoc_codes)
        self.assertIsNone(args.mission)
        self.assertFalse(args.no_llm)

    def test_init_boolean_flags(self):
        """Test boolean flags in init command."""
        # Test no-llm flag
        args_with_flag = parser.parse_args(
            ["init", "--course-name", "Test", "--no-llm"]
        )
        self.assertTrue(args_with_flag.no_llm)

        # Test without flag
        args_without_flag = parser.parse_args(["init", "--course-name", "Test"])
        self.assertFalse(args_without_flag.no_llm)

    def test_init_multiple_uoc_codes(self):
        """Test init command with multiple UOC codes."""
        args = parser.parse_args(
            [
                "init",
                "--course-name",
                "Test Course",
                "--uoc-codes",
                "ICTAII401",
                "ICTAII501",
                "ICTAII502",
                "BSBINS401",
            ]
        )
        expected_codes = ["ICTAII401", "ICTAII501", "ICTAII502", "BSBINS401"]
        self.assertEqual(args.uoc_codes, expected_codes)

    def test_init_single_uoc_code(self):
        """Test init command with single UOC code."""
        args = parser.parse_args(
            [
                "init",
                "--course-name",
                "Test Course",
                "--uoc-codes",
                "ICTAII401",
            ]
        )
        self.assertEqual(args.uoc_codes, ["ICTAII401"])

    def test_numeric_arguments_validation(self):
        """Test that numeric arguments are properly parsed."""
        args = parser.parse_args(
            [
                "init",
                "--course-name",
                "Test Course",
                "--num-weeks",
                "20",
                "--academic-weeks",
                "18",
                "--reassessment-weeks",
                "2",
            ]
        )

        # Check types
        self.assertIsInstance(args.num_weeks, int)
        self.assertIsInstance(args.academic_weeks, int)
        self.assertIsInstance(args.reassessment_weeks, int)

        # Check values
        self.assertEqual(args.num_weeks, 20)
        self.assertEqual(args.academic_weeks, 18)
        self.assertEqual(args.reassessment_weeks, 2)

    def test_delivery_mode_choices(self):
        """Test delivery mode choices validation."""
        valid_modes = ["face-to-face", "online", "hybrid"]

        for mode in valid_modes:
            args = parser.parse_args(
                [
                    "init",
                    "--course-name",
                    "Test Course",
                    "--delivery-mode",
                    mode,
                ]
            )
            self.assertEqual(args.delivery_mode, mode)

    def test_course_type_choices(self):
        """Test course type choices validation."""
        valid_types = ["TAFE", "COMMERCIAL", "ACCELERATED", "CUSTOM"]

        for course_type in valid_types:
            args = parser.parse_args(
                [
                    "init",
                    "--course-name",
                    "Test Course",
                    "--course-type",
                    course_type,
                ]
            )
            self.assertEqual(args.course_type, course_type)

    def test_template_choices(self):
        """Test template choices validation."""
        valid_templates = ["basic", "tafe", "commercial", "accelerated", "custom"]

        for template in valid_templates:
            args = parser.parse_args(["config", "--template", template])
            self.assertEqual(args.template, template)


if __name__ == "__main__":
    unittest.main()
