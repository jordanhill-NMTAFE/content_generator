from pathlib import Path
import argparse
from requests import RequestException
from src.content_generator.lap import lap
from src.content_generator.assessment_tools import assess_tool
from src.content_generator.init import init_course
from os import environ as env

from src.content_generator.mapping_matrix import mapping_matrix
from src.utils.logger import log
import click
import os

assert "COURSE_CONTENT" in env, "COURSE_CONTENT is undefined"
assert "OUTPUT_LOCATION" in env, "OUTPUT_LOCATION is undefined"


parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(dest="command", help="Available commands")

# Init command
init_parser = subparsers.add_parser(
    "init", help="Initialize a new course content folder"
)

init_parser.add_argument(
    "--course-name",
    "-c",
    type=str,
    required=True,
    help="Name of the course (will create a folder in the current directory)",
)

init_parser.add_argument(
    "--target",
    "-t",
    type=str,
    required=False,
    help="Path to an empty folder to initialize the course content folder in",
)

init_parser.add_argument(
    "--uoc-codes",
    "-u",
    type=str,
    nargs="+",
    required=False,
    help="Unit of Competency codes to fetch and use for course initialization (e.g., ICTAII401 ICTAII501)",
)

init_parser.add_argument(
    "--mission",
    "-m",
    type=str,
    required=False,
    help="Guiding prompt describing course context, delivery environment, and core goals. Use '<<' to start multi-line input.",
)

init_parser.add_argument(
    "--no-llm",
    action="store_true",
    help="Disable LLM/GPT content generation and use template content only",
)

# Course configuration arguments
init_parser.add_argument(
    "--course-type",
    "-ct",
    type=str,
    choices=["TAFE", "COMMERCIAL", "ACCELERATED", "CUSTOM"],
    default="TAFE",
    help="Type of course to generate",
)

init_parser.add_argument(
    "--num-weeks", "-w", type=int, help="Total number of weeks for the course"
)

init_parser.add_argument(
    "--academic-weeks",
    "-aw",
    type=int,
    help="Number of academic weeks (defaults based on course type)",
)

init_parser.add_argument(
    "--reassessment-weeks",
    "-rw",
    type=int,
    help="Number of reassessment weeks (defaults based on course type)",
)

# Institutional context arguments
init_parser.add_argument(
    "--delivery-location",
    "-l",
    type=str,
    help="Primary delivery location (campus, city, etc.)",
)

init_parser.add_argument(
    "--delivery-mode",
    "-dm",
    type=str,
    choices=["face-to-face", "online", "hybrid"],
    default="face-to-face",
    help="Primary delivery mode",
)

init_parser.add_argument(
    "--institution-name", "-in", type=str, help="Institution name for course materials"
)

init_parser.add_argument(
    "--student-cohort", "-sc", type=str, help="Target student cohort description"
)

# Configuration file support
init_parser.add_argument(
    "--config-file", "-cf", type=str, help="Path to JSON/YAML configuration file"
)

# Generate command (for the existing functionality)
generate_parser = subparsers.add_parser(
    "push",
    help="Push key academic documents to the generated content folder for archive in content collection.",
)
generate_parser.add_argument(
    "--target",
    "-t",
    type=str,
    required=False,
    help="Path to the course content folder to process (default: current directory)",
)

# Config command for creating configuration files
config_parser = subparsers.add_parser(
    "config", help="Create and manage course configuration files"
)

config_parser.add_argument(
    "--create",
    "-c",
    type=str,
    help="Create a new configuration file with the specified name (default: course_config.yaml)",
)

config_parser.add_argument(
    "--template",
    "-t",
    type=str,
    choices=["basic", "tafe", "commercial", "accelerated", "custom"],
    default="basic",
    help="Template type for the configuration file",
)

config_parser.add_argument(
    "--output-dir",
    "-o",
    type=str,
    default=".",
    help="Output directory for the configuration file (default: current directory)",
)


# Convert command for converting markdown files to notebooks
convert_parser = subparsers.add_parser(
    "convert",
    help="Convert markdown files to Jupyter notebooks (or vice versa) using jupytext",
)

convert_parser.add_argument(
    "course_directory", type=str, help="Path to the course content folder"
)

