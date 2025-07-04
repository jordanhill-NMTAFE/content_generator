#!/usr/bin/env python3
"""
Example script demonstrating flexible course generation with different course types.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gptgen.generator import GPTContentGenerator
from src.gptgen.config import CourseConfig


def demonstrate_tafe_course():
    """Demonstrate TAFE course generation (default)."""
    print("=" * 60)
    print("TAFE COURSE GENERATION (20 weeks, 18 academic + 2 reassessment)")
    print("=" * 60)

    config = CourseConfig(course_type="TAFE")
    generator = GPTContentGenerator(course_config=config)

    units = [
        {"id": "ICTAII401", "name": "Identify Opportunities for AI Task Automation"},
        {"id": "ICTAII501", "name": "Apply Machine Learning to Task Automation"},
        {"id": "ICTAII502", "name": "Implement AI Solutions for Task Automation"},
    ]

    print(f"Course Configuration:")
    print(f"  Type: {config.course_type}")
    print(f"  Total Weeks: {config.num_weeks}")
    print(f"  Academic Weeks: {config.academic_weeks}")
    print(f"  Reassessment Weeks: {config.reassessment_weeks}")
    print(f"  Has Units of Competency: {config.has_units_of_competency}")
    print(f"  Is Accredited: {config.is_accredited}")

    print(f"\nLearning Phases:")
    phases = config.get_learning_phases()
    for phase, weeks in phases.items():
        print(f"  {phase.title()}: Weeks {weeks[0]}-{weeks[-1]}")

    print(f"\nWeek Ranges:")
    ranges = config.get_week_ranges()
    for range_type, week_list in ranges.items():
        if week_list:
            print(f"  {range_type.title()}: Weeks {week_list[0]}-{week_list[-1]}")

    # Note: This would require API key to actually generate content
    print(f"\nNote: Set OPENAI_API_KEY environment variable to generate actual content")


def demonstrate_commercial_course():
    """Demonstrate commercial course generation (8 weeks, no units)."""
    print("\n" + "=" * 60)
    print("COMMERCIAL COURSE GENERATION (8 weeks, no units of competency)")
    print("=" * 60)

    config = CourseConfig(course_type="COMMERCIAL", num_weeks=8)
    generator = GPTContentGenerator(course_config=config)

    print(f"Course Configuration:")
    print(f"  Type: {config.course_type}")
    print(f"  Total Weeks: {config.num_weeks}")
    print(f"  Academic Weeks: {config.academic_weeks}")
    print(f"  Reassessment Weeks: {config.reassessment_weeks}")
    print(f"  Has Units of Competency: {config.has_units_of_competency}")
    print(f"  Is Accredited: {config.is_accredited}")

    print(f"\nLearning Phases:")
    phases = config.get_learning_phases()
    for phase, weeks in phases.items():
        print(f"  {phase.title()}: Weeks {weeks[0]}-{weeks[-1]}")

    print(f"\nWeek Ranges:")
    ranges = config.get_week_ranges()
    for range_type, week_list in ranges.items():
        if week_list:
            print(f"  {range_type.title()}: Weeks {week_list[0]}-{week_list[-1]}")


def demonstrate_accelerated_course():
    """Demonstrate accelerated course generation (10 weeks, with units)."""
    print("\n" + "=" * 60)
    print("ACCELERATED COURSE GENERATION (10 weeks, with units of competency)")
    print("=" * 60)

    config = CourseConfig(course_type="ACCELERATED", num_weeks=10)
    generator = GPTContentGenerator(course_config=config)

    units = [
        {"id": "ICTAII401", "name": "Identify Opportunities for AI Task Automation"},
        {"id": "ICTAII501", "name": "Apply Machine Learning to Task Automation"},
    ]

    print(f"Course Configuration:")
    print(f"  Type: {config.course_type}")
    print(f"  Total Weeks: {config.num_weeks}")
    print(f"  Academic Weeks: {config.academic_weeks}")
    print(f"  Reassessment Weeks: {config.reassessment_weeks}")
    print(f"  Has Units of Competency: {config.has_units_of_competency}")
    print(f"  Is Accredited: {config.is_accredited}")

    print(f"\nLearning Phases:")
    phases = config.get_learning_phases()
    for phase, weeks in phases.items():
        print(f"  {phase.title()}: Weeks {weeks[0]}-{weeks[-1]}")

    print(f"\nWeek Ranges:")
    ranges = config.get_week_ranges()
    for range_type, week_list in ranges.items():
        if week_list:
            print(f"  {range_type.title()}: Weeks {week_list[0]}-{week_list[-1]}")


def demonstrate_custom_course():
    """Demonstrate custom course generation (6 weeks, 5 academic + 1 wrap-up)."""
    print("\n" + "=" * 60)
    print("CUSTOM COURSE GENERATION (6 weeks, 5 academic + 1 wrap-up)")
    print("=" * 60)

    config = CourseConfig(
        course_type="CUSTOM",
        num_weeks=6,
        academic_weeks=5,
        reassessment_weeks=1,
        has_units_of_competency=False,
        is_accredited=False,
    )
    generator = GPTContentGenerator(course_config=config)

    print(f"Course Configuration:")
    print(f"  Type: {config.course_type}")
    print(f"  Total Weeks: {config.num_weeks}")
    print(f"  Academic Weeks: {config.academic_weeks}")
    print(f"  Reassessment Weeks: {config.reassessment_weeks}")
    print(f"  Has Units of Competency: {config.has_units_of_competency}")
    print(f"  Is Accredited: {config.is_accredited}")

    print(f"\nLearning Phases:")
    phases = config.get_learning_phases()
    for phase, weeks in phases.items():
        print(f"  {phase.title()}: Weeks {weeks[0]}-{weeks[-1]}")

    print(f"\nWeek Ranges:")
    ranges = config.get_week_ranges()
    for range_type, week_list in ranges.items():
        if week_list:
            print(f"  {range_type.title()}: Weeks {week_list[0]}-{week_list[-1]}")


def main():
    """Run all course type demonstrations."""
    print("Flexible Course Generation Examples")
    print("=" * 60)

    demonstrate_tafe_course()
    demonstrate_commercial_course()
    demonstrate_accelerated_course()
    demonstrate_custom_course()

    print("\n" + "=" * 60)
    print("USAGE EXAMPLES:")
    print("=" * 60)
    print("""
# TAFE Course (default)
config = CourseConfig(course_type="TAFE")
generator = GPTContentGenerator(course_config=config)

# Commercial Course (8 weeks, no units)
config = CourseConfig(course_type="COMMERCIAL", num_weeks=8)
generator = GPTContentGenerator(course_config=config)

# Accelerated Course (10 weeks, with units)
config = CourseConfig(course_type="ACCELERATED", num_weeks=10)
generator = GPTContentGenerator(course_config=config)

# Custom Course (6 weeks, 5 academic + 1 wrap-up)
config = CourseConfig(
    course_type="CUSTOM",
    num_weeks=6,
    academic_weeks=5,
    reassessment_weeks=1,
    has_units_of_competency=False,
    is_accredited=False
)
generator = GPTContentGenerator(course_config=config)

# Generate content
overview = generator.generate_course_overview(units, mission_prompt)
topics = generator.generate_weekly_topics(units, mission_prompt)
assessments = generator.generate_assessment_descriptions(units, mission_prompt)
activities = generator.generate_learning_activities(topics, mission_prompt)
resources = generator.generate_learning_resources(topics, mission_prompt)
""")


if __name__ == "__main__":
    main()
