"""
Assessment mapping validation utilities.

This module provides validation functions to ensure that assessment mapping values
are valid against the relevant Units of Competency (UOC) data.
"""

import logging
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path

from .uoc_api import UnitOfCompetency


class AssessmentMappingValidator:
    """
    Validates assessment mapping values against UOC data.
    """

    def __init__(self):
        self.validation_errors = []
        self.validation_warnings = []

    def validate_assessment_mapping(
        self, assessment_data: Dict[str, Any], units: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validate assessment mapping against UOC data.

        Args:
            assessment_data: Assessment data containing mapping information
            units: List of unit dictionaries with UOC data

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.validation_errors = []
        self.validation_warnings = []

        mapping = assessment_data.get("mapping", [])
        if not mapping:
            self.validation_errors.append("No mapping found in assessment data")
            return False, self.validation_errors, self.validation_warnings

        # Validate each mapping question
        for question_index, question in enumerate(mapping):
            self._validate_mapping_question(question, units, question_index + 1)

        # Check overall mapping quality
        self._validate_mapping_coverage(assessment_data, units)

        is_valid = len(self.validation_errors) == 0
        return is_valid, self.validation_errors, self.validation_warnings

    def _validate_mapping_question(
        self,
        question: Dict[str, Any],
        units: List[Dict[str, Any]],
        question_number: int,
    ):
        """Validate a single mapping question."""

        # Validate criteria mappings
        criteria_mappings = question.get("criteria", {})
        for unit_id, criteria_list in criteria_mappings.items():
            self._validate_criteria_mappings(
                unit_id, criteria_list, units, question_number
            )

        # Validate knowledge mappings
        knowledge_mappings = question.get("knowledge", {})
        for unit_id, knowledge_list in knowledge_mappings.items():
            self._validate_knowledge_mappings(
                unit_id, knowledge_list, units, question_number
            )

        # Validate skills mappings
        skills_mappings = question.get("skills", {})
        for unit_id, skills_list in skills_mappings.items():
            self._validate_skills_mappings(unit_id, skills_list, units, question_number)

        # Validate foundation skills mappings
        foundation_skills_mappings = question.get("foundation_skills", {})
        for unit_id, foundation_skills_list in foundation_skills_mappings.items():
            self._validate_foundation_skills_mappings(
                unit_id, foundation_skills_list, units, question_number
            )

    def _validate_criteria_mappings(
        self,
        unit_id: str,
        criteria_list: List[Any],
        units: List[Dict[str, Any]],
        question_number: int,
    ):
        """Validate criteria mappings for a specific unit."""

        # Find the unit data
        unit_data = None
        for unit in units:
            if unit["id"] == unit_id:
                unit_data = unit
                break

        if not unit_data:
            self.validation_errors.append(
                f"Question {question_number}: Unit {unit_id} not found in course units"
            )
            return

        # Get available criteria from UOC
        available_criteria = []
        if hasattr(unit_data["data"], "elements_and_criteria"):
            for element_criteria in unit_data["data"].elements_and_criteria.values():
                available_criteria.extend(list(element_criteria.keys()))

        # Validate each criteria mapping
        for criteria_value in criteria_list:
            if not self._is_valid_criteria_mapping(criteria_value, available_criteria):
                self.validation_errors.append(
                    f"Question {question_number}: Invalid criteria mapping '{criteria_value}' "
                    f"for unit {unit_id}. Available criteria: {available_criteria[:5]}..."
                )

    def _validate_knowledge_mappings(
        self,
        unit_id: str,
        knowledge_list: List[Any],
        units: List[Dict[str, Any]],
        question_number: int,
    ):
        """Validate knowledge mappings for a specific unit."""

        # Find the unit data
        unit_data = None
        for unit in units:
            if unit["id"] == unit_id:
                unit_data = unit
                break

        if not unit_data:
            self.validation_errors.append(
                f"Question {question_number}: Unit {unit_id} not found in course units"
            )
            return

        # Get available knowledge evidence from UOC
        available_knowledge = []
        if hasattr(unit_data["data"], "knowledge_evidence"):
            knowledge_blurb, KE = next(
                iter(unit_data["data"].knowledge_evidence.items())
            )
            if isinstance(KE, list):
                available_knowledge = [str(item) for item in KE]
            else:
                available_knowledge = list(KE.keys())

        # Validate each knowledge mapping
        for knowledge_value in knowledge_list:
            if not self._is_valid_knowledge_mapping(
                knowledge_value, available_knowledge
            ):
                self.validation_errors.append(
                    f"Question {question_number}: Invalid knowledge mapping '{knowledge_value}' "
                    f"for unit {unit_id}. Available knowledge: {available_knowledge[:5]}..."
                )

    def _validate_skills_mappings(
        self,
        unit_id: str,
        skills_list: List[Any],
        units: List[Dict[str, Any]],
        question_number: int,
    ):
        """Validate skills mappings for a specific unit."""

        # Find the unit data
        unit_data = None
        for unit in units:
            if unit["id"] == unit_id:
                unit_data = unit
                break

        if not unit_data:
            self.validation_errors.append(
                f"Question {question_number}: Unit {unit_id} not found in course units"
            )
            return

        # Get available performance skills from UOC
        available_skills = []
        if hasattr(unit_data["data"], "performance_skills"):
            available_skills = list(unit_data["data"].performance_skills.keys())

        # Validate each skills mapping
        for skills_value in skills_list:
            if not self._is_valid_skills_mapping(skills_value, available_skills):
                self.validation_errors.append(
                    f"Question {question_number}: Invalid skills mapping '{skills_value}' "
                    f"for unit {unit_id}. Available skills: {available_skills[:5]}..."
                )

    def _validate_foundation_skills_mappings(
        self,
        unit_id: str,
        foundation_skills_list: List[Any],
        units: List[Dict[str, Any]],
        question_number: int,
    ):
        """Validate foundation skills mappings for a specific unit."""

        # Find the unit data
        unit_data = None
        for unit in units:
            if unit["id"] == unit_id:
                unit_data = unit
                break

        if not unit_data:
            self.validation_errors.append(
                f"Question {question_number}: Unit {unit_id} not found in course units"
            )
            return

        # Get available foundation skills from UOC
        available_foundation_skills = []
        if hasattr(unit_data["data"], "foundation_skills"):
            available_foundation_skills = unit_data["data"].foundation_skills

        # Validate each foundation skills mapping
        for foundation_skills_value in foundation_skills_list:
            if not self._is_valid_foundation_skills_mapping(
                foundation_skills_value, available_foundation_skills
            ):
                self.validation_errors.append(
                    f"Question {question_number}: Invalid foundation skills mapping '{foundation_skills_value}' "
                    f"for unit {unit_id}. Available foundation skills: {available_foundation_skills[:5]}..."
                )

    def _is_valid_criteria_mapping(
        self, criteria_value: Any, available_criteria: List[str]
    ) -> bool:
        """Check if a criteria mapping is valid."""
        if isinstance(criteria_value, int):
            return 1 <= criteria_value <= len(available_criteria)

        if isinstance(criteria_value, str):
            # Use the same matching logic as the mapping matrix
            return self._match_criteria_enhanced(criteria_value, available_criteria)

        return False

    def _is_valid_knowledge_mapping(
        self, knowledge_value: Any, available_knowledge: List[str]
    ) -> bool:
        """Check if a knowledge mapping is valid."""
        if isinstance(knowledge_value, int):
            return 1 <= knowledge_value <= len(available_knowledge)

        if isinstance(knowledge_value, str):
            return self._match_knowledge_enhanced(knowledge_value, available_knowledge)

        return False

    def _is_valid_skills_mapping(
        self, skills_value: Any, available_skills: List[str]
    ) -> bool:
        """Check if a skills mapping is valid."""
        if isinstance(skills_value, int):
            return 1 <= skills_value <= len(available_skills)

        if isinstance(skills_value, str):
            return self._match_skills_enhanced(skills_value, available_skills)

        return False

    def _is_valid_foundation_skills_mapping(
        self, foundation_skills_value: Any, available_foundation_skills: List[str]
    ) -> bool:
        """Check if a foundation skills mapping is valid."""
        if isinstance(foundation_skills_value, int):
            return 1 <= foundation_skills_value <= len(available_foundation_skills)

        if isinstance(foundation_skills_value, str):
            return self._match_foundation_skills_enhanced(
                foundation_skills_value, available_foundation_skills
            )

        return False

    def _match_criteria_enhanced(
        self, criteria_value: str, available_criteria: List[str]
    ) -> bool:
        """Enhanced criteria matching using the same logic as the mapping matrix."""
        import re

        def normalize(s):
            return s.strip().lower() if isinstance(s, str) else s

        def extract_criteria_number(criteria_text):
            if not isinstance(criteria_text, str):
                return criteria_text

            match = re.match(r"^(\d+\.\d+)", criteria_text.strip())
            if match:
                return match.group(1)
            return criteria_text

        criteria_normalized = normalize(criteria_value)

        for available_criterion in available_criteria:
            available_normalized = normalize(available_criterion)

            # Direct match
            if criteria_normalized == available_normalized:
                return True

            # Number-based matching
            criteria_number = extract_criteria_number(criteria_value)
            available_number = extract_criteria_number(available_criterion)

            if criteria_number == available_number:
                return True

            # Fuzzy matching
            if (
                criteria_normalized in available_normalized
                or available_normalized in criteria_normalized
            ):
                return True

            # Word-based matching
            criteria_words = set(criteria_normalized.split())
            available_words = set(available_normalized.split())

            if len(criteria_words) > 0:
                common_words = criteria_words.intersection(available_words)
                match_ratio = len(common_words) / len(criteria_words)
                if match_ratio >= 0.5:
                    return True

        return False

    def _match_knowledge_enhanced(
        self, knowledge_value: str, available_knowledge: List[str]
    ) -> bool:
        """Enhanced knowledge matching."""

        def normalize(s):
            return s.strip().lower() if isinstance(s, str) else s

        knowledge_normalized = normalize(knowledge_value)

        for available_k in available_knowledge:
            available_normalized = normalize(available_k)

            if knowledge_normalized == available_normalized:
                return True

            if (
                knowledge_normalized in available_normalized
                or available_normalized in knowledge_normalized
            ):
                return True

        return False

    def _match_skills_enhanced(
        self, skills_value: str, available_skills: List[str]
    ) -> bool:
        """Enhanced skills matching."""

        def normalize(s):
            return s.strip().lower() if isinstance(s, str) else s

        skills_normalized = normalize(skills_value)

        for available_skill in available_skills:
            available_normalized = normalize(available_skill)

            if skills_normalized == available_normalized:
                return True

            if (
                skills_normalized in available_normalized
                or available_normalized in skills_normalized
            ):
                return True

        return False

    def _match_foundation_skills_enhanced(
        self, foundation_skills_value: str, available_foundation_skills: List[str]
    ) -> bool:
        """Enhanced foundation skills matching."""

        def normalize(s):
            return s.strip().lower() if isinstance(s, str) else s

        foundation_skills_normalized = normalize(foundation_skills_value)

        for available_fs in available_foundation_skills:
            available_normalized = normalize(available_fs)

            if foundation_skills_normalized == available_normalized:
                return True

            if (
                foundation_skills_normalized in available_normalized
                or available_normalized in foundation_skills_normalized
            ):
                return True

        return False

    def _validate_mapping_coverage(
        self, assessment_data: Dict[str, Any], units: List[Dict[str, Any]]
    ):
        """Validate overall mapping coverage."""
        mapping = assessment_data.get("mapping", [])

        # Check if we have any mappings at all
        has_criteria = False
        has_knowledge = False
        has_skills = False

        for question in mapping:
            if question.get("criteria"):
                has_criteria = True
            if question.get("knowledge"):
                has_knowledge = True
            if question.get("skills"):
                has_skills = True

        if not has_criteria:
            self.validation_warnings.append(
                "No criteria mappings found - assessment may not cover competency requirements"
            )

        if not has_knowledge:
            self.validation_warnings.append(
                "No knowledge mappings found - assessment may not cover knowledge requirements"
            )

        if not has_skills:
            self.validation_warnings.append(
                "No skills mappings found - assessment may not cover performance requirements"
            )


def validate_assessment_file(
    assessment_path: Path, units: List[Dict[str, Any]]
) -> Tuple[bool, List[str], List[str]]:
    """
    Validate an assessment file against UOC data.

    Args:
        assessment_path: Path to the assessment file
        units: List of unit dictionaries with UOC data

    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    from .markdown import parse_md

    try:
        assessment_data = parse_md(assessment_path)
        validator = AssessmentMappingValidator()
        return validator.validate_assessment_mapping(assessment_data, units)
    except Exception as e:
        return False, [f"Error parsing assessment file: {e}"], []


def validate_assessment_directory(
    assessment_dir: Path, units: List[Dict[str, Any]]
) -> Dict[str, Tuple[bool, List[str], List[str]]]:
    """
    Validate all assessment files in a directory.

    Args:
        assessment_dir: Path to the assessment directory
        units: List of unit dictionaries with UOC data

    Returns:
        Dictionary mapping assessment names to (is_valid, errors, warnings)
    """
    results = {}

    for assessment_file in assessment_dir.rglob("assessment.md"):
        try:
            is_valid, errors, warnings = validate_assessment_file(
                assessment_file, units
            )
            assessment_name = assessment_file.parent.name
            results[assessment_name] = (is_valid, errors, warnings)
        except Exception as e:
            assessment_name = assessment_file.parent.name
            results[assessment_name] = (
                False,
                [f"Error processing assessment: {e}"],
                [],
            )

    return results