convert_parser.add_argument(
    "--pattern", default="demo.md", help="File pattern to convert (default: demo.md)"
)

convert_parser.add_argument(
    "--reverse", action="store_true", help="Convert notebooks to markdown instead"
)

# New theme argument
init_parser.add_argument(
    "--theme",
    "-th",
    type=str,
    default="northmetro.css",
    help="Path or filename of the Marp CSS theme file to use for slides.md. The theme name will be parsed from the @theme declaration in this file.",
)


def init(args):
    """Initialize a new course content folder"""
    print(f"Initializing new course: {args.course_name}")

    target_path = None
    if args.target:
        target_path = Path(args.target)
        if not target_path.exists():
            print(f"Target path {target_path} does not exist. Creating...")
            target_path.mkdir(parents=True, exist_ok=True)

    # Handle mission prompt input
    mission_prompt = args.mission
    if mission_prompt and mission_prompt.startswith("<<"):
        print("Enter your mission prompt (end with '<<' on a new line):")
        lines = []
        while True:
            try:
                line = input()
                if line.strip() == "<<":
                    break
                lines.append(line)
            except EOFError:
                break
        mission_prompt = "\n".join(lines)

    try:
        # Build keyword arguments for *init_course* in the exact order the
        # test-suite asserts against.  We conditionally add *theme_css_path*
        # only when the user explicitly overrides the default.
        extra_kwargs = {}
        if getattr(args, "theme", None) not in (None, "northmetro.css"):
            extra_kwargs["theme_css_path"] = args.theme

        course_path = init_course(
            args.course_name,
            target_path,
            args.uoc_codes,
            mission_prompt,
            args.no_llm,
            course_type=args.course_type,
            num_weeks=args.num_weeks,
            academic_weeks=args.academic_weeks,
            reassessment_weeks=args.reassessment_weeks,
            delivery_location=args.delivery_location,
            delivery_mode=args.delivery_mode,
            institution_name=args.institution_name,
            student_cohort=args.student_cohort,
            config_file=args.config_file,
            **extra_kwargs,
        )
        print(f"Course '{args.course_name}' initialized successfully!")
        print(f"Course location: {course_path}")

        # Enhanced feedback
        if args.config_file:
            print(f"✓ Configuration loaded from: {args.config_file}")
        if args.course_type != "TAFE":
            print(f"✓ Course type: {args.course_type}")
        if args.num_weeks and args.num_weeks != 20:
            print(f"✓ Course duration: {args.num_weeks} weeks")
        if args.delivery_mode != "face-to-face":
            print(f"✓ Delivery mode: {args.delivery_mode}")

        if args.no_llm:
            print("✓ Course initialized with template content only (LLM disabled)")
        elif args.uoc_codes:
            print(f"UOC codes used: {', '.join(args.uoc_codes)}")
            print("✓ Course content generated using UOC data and language models")
        if mission_prompt and not args.no_llm:
            print("✓ Course guided by mission prompt")
        if not args.uoc_codes and not mission_prompt and not args.no_llm:
            print("✓ Course initialized with template content")

        print("\nNext steps:")
        print("1. Review and update course information in 2 KAD/1 LAP/fields.md")
        print("2. Customize assessment tools in 2 KAD/5 Assess Tool/")
        print("3. Add learning materials to 1 Learning Materials/")
        print(
            "4. Run 'python -m src.main generate --target <course_path>' to generate documents"
        )
    except Exception as e:
        print(f"Failed to initialize course: {e}")
        return 1

    return 0


def generate_lap():
    lap(COURSE_CONTENT, OUTPUT_LOCATION)


def generate_assessments():
    assess_tool(COURSE_CONTENT, OUTPUT_LOCATION)


def generate_matrix():
    mapping_matrix(COURSE_CONTENT, OUTPUT_LOCATION)


