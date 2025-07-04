#!/usr/bin/env python3
"""
Unit tests for GPT helper functions and methods.
Tests individual functions in isolation with mocked dependencies.
"""

import json
import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from src.gptgen.content_generator import GPTContentGenerator
from src.gptgen.config import CourseConfig
from src.gptgen.content_generator import create_gpt_generator
from src.gptgen.progress import InitProgressManager
from src.gptgen.locking import FileLock
from src.gptgen.context import CourseContextBuilder
from src.gptgen.helpers import ResponseBox


class TestResponseBox(unittest.TestCase):
    """Test ResponseBox utility functions."""

    def test_wrap_content(self):
        """Test wrapping content in response box."""
        content = "Test content with multiple\nlines and special characters: !@#$%"
        wrapped = ResponseBox.wrap(content, "TEST_BOX")

        self.assertIn("=== TEST_BOX START ===", wrapped)
        self.assertIn("=== TEST_BOX END ===", wrapped)
        self.assertIn(content, wrapped)

    def test_extract_content(self):
        """Test extracting content from response box."""
        content = "Test content"
        wrapped = ResponseBox.wrap(content, "TEST_BOX")
        extracted = ResponseBox.extract(wrapped, "TEST_BOX")

        self.assertEqual(extracted, content)

    def test_extract_from_mixed_content(self):
        """Test extraction from mixed content."""
        content = "Test content"
        wrapped = ResponseBox.wrap(content, "TEST_BOX")
        mixed = f"Preamble\n{wrapped}\nTrailing"
        extracted = ResponseBox.extract(mixed, "TEST_BOX")

        self.assertEqual(extracted, content)

    def test_extract_missing_box(self):
        """Test extraction when box doesn't exist."""
        extracted = ResponseBox.extract("No box here", "MISSING")
        self.assertIsNone(extracted)


class TestCourseConfig(unittest.TestCase):
    """Test CourseConfig class and its methods."""

    def test_tafe_default_config(self):
        """Test TAFE default configuration."""
        config = CourseConfig(course_type="TAFE")

        self.assertEqual(config.num_weeks, 20)
        self.assertEqual(config.academic_weeks, 18)
        self.assertEqual(config.reassessment_weeks, 2)
        self.assertTrue(config.has_reassessment_weeks)
        self.assertTrue(config.has_units_of_competency)
        self.assertTrue(config.is_accredited)

    def test_commercial_config(self):
        """Test commercial course configuration."""
        config = CourseConfig(course_type="COMMERCIAL", num_weeks=12)

        self.assertEqual(config.num_weeks, 12)
        self.assertEqual(config.academic_weeks, 12)
        self.assertEqual(config.reassessment_weeks, 0)
        self.assertFalse(config.has_reassessment_weeks)
        self.assertFalse(config.has_units_of_competency)
        self.assertFalse(config.is_accredited)

    def test_custom_config(self):
        """Test custom course configuration."""
        config = CourseConfig(
            course_type="CUSTOM", num_weeks=16, academic_weeks=14, reassessment_weeks=2
        )

        self.assertEqual(config.num_weeks, 16)
        self.assertEqual(config.academic_weeks, 14)
        self.assertEqual(config.reassessment_weeks, 2)

    def test_get_week_ranges(self):
        """Test week ranges calculation."""
        config = CourseConfig(course_type="TAFE")
        ranges = config.get_week_ranges()

        self.assertEqual(ranges["academic"], list(range(1, 19)))
        self.assertEqual(ranges["reassessment"], [19, 20])
        self.assertEqual(ranges["wrap_up"], [19, 20])

    def test_get_learning_phases(self):
        """Test learning phases calculation."""
        config = CourseConfig(course_type="TAFE")
        phases = config.get_learning_phases()

        self.assertIn("foundation", phases)
        self.assertIn("development", phases)
        self.assertIn("application", phases)
        self.assertIn("advanced", phases)
        self.assertIn("synthesis", phases)


