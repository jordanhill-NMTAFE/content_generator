"""
Validation utilities for course configuration and UOC codes.
"""

from typing import Dict, List

import logging

log = logging.getLogger(__name__)


class ConfigurationValidator:
    """Validates course configuration"""

    @staticmethod
    def validate_course_config(config: Dict) -> List[str]:
        """Validate course configuration and return list of errors"""
        errors = []

        course = config.get("course", {})

        # Validate course type
        valid_types = ["TAFE", "COMMERCIAL", "ACCELERATED", "CUSTOM"]
        if course.get("type") not in valid_types:
            errors.append(
                f"Invalid course type. Must be one of: {', '.join(valid_types)}"
            )

        # Validate weeks
        num_weeks = course.get("num_weeks")
        if num_weeks and (num_weeks < 1 or num_weeks > 52):
            errors.append("Number of weeks must be between 1 and 52")

        academic_weeks = course.get("academic_weeks")
        reassessment_weeks = course.get("reassessment_weeks")

        if academic_weeks and reassessment_weeks:
            if academic_weeks + reassessment_weeks != num_weeks:
                errors.append(
                    "Academic weeks + reassessment weeks must equal total weeks"
                )

        return errors

    @staticmethod
    def validate_uoc_codes(codes: List[str]) -> List[str]:
        """Validate UOC codes exist"""
        errors = []
        for code in codes:
            try:
                from src.utils.uoc_api import UnitOfCompetency

                UnitOfCompetency(code)
            except Exception:
                errors.append(f"Invalid or inaccessible UOC code: {code}")
        return errors

    @staticmethod
    def validate_assessment_structure(structure: Dict) -> List[str]:
        """Validate assessment structure configuration"""
        errors = []

        if not isinstance(structure, dict):
            errors.append("Assessment structure must be a dictionary")
            return errors

        assessments = structure.get("assessments", [])
        if not isinstance(assessments, list):
            errors.append("Assessments must be a list")
            return errors

        total_weight = 0
        for i, assessment in enumerate(assessments):
            if not isinstance(assessment, dict):
                errors.append(f"Assessment {i + 1} must be a dictionary")
                continue

            # Check required fields
            if "title" not in assessment:
                errors.append(f"Assessment {i + 1} missing title")
            if "weight" not in assessment:
                errors.append(f"Assessment {i + 1} missing weight")
            elif not isinstance(assessment["weight"], (int, float)):
                errors.append(f"Assessment {i + 1} weight must be a number")
            else:
                total_weight += assessment["weight"]

        # Check total weight
        if total_weight != 100:
            errors.append(f"Total assessment weight must be 100%, got {total_weight}%")

        return errors

    @staticmethod
    def validate_learning_phases(phases: Dict) -> List[str]:
        """Validate learning phases configuration"""
        errors = []

        if not isinstance(phases, dict):
            errors.append("Learning phases must be a dictionary")
            return errors

        valid_phases = [
            "foundation",
            "development",
            "application",
            "advanced",
            "synthesis",
        ]

        for phase_name, week_range in phases.items():
            if phase_name not in valid_phases:
                errors.append(f"Invalid phase name: {phase_name}")
                continue

            if not isinstance(week_range, list):
                errors.append(f"Phase {phase_name} must be a list of weeks")
                continue

            if len(week_range) != 2:
                errors.append(
                    f"Phase {phase_name} must have exactly 2 values [start, end]"
                )
                continue

            start, end = week_range
            if not isinstance(start, int) or not isinstance(end, int):
                errors.append(f"Phase {phase_name} week numbers must be integers")
                continue

            if start > end:
                errors.append(f"Phase {phase_name} start week must be <= end week")

        return errors