def push(args):
    """Generate all content (push)"""
    # Resolve paths - use current directory if no target specified
    if args.target:
        content_path = Path(args.target).resolve()
    else:
        content_path = Path.cwd().resolve()
        print(f"📁 No target specified, using current directory: {content_path}")

    if not content_path.exists():
        print(f"❌ Error: Content path {content_path} does not exist")
        print("💡 Please ensure the course directory exists before running push")
        return 1

    # Set up environment variables for production use
    global COURSE_CONTENT, OUTPUT_LOCATION

    if "COURSE_CONTENT" in env and "OUTPUT_LOCATION" in env:
        # Check if production directories are accessible
        prod_course_content = Path(env["COURSE_CONTENT"]).resolve() / content_path.name
        prod_output_location = (
            Path(env["OUTPUT_LOCATION"]).resolve() / content_path.name
        )

        # Check if production directories are accessible
        if prod_course_content.exists() and prod_output_location.parent.exists():
            # Production mode: use environment variables
            COURSE_CONTENT = prod_course_content
            OUTPUT_LOCATION = prod_output_location
            print(f"Production mode: Using environment variables")
        else:
            # Fall back to testing mode if production directories aren't accessible
            COURSE_CONTENT = content_path
            OUTPUT_LOCATION = Path.cwd() / f"output_{content_path.name}"
            print(
                f"Testing mode: Production directories not accessible, using local output"
            )
    else:
        # Testing mode: create output in current directory
        COURSE_CONTENT = content_path

        # Check if we're in a test environment (running pytest or similar)
        import sys

        is_test_environment = (
            any("pytest" in arg or "test" in arg.lower() for arg in sys.argv)
            or "PYTEST_CURRENT_TEST" in os.environ
        )

        if is_test_environment:
            # Use a dedicated test output directory
            test_output_dir = Path.cwd() / "test_outputs"
            test_output_dir.mkdir(exist_ok=True)
            OUTPUT_LOCATION = test_output_dir / f"output_{content_path.name}"
            print(f"Test mode: Creating output in test_outputs directory")
        else:
            # Normal testing mode: create output in current directory
            OUTPUT_LOCATION = Path.cwd() / f"output_{content_path.name}"
            print(f"Testing mode: Creating output in current directory")

    print(f"COURSE_CONTENT: {COURSE_CONTENT}")
    print(f"OUTPUT_LOCATION: {OUTPUT_LOCATION}")

    # Ensure output directory exists
    OUTPUT_LOCATION.mkdir(parents=True, exist_ok=True)

    # Call the functions using the global variables (as expected by the functions)
    generate_lap()
    generate_assessments()
    generate_matrix()


def create_config(args):
    """Create a new configuration file"""
    # Use sensible defaults if no arguments provided
    if not args.create:
        # Generate a default filename based on current directory or course name
        default_name = "course_config.yaml"
        print(f"📝 No configuration file name specified. Using default: {default_name}")
        print("💡 Tip: Use --create <filename> to specify a custom name")
        config_name = default_name
    else:
        config_name = args.create
        if not config_name.endswith((".yaml", ".yml", ".json")):
            config_name += ".yaml"

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config_path = output_dir / config_name

    if config_path.exists():
        print(f"⚠️  Warning: Configuration file {config_path} already exists.")
        response = input("Do you want to overwrite it? (y/N): ")
        if response.lower() != "y":
            print("Configuration file creation cancelled.")
            return 0

    # Create configuration template based on type
    template_type = args.template
    config_content = generate_config_template(template_type)

    try:
        with open(config_path, "w") as f:
            f.write(config_content)

        print(f"✅ Configuration file created successfully: {config_path}")
        print(f"📋 Template type: {template_type.upper()}")
        print(f"📁 Location: {config_path.absolute()}")

        print("\n📝 Next steps:")
        print("1. Edit the configuration file with your specific course details")
        print(
            f"2. Use it with: python -m src.main init --course-name 'Your Course' --config-file {config_path}"
        )

        print("\n💡 Tips:")
        print("- Update the institution name and delivery details")
        print("- Add your UOC codes to the units section")
        print("- Customize assessment weights and due dates")
        print("- Adjust learning phases to match your course structure")

        # Show template-specific tips
        if template_type == "tafe":
            print("- The TAFE template includes common AI/ML UOC codes")
            print("- Assessment structure follows TAFE best practices")
        elif template_type == "commercial":
            print("- Commercial template is optimized for professional training")
            print("- 12-week structure with hybrid delivery focus")
        elif template_type == "accelerated":
            print("- Accelerated template for intensive learning")
            print("- 8-week structure with online delivery focus")

        return 0
    except Exception as e:
        print(f"❌ Failed to create configuration file: {e}")
        return 1


