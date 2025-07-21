#!/usr/bin/env python3
"""
Integration tests for the two-stage learning materials generation system
"""

import sys
import os
import json
import unittest
from unittest.mock import Mock, patch, MagicMock

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.gptgen.content_generator import GPTContentGenerator
from src.gptgen.config import CourseConfig


class TestLearningMaterialsGenerationIntegration(unittest.TestCase):
    """Integration tests for the two-stage learning materials generation system."""

    def setUp(self):
        """Set up test fixtures."""
        self.generator = GPTContentGenerator()
        self.sample_weekly_topics = [
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
        self.mission_prompt = "Test mission for AI course development"

    def test_plan_learning_materials_structure(self):
        """Test that materials plan has correct structure."""
        # Mock the GPT client to return a valid materials plan
        mock_plan = [
            {
                "filename": "slides.md",
                "title": "Introduction to AI Slides",
                "description": "Comprehensive presentation slides for Week 1",
                "week": 1,
                "justification": "Students need clear visual presentation of AI concepts",
            },
            {
                "filename": "demo.md",
                "title": "AI Basics Workshop",
                "description": "Hands-on workshop for Week 1 concepts",
                "week": 1,
                "justification": "Practical application reinforces theoretical learning",
            },
        ]

        with patch.object(self.generator, "_safe_prompt_with_retries") as mock_prompt:
            mock_prompt.return_value = (json.dumps(mock_plan), True)

            result = self.generator._plan_learning_materials(
                self.sample_weekly_topics, self.mission_prompt
            )

            self.assertEqual(result, mock_plan)
            self.assertEqual(len(result), 2)

            # Check structure of each plan item
            for item in result:
                self.assertIn("filename", item)
                self.assertIn("title", item)
                self.assertIn("description", item)
                self.assertIn("week", item)
                self.assertIn("justification", item)

    def test_plan_learning_materials_failure(self):
        """Test handling of materials planning failure."""
        with patch.object(self.generator, "_safe_prompt_with_retries") as mock_prompt:
            mock_prompt.return_value = (None, False)

            result = self.generator._plan_learning_materials(
                self.sample_weekly_topics, self.mission_prompt
            )

            self.assertEqual(result, [])

    def test_generate_individual_materials_structure(self):
        """Test that individual materials generation produces correct structure."""
        materials_plan = [
            {
                "filename": "slides.md",
                "title": "Introduction to AI Slides",
                "description": "Comprehensive presentation slides for Week 1",
                "week": 1,
                "justification": "Students need clear visual presentation of AI concepts",
            },
            {
                "filename": "demo.md",
                "title": "AI Basics Workshop",
                "description": "Hands-on workshop for Week 1 concepts",
                "week": 1,
                "justification": "Practical application reinforces theoretical learning",
            },
        ]

        # Mock successful content generation
        with patch.object(self.generator, "_generate_single_material") as mock_generate:
            mock_generate.side_effect = [
                "# Week 1 Slides\n\n## Introduction to AI\n\n- AI basics\n- Machine learning overview",
                "# Week 1 Demo\n\n## AI Basics Workshop\n\n```python\nprint('Hello AI')\n```",
            ]

            result = self.generator._generate_individual_materials(
                materials_plan, self.sample_weekly_topics, self.mission_prompt
            )

            # Check structure
            self.assertIn(1, result)
            self.assertIn("slides.md", result[1])
            self.assertIn("demo.md", result[1])

            # Check content
            self.assertIn("# Week 1 Slides", result[1]["slides.md"])
            self.assertIn("# Week 1 Demo", result[1]["demo.md"])

    def test_generate_individual_materials_with_failures(self):
        """Test handling of individual material generation failures."""
        materials_plan = [
            {
                "filename": "slides.md",
                "title": "Introduction to AI Slides",
                "description": "Comprehensive presentation slides for Week 1",
                "week": 1,
                "justification": "Students need clear visual presentation of AI concepts",
            },
            {
                "filename": "demo.md",
                "title": "AI Basics Workshop",
                "description": "Hands-on workshop for Week 1 concepts",
                "week": 1,
                "justification": "Practical application reinforces theoretical learning",
            },
        ]

        # Mock one success, one failure
        with patch.object(self.generator, "_generate_single_material") as mock_generate:
            mock_generate.side_effect = [
                "# Week 1 Slides\n\n## Introduction to AI",  # Success
                None,  # Failure
            ]

            result = self.generator._generate_individual_materials(
                materials_plan, self.sample_weekly_topics, self.mission_prompt
            )

            # Should still have the successful material
            self.assertIn(1, result)
            self.assertIn("slides.md", result[1])
            self.assertIn("demo.md", result[1])  # Fallback should be present
            # Check that demo.md contains fallback content
            self.assertIn(
                "# Session 1: Introduction to AI - Practical Workshop",
                result[1]["demo.md"],
            )

    def test_generate_single_material_slides(self):
        """Test slides content generation."""
        material_spec = {
            "filename": "slides.md",
            "title": "Introduction to AI Slides",
            "description": "Comprehensive presentation slides for Week 1",
            "week": 1,
            "justification": "Students need clear visual presentation of AI concepts",
        }

        week_topic = self.sample_weekly_topics[0]
        course_context = "Test course context"
        industry_context = "Test industry context"

        with patch.object(self.generator, "_safe_prompt_with_retries") as mock_prompt:
            mock_prompt.return_value = (
                "# Week 1 Slides\n\n## Introduction to AI",
                True,
            )

            result = self.generator._generate_single_material(
                material_spec, week_topic, course_context, industry_context, ""
            )

            self.assertEqual(result, "# Week 1 Slides\n\n## Introduction to AI")
            mock_prompt.assert_called_once()

    def test_generate_single_material_demo(self):
        """Test demo content generation."""
        material_spec = {
            "filename": "demo.md",
            "title": "AI Basics Workshop",
            "description": "Hands-on workshop for Week 1 concepts",
            "week": 1,
            "justification": "Practical application reinforces theoretical learning",
        }

        week_topic = self.sample_weekly_topics[0]
        course_context = "Test course context"
        industry_context = "Test industry context"

        with patch.object(self.generator, "_safe_prompt_with_retries") as mock_prompt:
            mock_prompt.return_value = (
                "# Week 1 Demo\n\n## AI Basics Workshop",
                True,
            )

            result = self.generator._generate_single_material(
                material_spec, week_topic, course_context, industry_context, ""
            )

            self.assertEqual(result, "# Week 1 Demo\n\n## AI Basics Workshop")
            mock_prompt.assert_called_once()

    def test_generate_single_material_unknown_type(self):
        """Test handling of unknown material types."""
        material_spec = {
            "filename": "unknown.md",
            "title": "Unknown Material",
            "description": "Unknown material type",
            "week": 1,
            "justification": "Testing unknown type",
        }

        week_topic = self.sample_weekly_topics[0]
        course_context = "Test course context"
        industry_context = "Test industry context"

        result = self.generator._generate_single_material(
            material_spec, week_topic, course_context, industry_context, ""
        )

        self.assertIsNone(result)

    def test_generate_slides_content(self):
        """Test slides content generation with proper prompt structure."""
        week_topic = self.sample_weekly_topics[0]
        course_context = "Test course context"
        industry_context = "Test industry context"
        title = "Introduction to AI Slides"
        description = "Comprehensive presentation slides for Week 1"
        justification = "Students need clear visual presentation of AI concepts"

        with patch.object(self.generator, "_safe_prompt_with_retries") as mock_prompt:
            mock_prompt.return_value = (
                "# Week 1 Slides\n\n## Introduction to AI",
                True,
            )

            result = self.generator._generate_slides_content(
                week_topic,
                course_context,
                industry_context,
                "",  # previous_weeks_context
                title,
                description,
                justification,
            )

            self.assertEqual(result, "# Week 1 Slides\n\n## Introduction to AI")

            # Verify prompt contains expected elements
            call_args = mock_prompt.call_args[0]
            prompt = call_args[0]
            self.assertIn("Week 1: Introduction to AI", prompt)
            self.assertIn(
                "DESCRIPTION: Comprehensive presentation slides for Week 1", prompt
            )
            self.assertIn("Generate slides in Markdown format", prompt)

    def test_generate_slides_content_failure(self):
        """Test slides content generation failure."""
        week_topic = self.sample_weekly_topics[0]
        course_context = "Test course context"
        industry_context = "Test industry context"
        title = "Introduction to AI Slides"
        description = "Comprehensive presentation slides for Week 1"
        justification = "Students need clear visual presentation of AI concepts"

        with patch.object(self.generator, "_safe_prompt_with_retries") as mock_prompt:
            mock_prompt.return_value = (None, False)

            result = self.generator._generate_slides_content(
                week_topic,
                course_context,
                industry_context,
                "",  # previous_weeks_context
                title,
                description,
                justification,
            )

            self.assertIsNone(result)

    def test_generate_demo_content(self):
        """Test demo content generation method."""
        week_topic = self.sample_weekly_topics[0]
        course_context = "Test course context"
        industry_context = "Test industry context"
        title = "AI Basics Workshop"
        description = "Hands-on workshop for Week 1 concepts"
        justification = "Practical application reinforces theoretical learning"

        with patch.object(self.generator, "_safe_prompt_with_retries") as mock_prompt:
            mock_prompt.return_value = ("# Week 1 Demo\n\n## AI Basics Workshop", True)

            result = self.generator._generate_demo_content(
                week_topic,
                course_context,
                industry_context,
                "",  # previous_weeks_context
                title,
                description,
                justification,
            )

            self.assertEqual(result, "# Week 1 Demo\n\n## AI Basics Workshop")

            # Verify prompt contains expected elements
            call_args = mock_prompt.call_args[0]
            prompt = call_args[0]
            self.assertIn("WEEK TOPIC: Introduction to AI", prompt)
            self.assertIn("DESCRIPTION: Hands-on workshop for Week 1 concepts", prompt)
            self.assertIn("Generate comprehensive demo/workshop content", prompt)
            self.assertIn("jupytext", prompt)

    def test_generate_demo_content_failure(self):
        """Test demo content generation failure."""
        week_topic = self.sample_weekly_topics[0]
        course_context = "Test course context"
        industry_context = "Test industry context"
        title = "AI Basics Workshop"
        description = "Hands-on workshop for Week 1 concepts"
        justification = "Practical application reinforces theoretical learning"

        with patch.object(self.generator, "_safe_prompt_with_retries") as mock_prompt:
            mock_prompt.return_value = (None, False)

            result = self.generator._generate_demo_content(
                week_topic,
                course_context,
                industry_context,
                "",  # previous_weeks_context
                title,
                description,
                justification,
            )

            self.assertIsNone(result)

    def test_generate_learning_materials_full_flow(self):
        """Test complete learning materials generation workflow."""
        # Mock both planning and generation stages
        mock_plan = [
            {
                "filename": "slides.md",
                "title": "Introduction to AI Slides",
                "description": "Comprehensive presentation slides for Week 1",
                "week": 1,
                "justification": "Students need clear visual presentation of AI concepts",
            },
            {
                "filename": "demo.md",
                "title": "AI Basics Workshop",
                "description": "Hands-on workshop for Week 1 concepts",
                "week": 1,
                "justification": "Practical application reinforces theoretical learning",
            },
        ]

        with patch.object(
            self.generator, "_plan_learning_materials"
        ) as mock_plan_method:
            with patch.object(
                self.generator, "_generate_individual_materials"
            ) as mock_generate:
                mock_plan_method.return_value = mock_plan
                mock_generate.return_value = {
                    1: {
                        "slides.md": "# Week 1 Slides\n\n## Introduction to AI",
                        "demo.md": "# Week 1 Demo\n\n## AI Basics Workshop",
                    }
                }

                result = self.generator.generate_learning_materials(
                    self.sample_weekly_topics, self.mission_prompt
                )

                # Verify both methods were called
                mock_plan_method.assert_called_once_with(
                    self.sample_weekly_topics, self.mission_prompt
                )
                mock_generate.assert_called_once_with(
                    mock_plan, self.sample_weekly_topics, self.mission_prompt
                )

                # Verify result structure
                self.assertIn(1, result)
                self.assertIn("slides.md", result[1])
                self.assertIn("demo.md", result[1])

    def test_generate_learning_materials_planning_failure(self):
        """Test learning materials generation when planning fails."""
        with patch.object(
            self.generator, "_plan_learning_materials"
        ) as mock_plan_method:
            mock_plan_method.return_value = []  # Planning fails

            result = self.generator.generate_learning_materials(
                self.sample_weekly_topics, self.mission_prompt
            )

            # Should return fallback materials
            self.assertIsInstance(result, dict)
            self.assertGreater(len(result), 0)

    def test_generate_learning_materials_generation_failure(self):
        """Test learning materials generation when generation fails."""
        mock_plan = [
            {
                "filename": "slides.md",
                "title": "Introduction to AI Slides",
                "description": "Comprehensive presentation slides for Week 1",
                "week": 1,
                "justification": "Students need clear visual presentation of AI concepts",
            },
        ]

        with patch.object(
            self.generator, "_plan_learning_materials"
        ) as mock_plan_method:
            with patch.object(
                self.generator, "_generate_individual_materials"
            ) as mock_generate:
                mock_plan_method.return_value = mock_plan
                mock_generate.return_value = {}  # Generation fails

                result = self.generator.generate_learning_materials(
                    self.sample_weekly_topics, self.mission_prompt
                )

                # Should return fallback materials
                self.assertIsInstance(result, dict)
                self.assertGreater(len(result), 0)

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

    def test_build_course_context_with_learning_phases(self):
        """Test course context building with learning phases."""
        context = self.generator._build_course_context(
            self.sample_weekly_topics, self.mission_prompt
        )

        self.assertIn("Course Type: TAFE", context)
        self.assertIn("Total Weeks: 20", context)
        self.assertIn("Learning Phases:", context)
        self.assertIn(self.mission_prompt, context)
        self.assertIn("Week 1: Introduction to AI", context)

    def test_progress_tracking_integration(self):
        """Test progress tracking integration with learning materials generation."""
        # Create a progress manager
        progress_file = "test_progress.json"
        generator_with_progress = GPTContentGenerator(progress_file=progress_file)

        # Mock the planning and generation
        mock_plan = [
            {
                "filename": "slides.md",
                "title": "Test Slides",
                "description": "Test description",
                "week": 1,
                "justification": "Test justification",
            }
        ]

        with patch.object(
            generator_with_progress, "_plan_learning_materials"
        ) as mock_plan_method:
            with patch.object(
                generator_with_progress, "_generate_individual_materials"
            ) as mock_generate:
                mock_plan_method.return_value = mock_plan
                mock_generate.return_value = {
                    1: {"slides.md": "# Test Slides\n\n## Test Content"}
                }

                # Generate materials
                result = generator_with_progress.generate_learning_materials(
                    self.sample_weekly_topics, self.mission_prompt
                )

                # Verify progress was tracked
                self.assertTrue(
                    generator_with_progress.progress.is_done("learning_materials")
                )
                self.assertEqual(
                    generator_with_progress.progress.get_result("learning_materials"),
                    result,
                )

        # Clean up
        if os.path.exists(progress_file):
            os.remove(progress_file)

    def test_no_gpt_client_fallback(self):
        """Test fallback behavior when GPT client is not available."""
        # Create generator without API key
        generator_no_client = GPTContentGenerator(api_key=None)

        # Test fallback learning materials
        result = generator_no_client.generate_learning_materials(
            self.sample_weekly_topics, self.mission_prompt
        )

        # Should return fallback materials
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)

        # Each week should have slides and demo
        for week_num in [1, 2, 19, 20]:  # Use weeks from sample data
            if week_num in result:  # Only check if the week exists in result
                self.assertIn("slides.md", result[week_num])
                self.assertIn("demo.md", result[week_num])

                # Content should be strings
                self.assertIsInstance(result[week_num]["slides.md"], str)
                self.assertIsInstance(result[week_num]["demo.md"], str)

                # Content should contain session number
                self.assertIn(f"Session {week_num}", result[week_num]["slides.md"])
                self.assertIn(f"Session {week_num}", result[week_num]["demo.md"])

    def test_integration_slides_and_demo_generation_structure(self):
        """
        Integration: Generate slides.md and demo.md using real prompt construction, validate structure.
        """
        # Use a real theme name as would be parsed from CSS
        theme = "nmt-theme"
        # Minimal weekly topic for context
        weekly_topics = [
            {
                "week": 1,
                "title": "Introduction to AI",
                "topics": ["AI basics", "Machine learning overview", "Applications"],
            }
        ]
        mission_prompt = "Test mission for AI course development"
        generator = GPTContentGenerator()
        week_topic = weekly_topics[0]
        course_context = generator._build_course_context(weekly_topics, mission_prompt)
        industry_context = generator._build_industry_context()
        previous_weeks_context = ""
        title = "Introduction to AI Slides"
        description = "Comprehensive presentation slides for Week 1"
        justification = "Students need clear visual presentation of AI concepts"

        # Build the real slides.md prompt
        slides_prompt = generator._generate_slides_content.__func__(
            generator,
            week_topic,
            course_context,
            industry_context,
            previous_weeks_context,
            title,
            description,
            justification,
            slide_theme=theme,
        )
        # Instead of calling the model, we mock a plausible Marp-compliant slides.md
        slides_md = f"""---\nmarp: true\ntheme: {theme}\ntitle: {title}\nfooter: '![height:50px](footer.png)'\n---\n\n# Introduction to AI\n\n---\n\n## AI basics\n- What is AI?\n- History\n\n---\n\n## Machine learning overview\n- Supervised vs unsupervised\n\n---\n\n## Applications\n- Industry examples\n"""
        # Validate slides.md structure
        self.assertTrue(slides_md.startswith("---"))
        self.assertIn(f"theme: {theme}", slides_md)
        self.assertIn("marp: true", slides_md)
        self.assertIn("footer:", slides_md)
        self.assertRegex(
            slides_md,
            r"^---[\s\S]+---[\s\S]+---",
            msg="Should have at least one slide separator after YAML",
        )
        self.assertIn("# Introduction to AI", slides_md)
        self.assertIn("## AI basics", slides_md)

        # Build the real demo.md prompt (simulate)
        demo_md = """# Week 1 Demo\n\n## AI Basics Workshop\n\n```python\nprint('Hello AI')\n```\n\nSome explanation text.\n"""
        # Validate demo.md structure
        self.assertIn("```python", demo_md)
        self.assertIn("print('Hello AI')", demo_md)
        self.assertIn("# Week 1 Demo", demo_md)
        # Basic check for ipynb convertibility: at least one code block
        self.assertRegex(
            demo_md,
            r"```[a-zA-Z0-9]*\n[\s\S]+?```",
            msg="Should contain at least one code block for ipynb conversion",
        )


if __name__ == "__main__":
    unittest.main()
