#!/usr/bin/env python3
"""
Unit tests for CourseConfig class functionality
"""

import sys
import os
import unittest

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.gptgen.config import CourseConfig


class TestCourseConfig(unittest.TestCase):
    """Unit tests for the CourseConfig class functionality."""

    def test_tafe_default_config(self):
        """Test TAFE course default configuration."""
        config = CourseConfig(course_type="TAFE")

        self.assertEqual(config.course_type, "TAFE")
        self.assertEqual(config.num_weeks, 20)
        self.assertEqual(config.academic_weeks, 18)
        self.assertEqual(config.reassessment_weeks, 2)
        self.assertTrue(config.has_reassessment_weeks)
        self.assertTrue(config.has_units_of_competency)
        self.assertTrue(config.is_accredited)

    def test_commercial_config(self):
        """Test commercial course configuration."""
        config = CourseConfig(course_type="COMMERCIAL", num_weeks=8)

        self.assertEqual(config.course_type, "COMMERCIAL")
        self.assertEqual(config.num_weeks, 8)
        self.assertEqual(config.academic_weeks, 8)
        self.assertEqual(config.reassessment_weeks, 0)
        self.assertFalse(config.has_reassessment_weeks)
        self.assertFalse(config.has_units_of_competency)
        self.assertFalse(config.is_accredited)

    def test_accelerated_config(self):
        """Test accelerated course configuration."""
        config = CourseConfig(course_type="ACCELERATED", num_weeks=10)

        self.assertEqual(config.course_type, "ACCELERATED")
        self.assertEqual(config.num_weeks, 10)
        self.assertEqual(config.academic_weeks, 10)
        self.assertEqual(config.reassessment_weeks, 0)
        self.assertFalse(config.has_reassessment_weeks)
        self.assertTrue(config.has_units_of_competency)
        self.assertTrue(config.is_accredited)

    def test_custom_config(self):
        """Test custom course configuration."""
        config = CourseConfig(
            course_type="CUSTOM",
            num_weeks=6,
            academic_weeks=5,
            reassessment_weeks=1,
            has_units_of_competency=False,
            is_accredited=False,
        )

        self.assertEqual(config.course_type, "CUSTOM")
        self.assertEqual(config.num_weeks, 6)
        self.assertEqual(config.academic_weeks, 5)
        self.assertEqual(config.reassessment_weeks, 1)
        self.assertTrue(config.has_reassessment_weeks)
        self.assertFalse(config.has_units_of_competency)
        self.assertFalse(config.is_accredited)

    def test_custom_config_defaults(self):
        """Test custom config with partial parameters."""
        # Test with only num_weeks and reassessment_weeks
        config = CourseConfig(course_type="CUSTOM", num_weeks=12, reassessment_weeks=2)

        self.assertEqual(config.num_weeks, 12)
        self.assertEqual(config.academic_weeks, 10)  # 12 - 2
        self.assertEqual(config.reassessment_weeks, 2)

        # Test with only num_weeks and academic_weeks
        config = CourseConfig(course_type="CUSTOM", num_weeks=15, academic_weeks=12)

        self.assertEqual(config.num_weeks, 15)
        self.assertEqual(config.academic_weeks, 12)
        self.assertEqual(config.reassessment_weeks, 3)  # 15 - 12

    def test_get_week_ranges_tafe(self):
        """Test week ranges for TAFE course."""
        config = CourseConfig(course_type="TAFE")
        ranges = config.get_week_ranges()

        self.assertEqual(ranges["academic"], list(range(1, 19)))
        self.assertEqual(ranges["reassessment"], [19, 20])
        self.assertEqual(ranges["wrap_up"], [19, 20])

    def test_get_week_ranges_commercial(self):
        """Test week ranges for commercial course."""
        config = CourseConfig(course_type="COMMERCIAL", num_weeks=8)
        ranges = config.get_week_ranges()

        self.assertEqual(ranges["academic"], list(range(1, 9)))
        self.assertEqual(ranges["reassessment"], [])
        self.assertEqual(ranges["wrap_up"], [8])

    def test_get_learning_phases_short_course(self):
        """Test learning phases for short course (4 weeks)."""
        config = CourseConfig(course_type="COMMERCIAL", num_weeks=4)
        phases = config.get_learning_phases()

        self.assertEqual(phases["foundation"], [1, 2, 3, 4])

    def test_get_learning_phases_medium_course(self):
        """Test learning phases for medium course (8 weeks)."""
        config = CourseConfig(course_type="COMMERCIAL", num_weeks=8)
        phases = config.get_learning_phases()

        self.assertEqual(phases["foundation"], [1, 2, 3, 4])
        self.assertEqual(phases["application"], [5, 6, 7, 8])

    def test_get_learning_phases_longer_course(self):
        """Test learning phases for longer course (12 weeks)."""
        config = CourseConfig(course_type="ACCELERATED", num_weeks=12)
        phases = config.get_learning_phases()

        self.assertEqual(phases["foundation"], [1, 2, 3, 4])
        self.assertEqual(phases["development"], [5, 6, 7, 8])
        self.assertEqual(phases["application"], [9, 10, 11, 12])

    def test_get_learning_phases_full_course(self):
        """Test learning phases for full course (20 weeks)."""
        config = CourseConfig(course_type="TAFE")
        phases = config.get_learning_phases()

        # For 18 weeks: fifth = 18 // 5 = 3
        # foundation: range(1, 2*3+1) = range(1, 7) = [1, 2, 3, 4, 5, 6]
        # development: range(2*3+1, 3*3+1) = range(7, 10) = [7, 8, 9]
        # application: range(3*3+1, 4*3+1) = range(10, 13) = [10, 11, 12]
        # advanced: range(4*3+1, 5*3+1) = range(13, 16) = [13, 14, 15]
        # synthesis: range(5*3+1, 18+1) = range(16, 19) = [16, 17, 18]
        self.assertEqual(phases["foundation"], [1, 2, 3, 4, 5, 6])
        self.assertEqual(phases["development"], [7, 8, 9])
        self.assertEqual(phases["application"], [10, 11, 12])
        self.assertEqual(phases["advanced"], [13, 14, 15])
        self.assertEqual(phases["synthesis"], [16, 17, 18])

    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        # Test 1-week course
        config = CourseConfig(course_type="COMMERCIAL", num_weeks=1)
        phases = config.get_learning_phases()
        self.assertEqual(phases["foundation"], [1])

        # Test 2-week course
        config = CourseConfig(course_type="COMMERCIAL", num_weeks=2)
        phases = config.get_learning_phases()
        self.assertEqual(phases["foundation"], [1, 2])

        # Test 3-week course
        config = CourseConfig(course_type="COMMERCIAL", num_weeks=3)
        phases = config.get_learning_phases()
        self.assertEqual(phases["foundation"], [1, 2, 3])

        # Test 4-week course (boundary)
        config = CourseConfig(course_type="COMMERCIAL", num_weeks=4)
        phases = config.get_learning_phases()
        self.assertEqual(phases["foundation"], [1, 2, 3, 4])

        # Test 5-week course (should be 2 phases)
        config = CourseConfig(course_type="COMMERCIAL", num_weeks=5)
        phases = config.get_learning_phases()
        self.assertEqual(phases["foundation"], [1, 2])
        self.assertEqual(phases["application"], [3, 4, 5])

    def test_invalid_course_type(self):
        """Test that invalid course type defaults to TAFE."""
        config = CourseConfig(course_type="INVALID")

        # Should default to TAFE settings
        self.assertEqual(config.course_type, "INVALID")  # Keeps the invalid type
        self.assertEqual(config.num_weeks, 20)  # But uses TAFE defaults
        self.assertEqual(config.academic_weeks, 18)
        self.assertEqual(config.reassessment_weeks, 2)


if __name__ == "__main__":
    unittest.main()
