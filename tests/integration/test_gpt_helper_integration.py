#!/usr/bin/env python3
"""
Integration tests for GPT helper functionality including structured response system
"""

import sys
import os
import json
import unittest
from unittest.mock import Mock, patch

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.gptgen.content_generator import GPTContentGenerator
from src.gptgen.helpers import ResponseBox


class TestGPTHelperIntegration(unittest.TestCase):
    """Integration tests for the GPT helper with structured responses."""

    def setUp(self):
        """Set up test fixtures."""
        self.generator = GPTContentGenerator()
        self.sample_units = [
            {
                "id": "ICTAII401",
                "name": "Identify Opportunities for AI Task Automation",
            },
            {"id": "ICTAII501", "name": "Apply Machine Learning to Task Automation"},
            {"id": "ICTAII502", "name": "Implement AI Solutions for Task Automation"},
        ]

    def test_response_box_functionality(self):
        """Test ResponseBox wrap and extract functionality."""
        content = "Test content with multiple\nlines and special characters: !@#$%"

        # Test wrapping
        wrapped = ResponseBox.wrap(content, "TEST_BOX")
        self.assertIn("=== TEST_BOX START ===", wrapped)
        self.assertIn("=== TEST_BOX END ===", wrapped)
        self.assertIn(content, wrapped)

        # Test extraction
        extracted = ResponseBox.extract(wrapped, "TEST_BOX")
        self.assertEqual(extracted, content)

        # Test extraction from mixed content
        mixed = f"Preamble\n{wrapped}\nTrailing"
        extracted_mixed = ResponseBox.extract(mixed, "TEST_BOX")
        self.assertEqual(extracted_mixed, content)

        # Test extraction when box doesn't exist
        extracted_none = ResponseBox.extract("No box here", "MISSING")
        self.assertIsNone(extracted_none)

    @patch("src.gptgen.content_generator.Chat")
    def test_safe_prompt_with_retries_success(self, mock_chat):
        """Test successful prompt with retries."""
        # Mock successful response
        mock_client = Mock()
        mock_client.prompt.return_value = ResponseBox.wrap(
            "Success response", "RESPONSE"
        )
        self.generator.client = mock_client

        response, success = self.generator._safe_prompt_with_retries(
            "Test prompt", max_retries=3, response_type="RESPONSE", json_expected=False
        )

        self.assertTrue(success)
        self.assertEqual(response, "Success response")
        mock_client.prompt.assert_called_once()

    @patch("src.gptgen.content_generator.Chat")
    def test_safe_prompt_with_retries_json_validation(self, mock_chat):
        """Test JSON validation in safe prompt."""
        # Mock JSON response
        json_response = '[{"test": "data"}]'
        mock_client = Mock()
        mock_client.prompt.return_value = ResponseBox.wrap(
            json_response, "JSON_RESPONSE"
        )
        self.generator.client = mock_client

        response, success = self.generator._safe_prompt_with_retries(
            "Test prompt",
            max_retries=3,
            response_type="JSON_RESPONSE",
            json_expected=True,
        )

        self.assertTrue(success)
        # Verify it's valid JSON
        parsed = json.loads(response)
        self.assertEqual(parsed, [{"test": "data"}])

    @patch("src.gptgen.content_generator.Chat")
    def test_safe_prompt_with_retries_failure_then_success(self, mock_chat):
        """Test retry logic with initial failure then success."""
        mock_client = Mock()
        # First call fails, second succeeds
        mock_client.prompt.side_effect = [
            Exception("First failure"),
            ResponseBox.wrap("Success on retry", "RESPONSE"),
        ]
        self.generator.client = mock_client

        response, success = self.generator._safe_prompt_with_retries(
            "Test prompt", max_retries=3, response_type="RESPONSE", json_expected=False
        )

        self.assertTrue(success)
        self.assertEqual(response, "Success on retry")
        self.assertEqual(mock_client.prompt.call_count, 2)

    @patch("src.gptgen.content_generator.Chat")
    def test_safe_prompt_with_retries_all_failures(self, mock_chat):
        """Test when all retries fail and direct response is attempted."""
        mock_client = Mock()
        # All retries fail
        mock_client.prompt.side_effect = [
            Exception("Failure 1"),
            Exception("Failure 2"),
            Exception("Failure 3"),
            ResponseBox.wrap("Direct response success", "RESPONSE"),
        ]
        self.generator.client = mock_client

        response, success = self.generator._safe_prompt_with_retries(
            "Test prompt", max_retries=3, response_type="RESPONSE", json_expected=False
        )

        self.assertTrue(success)
        self.assertEqual(response, "Direct response success")
        self.assertEqual(mock_client.prompt.call_count, 4)  # 3 retries + 1 direct

    def test_fallback_methods(self):
        """Test fallback methods work correctly."""
        # Test fallback course overview
        overview = self.generator._fallback_course_overview(self.sample_units)
        self.assertIsInstance(overview, str)
        self.assertIn("comprehensive training", overview)

        # Test fallback weekly topics
        topics = self.generator._fallback_weekly_topics(self.sample_units, 20)
        self.assertIsInstance(topics, list)
        self.assertEqual(len(topics), 20)
        self.assertIn("week", topics[0])
        self.assertIn("title", topics[0])

        # Test fallback assessments
        assessments = self.generator._fallback_assessment_descriptions(
            self.sample_units
        )
        self.assertIsInstance(assessments, list)
        self.assertEqual(len(assessments), 4)
        self.assertIn("title", assessments[0])
        self.assertIn("description", assessments[0])

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

    def test_build_previous_weeks_context(self):
        """Test previous weeks context building."""
        weekly_topics = [
            {"week": 1, "title": "Week 1", "topics": ["Topic 1", "Topic 2"]},
            {"week": 2, "title": "Week 2", "topics": ["Topic 3", "Topic 4"]},
            {"week": 3, "title": "Week 3", "topics": ["Topic 5", "Topic 6"]},
        ]

        context = self.generator._build_previous_weeks_context(weekly_topics, 3)

        self.assertIn("PREVIOUS WEEKS CONTEXT:", context)
        self.assertIn("Week 1: Week 1", context)
        self.assertIn("Week 2: Week 2", context)
        self.assertNotIn(
            "Week 3: Week 3", context
        )  # Current week should not be included

    def test_build_course_structure_context(self):
        """Test course structure context building."""
        context = self.generator._build_course_structure_context()

        self.assertIn("Course Structure: 20-week TAFE course", context)
        self.assertIn("Academic Period: 18 weeks", context)
        self.assertIn("Reassessment Period: 2 weeks", context)
        self.assertIn(
            "Assessment Strategy: All assessments must be passed for competency",
            context,
        )

    def test_build_learning_phases_context(self):
        """Test learning phases context building."""
        context = self.generator._build_learning_phases_context()

        self.assertIn("Learning Phases:", context)
        self.assertIn("Foundation", context)
        self.assertIn("Development", context)
        self.assertIn("Application", context)
        self.assertIn("Advanced", context)
        self.assertIn("Synthesis", context)

    def test_build_industry_context(self):
        """Test industry context building."""
        # Set a sample industry_context
        self.generator.course_config.industry_context = {
            "primary_industry": "Information Technology",
            "industry_focus": "Software Development and Data Analytics",
            "specific_tools": ["Python", "SQL", "Power BI", "Azure"],
            "industry_standards": ["Agile methodologies", "DevOps practices"],
            "workplace_context": "Modern software development environments with cloud-based tools",
            "industry_partners": ["Local software companies", "Government departments"],
        }
        context = self.generator._build_industry_context()

        # Should include default industry context
        self.assertIn("INDUSTRY CONTEXTUALIZATION:", context)
        self.assertIn("Primary Industry: Information Technology", context)
        self.assertIn(
            "Industry Focus: Software Development and Data Analytics", context
        )
        self.assertIn("Industry Tools: Python, SQL, Power BI, Azure", context)
        self.assertIn(
            "Industry Standards: Agile methodologies, DevOps practices", context
        )

    def test_format_chain_of_thought_header(self):
        """Test chain of thought header formatting."""
        # Test with default steps
        header = self.generator._format_chain_of_thought_header()
        self.assertIn("CHAIN OF THOUGHT ANALYSIS:", header)
        self.assertIn("tafe course", header.lower())
        self.assertIn("20-week", header)

        # Test with custom steps
        custom_steps = ["Custom step 1", "Custom step 2"]
        custom_header = self.generator._format_chain_of_thought_header(custom_steps)
        self.assertIn("1. Custom step 1", custom_header)
        self.assertIn("2. Custom step 2", custom_header)

    def test_format_thought_answer_structure(self):
        """Test thought and answer structure formatting."""
        structure = self.generator._format_thought_answer_structure("TEST_TYPE")
        self.assertIn("<thought>", structure)
        self.assertIn("<answer>", structure)
        self.assertIn("TEST_TYPE", structure)

    def test_format_formatting_requirements(self):
        """Test formatting requirements formatting."""
        requirements = self.generator._format_formatting_requirements("test content")
        self.assertIn("CRITICAL FORMATTING REQUIREMENTS:", requirements)
        self.assertIn("test content", requirements)


if __name__ == "__main__":
    unittest.main()
