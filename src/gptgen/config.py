from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class CourseConfig:
    """
    Configuration for course generation with flexible parameters.
    """

    num_weeks: int = 20
    course_type: str = "TAFE"  # TAFE, COMMERCIAL, ACCELERATED, CUSTOM
    has_reassessment_weeks: bool = True
    has_units_of_competency: bool = True
    is_accredited: bool = True
    academic_weeks: Optional[int] = None
    reassessment_weeks: Optional[int] = None

    # Session hours configuration
    session_hours: float = 4.5
    out_of_class_hours: float = 3.0

    # TAFE-specific fields
    industry_context: Optional[Dict[str, Any]] = None
    assessment_criteria: Optional[Dict[str, Any]] = None
    use_competency_grading: bool = True  # TAFE uses Competent/Not Competent
    require_all_assessments: bool = True  # TAFE requires all assessments to be passed

    def __post_init__(self):
        """Set default values based on course type."""
        if self.course_type == "TAFE":
            if not hasattr(self, "num_weeks") or self.num_weeks is None:
                self.num_weeks = 20
            self.has_reassessment_weeks = True
            self.has_units_of_competency = True
            self.is_accredited = True
            if self.academic_weeks is None:
                self.academic_weeks = 18
            if self.reassessment_weeks is None:
                self.reassessment_weeks = 2
        elif self.course_type == "COMMERCIAL":
            self.has_reassessment_weeks = False
            self.has_units_of_competency = False
            self.is_accredited = False
            self.academic_weeks = self.num_weeks
            self.reassessment_weeks = 0
        elif self.course_type == "ACCELERATED":
            self.has_reassessment_weeks = False
            self.has_units_of_competency = True
            self.is_accredited = True
            self.academic_weeks = self.num_weeks
            self.reassessment_weeks = 0
        elif self.course_type == "CUSTOM":
            # Use provided values, set defaults for None
            if self.academic_weeks is None:
                self.academic_weeks = self.num_weeks - (self.reassessment_weeks or 0)
            if self.reassessment_weeks is None:
                self.reassessment_weeks = self.num_weeks - self.academic_weeks
        else:
            # Default to TAFE settings for unknown course types
            if not hasattr(self, "num_weeks") or self.num_weeks is None:
                self.num_weeks = 20
            self.has_reassessment_weeks = True
            self.has_units_of_competency = True
            self.is_accredited = True
            if self.academic_weeks is None:
                self.academic_weeks = 18
            if self.reassessment_weeks is None:
                self.reassessment_weeks = 2

    @property
    def total_session_hours(self) -> int:
        """Calculate total session hours based on session_hours and num_weeks."""
        return int(self.session_hours * self.num_weeks)

    @property
    def total_out_of_class_hours(self) -> int:
        """Calculate total out-of-class hours based on out_of_class_hours and num_weeks."""
        return int(self.out_of_class_hours * self.num_weeks)

    @property
    def total_training(self) -> int:
        """Calculate total training hours as sum of session and out-of-class hours."""
        return self.total_session_hours + self.total_out_of_class_hours

    def get_week_ranges(self) -> Dict[str, List[int]]:
        """Get week ranges for different phases of the course."""
        ranges = {
            "academic": list(range(1, self.academic_weeks + 1)),
            "reassessment": [],
            "wrap_up": [],
        }

        if self.has_reassessment_weeks and self.reassessment_weeks > 0:
            reassessment_start = self.academic_weeks + 1
            ranges["reassessment"] = list(
                range(reassessment_start, reassessment_start + self.reassessment_weeks)
            )
            ranges["wrap_up"] = ranges["reassessment"]
        else:
            # For courses without reassessment, wrap-up is the last week
            ranges["wrap_up"] = [self.academic_weeks]

        return ranges

    def get_learning_phases(self) -> Dict[str, List[int]]:
        """Get learning phases based on course configuration."""
        academic_weeks = self.academic_weeks

        if academic_weeks <= 4:
            # Short course - single phase
            return {"foundation": list(range(1, academic_weeks + 1))}
        elif academic_weeks <= 8:
            # Medium course - two phases
            mid_point = academic_weeks // 2
            return {
                "foundation": list(range(1, mid_point + 1)),
                "application": list(range(mid_point + 1, academic_weeks + 1)),
            }
        elif academic_weeks <= 12:
            # Longer course - three phases
            third = academic_weeks // 3
            return {
                "foundation": list(range(1, third + 1)),
                "development": list(range(third + 1, 2 * third + 1)),
                "application": list(range(2 * third + 1, academic_weeks + 1)),
            }
        else:
            # Full course - five phases
            fifth = academic_weeks // 5
            return {
                "foundation": list(range(1, 2 * fifth + 1)),
                "development": list(range(2 * fifth + 1, 3 * fifth + 1)),
                "application": list(range(3 * fifth + 1, 4 * fifth + 1)),
                "advanced": list(range(4 * fifth + 1, 5 * fifth + 1)),
                "synthesis": list(range(5 * fifth + 1, academic_weeks + 1)),
            }
