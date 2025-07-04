#!/usr/bin/env python3
"""
Unit tests for learning materials generation methods.
Tests individual methods in isolation with mocked dependencies.
"""

import sys
import os
import json
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.gptgen.content_generator import GPTContentGenerator
from src.gptgen.config import CourseConfig


class TestLearningMaterialsUnit(unittest.TestCase):
    """Unit tests for learning materials generation methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.generator = GPTContentGenerator()
        self.sample_weekly_topics = [
            {
                "week": 1,
                "title": "Introduction to AI",
                "topics": ["AI basics", "Machine learning overview", "Applications"],
            },
        ]

    def test_fallback_learning_materials(self):
        """Test fallback learning materials generation."""
        result = self.generator._fallback_learning_materials(self.sample_weekly_topics)
        self.assertIn(1, result)
        self.assertIn("slides.md", result[1])
        self.assertIn("demo.md", result[1])


if __name__ == "__main__":
    unittest.main()