def generate_config_template(template_type: str) -> str:
    """Generate configuration template based on type"""

    if template_type == "basic":
        return """# Basic Course Configuration Template
# Edit this file with your specific course details

# REQUIRED: Course mission and context
mission: "Describe your course mission, context, and core learning objectives here"

# REQUIRED: Course configuration
course:
  type: "TAFE"  # REQUIRED: TAFE, COMMERCIAL, ACCELERATED, CUSTOM
  num_weeks: 20  # REQUIRED: Total number of weeks
  academic_weeks: 18  # REQUIRED: Number of academic weeks
  reassessment_weeks: 2  # REQUIRED: Number of reassessment weeks

# REQUIRED: Institution details
institution:
  name: "Your Institution Name"  # REQUIRED: Institution name
  delivery_location: "Your Campus/City"  # REQUIRED: Delivery location
  delivery_mode: "face-to-face"  # REQUIRED: face-to-face, online, hybrid

# REQUIRED: Student cohort information
students:
  cohort: "Describe your target student cohort"  # REQUIRED: Target student cohort
  typical_background: "Typical student background and experience"  # OPTIONAL: Student background

# OPTIONAL: Add your UOC codes here
# units:
#   - code: "ICTAII401"  # REQUIRED: Unit code
#     name: "Unit Name"  # REQUIRED: Unit name
#   - code: "ICTAII501"  # REQUIRED: Unit code
#     name: "Unit Name"  # REQUIRED: Unit name

# OPTIONAL: Customize assessment structure
# assessments:
#   structure:
#     - title: "Practical Project"  # OPTIONAL: Assessment title
#       type: "project"  # OPTIONAL: Assessment type
#       weight: 30  # OPTIONAL: Assessment weight
#       due_week: 8  # OPTIONAL: Due week
#     - title: "Knowledge Assessment"  # OPTIONAL: Assessment title
#       type: "test"  # OPTIONAL: Assessment type
#       weight: 25  # OPTIONAL: Assessment weight
#       due_week: 12  # OPTIONAL: Due week
#     - title: "Research Presentation"  # OPTIONAL: Assessment title
#       type: "presentation"  # OPTIONAL: Assessment type
#       weight: 25  # OPTIONAL: Assessment weight
#       due_week: 15  # OPTIONAL: Due week
#     - title: "Final Assessment"  # OPTIONAL: Assessment title
#       type: "comprehensive"  # OPTIONAL: Assessment type
#       weight: 20  # OPTIONAL: Assessment weight
#       due_week: 18  # OPTIONAL: Due week

# OPTIONAL: Customize learning phases
# learning_phases:
#   foundation: [1, 4]  # OPTIONAL: Foundation weeks
#   development: [5, 8]  # OPTIONAL: Development weeks
#   application: [9, 12]  # OPTIONAL: Application weeks
#   advanced: [13, 16]  # OPTIONAL: Advanced weeks
#   synthesis: [17, 18]  # OPTIONAL: Synthesis weeks
"""

    elif template_type == "tafe":
        return """# TAFE Course Configuration Template
# Optimized for TAFE delivery with units of competency

# REQUIRED: Course mission and context
mission: "Describe your course mission, context, and core learning objectives here"

# REQUIRED: Course configuration
course:
  type: "TAFE"  # REQUIRED: TAFE, COMMERCIAL, ACCELERATED, CUSTOM
  num_weeks: 20  # REQUIRED: Total number of weeks
  academic_weeks: 18  # REQUIRED: Number of academic weeks
  reassessment_weeks: 2  # REQUIRED: Number of reassessment weeks

# REQUIRED: Institution details
institution:
  name: "Your TAFE Institution"  # REQUIRED: Institution name
  delivery_location: "Your TAFE Campus"  # REQUIRED: Delivery location
  delivery_mode: "face-to-face"  # REQUIRED: face-to-face, online, hybrid

# REQUIRED: Student cohort information
students:
  cohort: "TAFE students with industry experience"  # REQUIRED: Target student cohort
  typical_background: "Students seeking vocational training and upskilling"  # OPTIONAL: Student background

# OPTIONAL: TAFE-specific industry contextualization
industry_context:
  primary_industry: "Information Technology"  # OPTIONAL: Primary industry focus
  industry_focus: "Software Development and Data Analytics"  # OPTIONAL: Specific industry focus
  specific_tools: ["Python", "SQL", "Power BI", "Azure"]  # OPTIONAL: Industry-specific tools
  industry_standards: ["Agile methodologies", "DevOps practices"]  # OPTIONAL: Industry standards
  workplace_context: "Modern software development environments with cloud-based tools"  # OPTIONAL: Workplace context
  industry_partners: ["Local software companies", "Government departments"]  # OPTIONAL: Industry partners

# REQUIRED: TAFE units of competency
units:
  - code: "ICTAII401"  # REQUIRED: Unit code
    name: "Apply artificial intelligence to identify automation opportunities"  # REQUIRED: Unit name
  - code: "ICTAII501"  # REQUIRED: Unit code
    name: "Build and test a machine learning model"  # REQUIRED: Unit name
  - code: "ICTAII502"  # REQUIRED: Unit code
    name: "Apply machine learning to task automation"  # REQUIRED: Unit name

# OPTIONAL: TAFE assessment structure (Competent/Not Competent - no weighting)
assessments:
  structure:
    - title: "Practical Project - Industry Application"  # OPTIONAL: Assessment title
      type: "project"  # OPTIONAL: Assessment type
      competency_focus: "Apply technical skills in real-world context"  # OPTIONAL: Competency focus
      due_week: 8  # OPTIONAL: Due week
      assessment_method: "Portfolio of work demonstrating industry tools"  # OPTIONAL: Assessment method
    - title: "Knowledge Assessment - Industry Standards"  # OPTIONAL: Assessment title
      type: "test"  # OPTIONAL: Assessment type
      competency_focus: "Demonstrate understanding of industry practices"  # OPTIONAL: Competency focus
      due_week: 12  # OPTIONAL: Due week
      assessment_method: "Written assessment with practical scenarios"  # OPTIONAL: Assessment method
    - title: "Industry Presentation"  # OPTIONAL: Assessment title
      type: "presentation"  # OPTIONAL: Assessment type
      competency_focus: "Communicate technical concepts to stakeholders"  # OPTIONAL: Competency focus
      due_week: 15  # OPTIONAL: Due week
      assessment_method: "Presentation to industry panel"  # OPTIONAL: Assessment method
    - title: "Final Competency Assessment"  # OPTIONAL: Assessment title
      type: "comprehensive"  # OPTIONAL: Assessment type
      competency_focus: "Demonstrate overall unit competency"  # OPTIONAL: Competency focus
      due_week: 18  # OPTIONAL: Due week
      assessment_method: "Integrated assessment across all elements"  # OPTIONAL: Assessment method

# OPTIONAL: Assessment criteria (TAFE Competent/Not Competent)
assessment_criteria:
  competent_standard: "Student must demonstrate competency in ALL assessment tasks"  # OPTIONAL: Competency standard
  grading_system: "Competent (C) / Not Yet Competent (NYC)"  # OPTIONAL: Grading system
  minimum_requirements: "All assessments must be completed and meet competency standards"  # OPTIONAL: Minimum requirements
  reassessment_policy: "Students may be reassessed in weeks 19-20 if not yet competent"  # OPTIONAL: Reassessment policy

# OPTIONAL: Learning phases
learning_phases:
  foundation: [1, 4]      # OPTIONAL: Foundation weeks
  development: [5, 8]     # OPTIONAL: Development weeks
  application: [9, 12]    # OPTIONAL: Application weeks
  advanced: [13, 16]      # OPTIONAL: Advanced weeks
  synthesis: [17, 18]     # OPTIONAL: Synthesis weeks
"""

    elif template_type == "commercial":
        return """# Commercial Course Configuration Template
# Optimized for commercial training and upskilling

# REQUIRED: Course mission and context
mission: "Describe your course mission, context, and core learning objectives here"

# REQUIRED: Course configuration
course:
  type: "COMMERCIAL"  # REQUIRED: TAFE, COMMERCIAL, ACCELERATED, CUSTOM
  num_weeks: 12  # REQUIRED: Total number of weeks
  academic_weeks: 12  # REQUIRED: Number of academic weeks
  reassessment_weeks: 0  # REQUIRED: Number of reassessment weeks

# REQUIRED: Institution details
institution:
  name: "Your Training Organization"  # REQUIRED: Institution name
  delivery_location: "Your Training Center"  # REQUIRED: Delivery location
  delivery_mode: "hybrid"  # REQUIRED: face-to-face, online, hybrid

# REQUIRED: Student cohort information
students:
  cohort: "Professional learners seeking upskilling"  # REQUIRED: Target student cohort
  typical_background: "Working professionals with some technical background"  # OPTIONAL: Student background

# OPTIONAL: Add relevant skill areas
# skill_areas:
#   - "Data Analysis"  # OPTIONAL: Skill area
#   - "Machine Learning"  # OPTIONAL: Skill area
#   - "AI Applications"  # OPTIONAL: Skill area

# OPTIONAL: Assessment structure
assessments:
  structure:
    - title: "Skills Assessment Project"  # OPTIONAL: Assessment title
      type: "project"  # OPTIONAL: Assessment type
      weight: 40  # OPTIONAL: Assessment weight
      due_week: 6  # OPTIONAL: Due week
    - title: "Knowledge Check"  # OPTIONAL: Assessment title
      type: "test"  # OPTIONAL: Assessment type
      weight: 30  # OPTIONAL: Assessment weight
      due_week: 9  # OPTIONAL: Due week
    - title: "Final Capstone Project"  # OPTIONAL: Assessment title
      type: "comprehensive"  # OPTIONAL: Assessment type
      weight: 30  # OPTIONAL: Assessment weight
      due_week: 12  # OPTIONAL: Due week

# OPTIONAL: Learning phases
learning_phases:
  foundation: [1, 3]      # OPTIONAL: Core concepts and tools
  development: [4, 6]     # OPTIONAL: Skill building
  application: [7, 9]     # OPTIONAL: Real-world application
  synthesis: [10, 12]     # OPTIONAL: Integration and mastery
"""

    elif template_type == "accelerated":
        return """# Accelerated Course Configuration Template
# Optimized for intensive, fast-paced learning

# REQUIRED: Course mission and context
mission: "Describe your course mission, context, and core learning objectives here"

# REQUIRED: Course configuration
course:
  type: "ACCELERATED"  # REQUIRED: TAFE, COMMERCIAL, ACCELERATED, CUSTOM
  num_weeks: 8  # REQUIRED: Total number of weeks
  academic_weeks: 8  # REQUIRED: Number of academic weeks
  reassessment_weeks: 0  # REQUIRED: Number of reassessment weeks

# REQUIRED: Institution details
institution:
  name: "Your Training Institution"  # REQUIRED: Institution name
  delivery_location: "Your Campus"  # REQUIRED: Delivery location
  delivery_mode: "online"  # REQUIRED: face-to-face, online, hybrid

# REQUIRED: Student cohort information
students:
  cohort: "Fast-track learners with prior experience"  # REQUIRED: Target student cohort
  typical_background: "Students with relevant background seeking rapid upskilling"  # OPTIONAL: Student background

# REQUIRED: Units of competency for accelerated delivery
units:
  - code: "ICTAII401"  # REQUIRED: Unit code
    name: "Apply artificial intelligence to identify automation opportunities"  # REQUIRED: Unit name
  - code: "ICTAII501"  # REQUIRED: Unit code
    name: "Build and test a machine learning model"  # REQUIRED: Unit name

# OPTIONAL: Assessment structure
assessments:
  structure:
    - title: "Rapid Skills Assessment"  # OPTIONAL: Assessment title
      type: "project"  # OPTIONAL: Assessment type
      weight: 50  # OPTIONAL: Assessment weight
      due_week: 4  # OPTIONAL: Due week
    - title: "Final Intensive Assessment"  # OPTIONAL: Assessment title
      type: "comprehensive"  # OPTIONAL: Assessment type
      weight: 50  # OPTIONAL: Assessment weight
      due_week: 8  # OPTIONAL: Due week

# OPTIONAL: Learning phases
learning_phases:
  foundation: [1, 2]      # OPTIONAL: Core concepts
  development: [3, 4]     # OPTIONAL: Skill building
  application: [5, 6]     # OPTIONAL: Practical application
  synthesis: [7, 8]       # OPTIONAL: Integration and assessment
"""

    else:  # custom
        return """# Custom Course Configuration Template
# Fully customizable template for unique course requirements

# REQUIRED: Course mission and context
mission: "Describe your course mission, context, and core learning objectives here"

# REQUIRED: Course configuration
course:
  type: "CUSTOM"  # REQUIRED: TAFE, COMMERCIAL, ACCELERATED, CUSTOM
  num_weeks: 16  # REQUIRED: Total number of weeks (adjust as needed)
  academic_weeks: 14  # REQUIRED: Number of academic weeks (adjust as needed)
  reassessment_weeks: 2  # REQUIRED: Number of reassessment weeks (adjust as needed)

# REQUIRED: Institution details
institution:
  name: "Your Institution"  # REQUIRED: Institution name
  delivery_location: "Your Location"  # REQUIRED: Delivery location
  delivery_mode: "face-to-face"  # REQUIRED: face-to-face, online, hybrid

# REQUIRED: Student cohort information
students:
  cohort: "Describe your unique student cohort"  # REQUIRED: Target student cohort
  typical_background: "Describe typical student background"  # OPTIONAL: Student background

# OPTIONAL: Add your custom units or skill areas
# units:
#   - code: "CUSTOM001"  # REQUIRED: Unit code
#     name: "Custom Unit 1"  # REQUIRED: Unit name
#   - code: "CUSTOM002"  # REQUIRED: Unit code
#     name: "Custom Unit 2"  # REQUIRED: Unit name

# OPTIONAL: Customize assessment structure
assessments:
  structure:
    - title: "Custom Assessment 1"  # OPTIONAL: Assessment title
      type: "project"  # OPTIONAL: project, test, presentation, comprehensive
      weight: 25  # OPTIONAL: Assessment weight
      due_week: 4  # OPTIONAL: Due week
    - title: "Custom Assessment 2"  # OPTIONAL: Assessment title
      type: "test"  # OPTIONAL: Assessment type
      weight: 25  # OPTIONAL: Assessment weight
      due_week: 8  # OPTIONAL: Due week
    - title: "Custom Assessment 3"  # OPTIONAL: Assessment title
      type: "presentation"  # OPTIONAL: Assessment type
      weight: 25  # OPTIONAL: Assessment weight
      due_week: 12  # OPTIONAL: Due week
    - title: "Final Custom Assessment"  # OPTIONAL: Assessment title
      type: "comprehensive"  # OPTIONAL: Assessment type
      weight: 25  # OPTIONAL: Assessment weight
      due_week: 16  # OPTIONAL: Due week

# OPTIONAL: Customize learning phases
learning_phases:
  phase1: [1, 4]      # OPTIONAL: Define your phases
  phase2: [5, 8]      # OPTIONAL: Define your phases
  phase3: [9, 12]
  phase4: [13, 16]

# Add any additional custom configuration
# custom_settings:
#   special_requirements: "Any special requirements"
#   additional_resources: "Additional resources needed"
"""


