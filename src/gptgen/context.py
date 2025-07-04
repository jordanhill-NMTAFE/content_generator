from typing import List, Dict, Any, Optional


class CourseContextBuilder:
    """Builds comprehensive context for GPT generation"""

    def __init__(
        self, config: Dict, units: List[Dict], mission_prompt: Optional[str] = None
    ):
        self.config = config
        self.units = units
        self.mission_prompt = mission_prompt

    def build_full_context(self) -> str:
        """Build complete context string for GPT prompts"""
        context_parts = []

        # Course configuration context
        course_config = self.config.get("course", {})
        context_parts.append(f"Course Type: {course_config.get('type', 'TAFE')}")
        context_parts.append(f"Total Weeks: {course_config.get('num_weeks', 20)}")
        context_parts.append(
            f"Academic Weeks: {course_config.get('academic_weeks', 18)}"
        )
        context_parts.append(
            f"Reassessment Weeks: {course_config.get('reassessment_weeks', 2)}"
        )

        # Institutional context
        institution = self.config.get("institution", {})
        if institution.get("name"):
            context_parts.append(f"Institution: {institution['name']}")
        if institution.get("delivery_location"):
            context_parts.append(
                f"Delivery Location: {institution['delivery_location']}"
            )
        if institution.get("delivery_mode"):
            context_parts.append(f"Delivery Mode: {institution['delivery_mode']}")

        # Student context
        students = self.config.get("students", {})
        if students.get("cohort"):
            context_parts.append(f"Student Cohort: {students['cohort']}")

        # Industry contextualization (TAFE-specific)
        industry_context = self.config.get("industry_context", {})
        if industry_context:
            context_parts.append("=== INDUSTRY CONTEXTUALIZATION ===")
            if industry_context.get("primary_industry"):
                context_parts.append(
                    f"Primary Industry: {industry_context['primary_industry']}"
                )
            if industry_context.get("industry_focus"):
                context_parts.append(
                    f"Industry Focus: {industry_context['industry_focus']}"
                )
            if industry_context.get("specific_tools"):
                tools = ", ".join(industry_context["specific_tools"])
                context_parts.append(f"Industry Tools: {tools}")
            if industry_context.get("industry_standards"):
                standards = ", ".join(industry_context["industry_standards"])
                context_parts.append(f"Industry Standards: {standards}")
            if industry_context.get("workplace_context"):
                context_parts.append(
                    f"Workplace Context: {industry_context['workplace_context']}"
                )
            if industry_context.get("industry_partners"):
                partners = ", ".join(industry_context["industry_partners"])
                context_parts.append(f"Industry Partners: {partners}")

        # Assessment criteria (TAFE-specific)
        assessment_criteria = self.config.get("assessment_criteria", {})
        if assessment_criteria:
            context_parts.append("=== ASSESSMENT CRITERIA ===")
            if assessment_criteria.get("competent_standard"):
                context_parts.append(
                    f"Competency Standard: {assessment_criteria['competent_standard']}"
                )
            if assessment_criteria.get("grading_system"):
                context_parts.append(
                    f"Grading System: {assessment_criteria['grading_system']}"
                )
            if assessment_criteria.get("minimum_requirements"):
                context_parts.append(
                    f"Minimum Requirements: {assessment_criteria['minimum_requirements']}"
                )
            if assessment_criteria.get("reassessment_policy"):
                context_parts.append(
                    f"Reassessment Policy: {assessment_criteria['reassessment_policy']}"
                )

        # Unit information
        if self.units:
            unit_info = "\n".join(
                [f"- {unit['id']}: {unit['name']}" for unit in self.units]
            )
            context_parts.append(f"Units of Competency:\n{unit_info}")

        # Mission prompt
        if self.mission_prompt:
            context_parts.append(f"Mission Context:\n{self.mission_prompt}")

        return "\n\n".join(context_parts)
