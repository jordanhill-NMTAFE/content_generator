#!/usr/bin/env python3
"""
Unit tests for context awareness methods in GPT helper
"""

import sys
import os
import unittest

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.gptgen.content_generator import GPTContentGenerator


class TestContextAwareness(unittest.TestCase):
    """Unit tests for context awareness methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.generator = GPTContentGenerator()

    def test_build_course_context(self):
        """Test course context building method."""
        weekly_topics = [
            {
                "week": 1,
                "title": "Introduction to AI",
                "topics": ["AI basics", "Machine learning overview", "Applications"],
            },
            {
                "week": 2,
                "title": "Data Preparation",
                "topics": ["Data cleaning", "Feature engineering", "Data validation"],
            },
            {
                "week": 19,
                "title": "Reassessment Week",
                "topics": ["Review", "Catch-up", "Reassessment"],
            },
            {
                "week": 20,
                "title": "Course Wrap-up",
                "topics": ["Final submissions", "Reflection", "No-contact prep"],
            },
        ]

        mission_prompt = "Test mission for AI course"
        context = self.generator._build_course_context(weekly_topics, mission_prompt)

        # Assertions
        self.assertIn("Course Type: TAFE", context)
        self.assertIn("Total Weeks: 20", context)
        self.assertIn("Academic Weeks: 18", context)
        self.assertIn("Reassessment Weeks: 2", context)
        self.assertIn("Learning Phases:", context)
        self.assertIn(mission_prompt, context)
        self.assertIn("Week 1: Introduction to AI", context)
        self.assertIn("Week 19: Reassessment Week", context)
        self.assertIn("Week 20: Course Wrap-up", context)

    def test_build_previous_weeks_context_with_content(self):
        """Test previous weeks context building with existing content."""
        weekly_topics = [
            {
                "week": 1,
                "title": "Introduction to AI",
                "topics": ["AI basics", "Machine learning overview", "Applications"],
            },
            {
                "week": 2,
                "title": "Data Preparation",
                "topics": ["Data cleaning", "Feature engineering", "Data validation"],
            },
            {
                "week": 3,
                "title": "Model Development",
                "topics": ["Algorithm selection", "Training process", "Evaluation"],
            },
            {
                "week": 4,
                "title": "Current Week",
                "topics": ["Current topic 1", "Current topic 2"],
            },
        ]

        # Test for week 4 (should include weeks 1-3)
        context = self.generator._build_previous_weeks_context(weekly_topics, 4)

        # Assertions
        self.assertIn("PREVIOUS WEEKS CONTEXT:", context)
        self.assertIn("Week 1: Introduction to AI", context)
        self.assertIn("Week 2: Data Preparation", context)
        self.assertIn("Week 3: Model Development", context)
        # Check for bullet-pointed topics
        self.assertIn("  - AI basics", context)
        self.assertIn("  - Machine learning overview", context)
        self.assertIn("  - Applications", context)
        self.assertIn("  - Data cleaning", context)
        self.assertIn("  - Feature engineering", context)
        self.assertIn("  - Data validation", context)
        self.assertIn("  - Algorithm selection", context)
        self.assertIn("  - Training process", context)
        self.assertIn("  - Evaluation", context)

    def test_build_previous_weeks_context_empty(self):
        """Test previous weeks context building with no previous content."""
        context = self.generator._build_previous_weeks_context([], 1)
        # Should be empty string if no weekly topics or week 1
        self.assertEqual(context, "")

    def test_build_previous_weeks_context_many_weeks(self):
        """Test previous weeks context building with window parameter."""
        # Create 8 weeks of content
        weekly_topics = []

        for i in range(1, 9):
            weekly_topics.append(
                {
                    "week": i,
                    "title": f"Week {i} Title",
                    "topics": [f"Topic {i}.1", f"Topic {i}.2", f"Topic {i}.3"],
                }
            )

        # Test with default window (3) for week 8
        context = self.generator._build_previous_weeks_context(weekly_topics, 8)

        # Should include weeks 5, 6, 7 (window of 3)
        self.assertIn("Week 5: Week 5 Title", context)
        self.assertIn("Week 6: Week 6 Title", context)
        self.assertIn("Week 7: Week 7 Title", context)
        self.assertNotIn("Week 4: Week 4 Title", context)  # Outside window
        self.assertNotIn("Week 8: Week 8 Title", context)  # Current week

    def test_context_methods_integration(self):
        """Test that context methods work together properly."""
        weekly_topics = [
            {
                "week": 1,
                "title": "Introduction to AI",
                "topics": ["AI basics", "Machine learning overview", "Applications"],
            },
            {
                "week": 2,
                "title": "Data Preparation",
                "topics": ["Data cleaning", "Feature engineering", "Data validation"],
            },
        ]

        # Test both methods work together
        course_context = self.generator._build_course_context(
            weekly_topics, "Test mission"
        )
        previous_context = self.generator._build_previous_weeks_context(
            weekly_topics, 2
        )

        # Both should be valid strings
        self.assertIsInstance(course_context, str)
        self.assertIsInstance(previous_context, str)
        self.assertGreater(len(course_context), 0)
        self.assertGreater(len(previous_context), 0)

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
        self.assertIn("Learning Progression:", context)

    def test_build_learning_phases_context(self):
        """Test learning phases context building."""
        context = self.generator._build_learning_phases_context()

        self.assertIn("Learning Phases:", context)
        self.assertIn("Foundation", context)
        self.assertIn("Development", context)
        self.assertIn("Application", context)
        self.assertIn("Advanced", context)
        self.assertIn("Synthesis", context)

        # Check that phase descriptions are included
        self.assertIn("Establish core concepts and fundamental skills", context)
        self.assertIn("Build upon foundations with intermediate concepts", context)
        self.assertIn("Apply knowledge to practical scenarios", context)
        self.assertIn("Master complex concepts and advanced techniques", context)

    def test_build_industry_context(self):
        """Test industry context building for all valid input types."""
        # Case 1: No industry_context set (should return empty string)
        generator = self.generator  # default config, no industry_context
        context = generator._build_industry_context()
        self.assertTrue(context == "" or "INDUSTRY CONTEXTUALIZATION:" in context)

        # Case 2: industry_context as dict
        generator.course_config.industry_context = {
            "primary_industry": "Education",
            "industry_focus": "EdTech",
            "specific_tools": ["Moodle", "Zoom"],
            "industry_standards": ["SCORM", "LTI"],
            "workplace_context": "Online learning environments",
            "industry_partners": ["Universities", "Colleges"],
        }
        context = generator._build_industry_context()
        self.assertIn("INDUSTRY CONTEXTUALIZATION:", context)
        self.assertIn("Primary Industry: Education", context)
        self.assertIn("Industry Focus: EdTech", context)
        self.assertIn("Industry Tools: Moodle, Zoom", context)
        self.assertIn("Industry Standards: SCORM, LTI", context)
        self.assertIn("Workplace Context: Online learning environments", context)
        self.assertIn("Industry Partners: Universities, Colleges", context)

        # Case 3: industry_context as string
        generator.course_config.industry_context = "Custom industry context string."
        context = generator._build_industry_context()
        self.assertIn("INDUSTRY CONTEXTUALIZATION:", context)
        self.assertIn("Custom industry context string.", context)


if __name__ == "__main__":
    unittest.main()