def convert(course_directory: str, pattern: str, reverse: bool):
    """Convert markdown files to Jupyter notebooks (or vice versa) using jupytext."""
    from src.utils.notebook_converter import (
        batch_convert_md_to_notebook,
        batch_convert_notebook_to_md,
    )

    course_path = Path(course_directory)
    if not course_path.exists():
        print(f"❌ Course directory not found: {course_directory}")
        return

    if reverse:
        print(f"Converting notebooks to markdown in {course_directory}...")
        created_files = batch_convert_notebook_to_md(course_path, pattern)
        print(f"✅ Converted {len(created_files)} notebooks to markdown files")
    else:
        print(f"Converting markdown files to notebooks in {course_directory}...")
        created_files = batch_convert_md_to_notebook(course_path, pattern)
        print(f"✅ Converted {len(created_files)} markdown files to notebooks")

    for file_path in created_files:
        print(f"  📄 {file_path}")


def main():
    args = parser.parse_args()

    if not hasattr(args, "command") or args.command is None:
        parser.print_help()
        return 1
    elif args.command == "init":
        return init(args)
    elif args.command == "push":
        return push(args)
    elif args.command == "config":
        return create_config(args)
    elif args.command == "convert":
        convert(args.course_directory, args.pattern, args.reverse)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    exit(main())