class TestGPTContentGeneratorUnit(unittest.TestCase):
    """Unit tests for GPTContentGenerator methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.progress_file = os.path.join(self.temp_dir.name, "progress.json")
        self.generator = GPTContentGenerator(progress_file=self.progress_file)
        self.sample_units = [
            {
                "id": "ICTAII401",
                "name": "Identify Opportunities for AI Task Automation",
            },
            {"id": "ICTAII501", "name": "Apply Machine Learning to Task Automation"},
        ]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_initialization(self):
        """Test GPTContentGenerator initialization."""
        self.assertIsNotNone(self.generator.course_config)
        self.assertEqual(self.generator.course_config.course_type, "TAFE")
        self.assertEqual(self.generator.course_config.num_weeks, 20)

    def test_initialization_with_custom_config(self):
        """Test initialization with custom configuration."""
        custom_config = CourseConfig(course_type="COMMERCIAL", num_weeks=12)
        generator = GPTContentGenerator(course_config=custom_config)

        self.assertEqual(generator.course_config.course_type, "COMMERCIAL")
        self.assertEqual(generator.course_config.num_weeks, 12)

    def test_fallback_course_overview(self):
        """Test fallback course overview generation."""
        overview = self.generator._fallback_course_overview(self.sample_units)

        self.assertIsInstance(overview, str)
        self.assertIn("comprehensive training", overview)
        self.assertIn("ICTAII401", overview)
        self.assertIn("ICTAII501", overview)

    def test_fallback_weekly_topics(self):
        """Test fallback weekly topics generation."""
        topics = self.generator._fallback_weekly_topics(self.sample_units, 20)

        self.assertIsInstance(topics, list)
        self.assertEqual(len(topics), 20)

        # Check structure of first topic
        first_topic = topics[0]
        self.assertIn("week", first_topic)
        self.assertIn("title", first_topic)
        self.assertIn("topics", first_topic)
        self.assertIn("activity", first_topic)
        self.assertEqual(first_topic["week"], 1)

    def test_fallback_assessment_descriptions(self):
        """Test fallback assessment descriptions."""
        assessments = self.generator._fallback_assessment_descriptions(
            self.sample_units
        )

        # Should return 4 assessments
        self.assertEqual(len(assessments), 4)

        # Check structure of first assessment
        first_assessment = assessments[0]
        self.assertIn("title", first_assessment)
        self.assertIn("description", first_assessment)
        self.assertIn("assessment_number", first_assessment)
        self.assertIn("week_range", first_assessment)
        self.assertIn("assessment_type", first_assessment)
        self.assertIn("weighting", first_assessment)

    def test_build_course_context(self):
        """Test course context building."""
        weekly_topics = [
            {"week": 1, "title": "Introduction", "topics": ["Basics", "Overview"]},
            {"week": 2, "title": "Advanced", "topics": ["Complex", "Advanced"]},
        ]

        context = self.generator._build_course_context(weekly_topics, "Test mission")

        self.assertIn("Test mission", context)
        self.assertIn("Course Type: TAFE", context)
        self.assertIn("Week 1: Introduction", context)
        self.assertIn("Week 2: Advanced", context)

    def test_build_course_structure_context(self):
        """Test course structure context building."""
        context = self.generator._build_course_structure_context()

        self.assertIn("Course Structure: 20-week TAFE course", context)
        self.assertIn("Academic Period: 18 weeks", context)
        self.assertIn("Reassessment Period: 2 weeks", context)

    def test_build_learning_phases_context(self):
        """Test learning phases context building."""
        context = self.generator._build_learning_phases_context()

        self.assertIn("Learning Phases:", context)
        self.assertIn("Foundation", context)
        self.assertIn("Development", context)
        self.assertIn("Application", context)

    def test_build_industry_context_empty(self):
        """Test industry context building with no context."""
        context = self.generator._build_industry_context()
        self.assertEqual(context, "")

    def test_build_industry_context_string(self):
        """Test industry context building with string context."""
        self.generator.course_config.industry_context = "Test industry context"
        context = self.generator._build_industry_context()

        self.assertIn("INDUSTRY CONTEXTUALIZATION:", context)
        self.assertIn("Test industry context", context)

    def test_build_industry_context_dict(self):
        """Test industry context building with dictionary context."""
        self.generator.course_config.industry_context = {
            "primary_industry": "Technology",
            "industry_focus": "Software Development",
            "specific_tools": ["Python", "Git"],
            "industry_standards": ["Agile", "DevOps"],
        }
        context = self.generator._build_industry_context()

        self.assertIn("Primary Industry: Technology", context)
        self.assertIn("Industry Focus: Software Development", context)
        self.assertIn("Industry Tools: Python, Git", context)
        self.assertIn("Industry Standards: Agile, DevOps", context)

    def test_build_unit_context(self):
        """Test unit context building."""
        unit_info, unit_context = self.generator._build_unit_context(
            self.sample_units, "Test mission"
        )

        self.assertIn("ICTAII401", unit_info)
        self.assertIn("ICTAII501", unit_info)
        self.assertIn("Test mission", unit_context)

    def test_sanitize_activity_text(self):
        """Test activity text sanitization."""
        text_with_colons = "Activity: Complete the following tasks: 1. Read, 2. Write"
        sanitized = self.generator._sanitize_activity_text(text_with_colons)

        # Should replace colons with semicolons
        self.assertNotIn(": ", sanitized)
        self.assertIn("; ", sanitized)

    def test_sanitize_activity_text_empty(self):
        """Test sanitization of empty text."""
        sanitized = self.generator._sanitize_activity_text("")
        self.assertEqual(sanitized, "Activity description not available.")

    def test_format_chain_of_thought_header(self):
        """Test chain of thought header formatting."""
        header = self.generator._format_chain_of_thought_header()

        self.assertIn("CHAIN OF THOUGHT ANALYSIS:", header)
        self.assertIn("tafe course", header)
        self.assertIn("20-week duration", header)

    def test_format_chain_of_thought_header_custom_steps(self):
        """Test chain of thought header with custom steps."""
        custom_steps = [
            "First, analyze the requirements",
            "Second, consider the approach",
        ]
        header = self.generator._format_chain_of_thought_header(custom_steps)

        self.assertIn("1. First, analyze the requirements", header)
        self.assertIn("2. Second, consider the approach", header)

    def test_format_thought_answer_structure(self):
        """Test thought and answer structure formatting."""
        structure = self.generator._format_thought_answer_structure("TEST_RESPONSE")

        self.assertIn("TEST_RESPONSE", structure)
        self.assertIn("<thought>", structure)
        self.assertIn("<answer>", structure)

    def test_format_formatting_requirements(self):
        """Test formatting requirements formatting."""
        requirements = self.generator._format_formatting_requirements("test content")

        self.assertIn("test content", requirements)
        self.assertIn("CRITICAL FORMATTING REQUIREMENTS:", requirements)

    @patch("src.gptgen.content_generator.Chat")
    def test_safe_prompt_with_retries_success(self, mock_chat):
        """Test successful prompt with retries."""
        mock_client = Mock()
        mock_client.prompt.return_value = ResponseBox.wrap(
            "Success response", "RESPONSE"
        )
        self.generator.client = mock_client

        response, success = self.generator._safe_prompt_with_retries(
            "Test prompt", response_type="RESPONSE"
        )

        self.assertTrue(success)
        self.assertEqual(response, "Success response")

    @patch("src.gptgen.content_generator.Chat")
    def test_safe_prompt_with_retries_json_validation(self, mock_chat):
        """Test JSON validation in safe prompt."""
        json_response = '{"test": "data"}'
        mock_client = Mock()
        mock_client.prompt.return_value = ResponseBox.wrap(
            json_response, "JSON_RESPONSE"
        )
        self.generator.client = mock_client

        response, success = self.generator._safe_prompt_with_retries(
            "Test prompt", response_type="JSON_RESPONSE", json_expected=True
        )

        self.assertTrue(success)
        # Verify it's valid JSON
        parsed = json.loads(response)
        self.assertEqual(parsed, {"test": "data"})

    @patch("src.gptgen.content_generator.Chat")
    def test_safe_prompt_with_retries_failure_recovery(self, mock_chat):
        """Test retry logic with failure then success."""
        mock_client = Mock()
        mock_client.prompt.side_effect = [
            Exception("First failure"),
            ResponseBox.wrap("Success on retry", "RESPONSE"),
        ]
        self.generator.client = mock_client

        response, success = self.generator._safe_prompt_with_retries(
            "Test prompt", response_type="RESPONSE"
        )

        self.assertTrue(success)
        self.assertEqual(response, "Success on retry")
        self.assertEqual(mock_client.prompt.call_count, 2)


class TestCourseContextBuilder(unittest.TestCase):
    """Test CourseContextBuilder class."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            "course": {"type": "TAFE", "num_weeks": 20},
            "institution": {"name": "Test Institution"},
            "students": {"cohort": "Adult learners"},
        }
        self.units = [
            {"id": "ICTAII401", "name": "Test Unit 1"},
            {"id": "ICTAII501", "name": "Test Unit 2"},
        ]
        self.builder = CourseContextBuilder(self.config, self.units)

    def test_build_full_context(self):
        """Test building full context."""
        context = self.builder.build_full_context()

        self.assertIn("Course Type: TAFE", context)
        self.assertIn("Total Weeks: 20", context)
        self.assertIn("Institution: Test Institution", context)
        self.assertIn("Student Cohort: Adult learners", context)
        self.assertIn("ICTAII401: Test Unit 1", context)

    def test_build_full_context_with_mission(self):
        """Test building context with mission prompt."""
        builder = CourseContextBuilder(self.config, self.units, "Test mission")
        context = builder.build_full_context()

        self.assertIn("Mission Context:", context)
        self.assertIn("Test mission", context)


class TestCreateGPTGenerator(unittest.TestCase):
    """Test the create_gpt_generator factory function."""

    def test_create_default_generator(self):
        """Test creating generator with defaults."""
        generator = create_gpt_generator()

        self.assertIsInstance(generator, GPTContentGenerator)
        self.assertEqual(generator.course_config.course_type, "TAFE")

    def test_create_generator_with_custom_config(self):
        """Test creating generator with custom config."""
        config = CourseConfig(course_type="COMMERCIAL", num_weeks=12)
        generator = create_gpt_generator(course_config=config)

        self.assertEqual(generator.course_config.course_type, "COMMERCIAL")
        self.assertEqual(generator.course_config.num_weeks, 12)

    def test_create_generator_with_progress_file(self):
        """Test creating generator with progress file."""
        generator = create_gpt_generator(progress_file="test_progress.json")

        self.assertIsNotNone(generator.progress)


if __name__ == "__main__":
    unittest.main()
