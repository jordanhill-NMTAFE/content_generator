# Load environment variables BEFORE any other imports
# This must be at the very top to ensure env vars are available for module-level assertions
from pathlib import Path
import os

def _load_dotenv():
    """Load .env file from standard locations before other imports."""
    from dotenv import load_dotenv

    # Locations to search for .env file (in priority order)
    env_locations = [
        Path.cwd() / ".env",  # Current working directory
        Path.home() / ".config" / "content-generator" / ".env",  # User config dir
        Path.home() / ".content-generator.env",  # User home directory
    ]

    for env_path in env_locations:
        if env_path.exists():
            load_dotenv(env_path)
            return str(env_path)

    return None

# Load dotenv immediately
_env_file_loaded = _load_dotenv()

# Set ROOT_DIR to package location if not already set
if "ROOT_DIR" not in os.environ:
    os.environ["ROOT_DIR"] = str(Path(__file__).parent.parent.resolve())

# Now import everything else
import argparse
from requests import RequestException
from src.content_generator.lap import lap
from src.content_generator.assessment_tools import assess_tool, convert_assessment_resources
from src.content_generator.marking_guide import marking_guide_generator
from src.content_generator.init import init_course
from os import environ as env

from src.content_generator.mapping_matrix import mapping_matrix

import logging

log = logging.getLogger(__name__)

import click
import logging

assert "COURSE_CONTENT" in env, f"COURSE_CONTENT is undefined. Create a .env file at ~/.config/content-generator/.env with COURSE_CONTENT=/path/to/your/course-content"
assert "OUTPUT_LOCATION" in env, f"OUTPUT_LOCATION is undefined. Create a .env file at ~/.config/content-generator/.env with OUTPUT_LOCATION=/path/to/output"


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

# Model selection argument
init_parser.add_argument(
    "--model",
    "-i",
    type=str,
    default="gpt-4.1-nano-2025-04-14",
    help="The AI model to use for content generation (e.g., gpt-4.1-nano-2025-04-14, gpt-4o-mini, gpt-4o, claude-3-5-sonnet)",
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
    "course_directory",
    nargs="?",
    type=str,
    help="Path to the course content folder to process (default: current directory)",
)
generate_parser.add_argument(
    "--target",
    "-t",
    type=str,
    required=False,
    help="Path to the course content folder to process (alternative to positional argument)",
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

# Validation command for validating assessment mappings
validate_parser = subparsers.add_parser(
    "validate",
    help="Validate assessment mappings against Units of Competency data",
)

validate_parser.add_argument(
    "--target",
    "-t",
    type=str,
    required=False,
    help="Path to the course content folder to validate (default: current directory)",
)

validate_parser.add_argument(
    "--assessment",
    "-a",
    type=str,
    required=False,
    help="Specific assessment to validate (by name, e.g., 'AT1 Identify Opportunities for AI Task Automation')",
)

validate_parser.add_argument(
    "--fix",
    "-f",
    action="store_true",
    help="Attempt to fix validation errors by regenerating invalid mappings",
)

# List models command
list_models_parser = subparsers.add_parser(
    "list-models",
    help="List available AI models for content generation",
)

# Analyze Word document command
analyze_parser = subparsers.add_parser(
    "analyze",
    help="Analyze Word document structure (tables, paragraphs, context)",
)

analyze_parser.add_argument(
    "document_path",
    type=str,
    help="Path to the Word document (.docx) to analyze",
)

analyze_parser.add_argument(
    "--tables-only",
    "-t",
    action="store_true",
    help="Show only table structures (skip paragraphs)",
)

analyze_parser.add_argument(
    "--context-only",
    "-c",
    action="store_true",
    help="Show only paragraph context (skip detailed table content)",
)

analyze_parser.add_argument(
    "--export",
    "-e",
    type=str,
    help="Export analysis to file (txt or json format)",
)

# New theme argument
init_parser.add_argument(
    "--theme",
    "-th",
    type=str,
    default="northmetro.css",
    help="Path or filename of the Marp CSS theme file to use for slides.md. The theme name will be parsed from the @theme declaration in this file.",
)

init_parser.add_argument(
    "--yes",
    "-y",
    action="store_true",
    help="Skip confirmation prompts and proceed with initialization",
)


def init(args):
    """Initialize a new course content folder"""
    log.info(f"Initializing new course: {args.course_name}")

    target_path = None
    if args.target:
        target_path = Path(args.target)
        if not target_path.exists():
            log.info(f"Target path {target_path} does not exist. Creating...")
            target_path.mkdir(parents=True, exist_ok=True)

    # Handle mission prompt input
    mission_prompt = args.mission
    if mission_prompt and mission_prompt.startswith("<<"):
        log.info("Enter your mission prompt (end with '<<' on a new line):")
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
        # Defensive fallback: ensure args.model exists
        if not hasattr(args, "model"):
            args.model = "gpt-4.1-nano-2025-04-14"
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
            model=args.model,
            yes_to_all=args.yes,
            **extra_kwargs,
        )
        log.info(f"Course '{args.course_name}' initialized successfully!")
        log.info(f"Course location: {course_path}")

        # Enhanced feedback
        if args.config_file:
            log.info(f"✓ Configuration loaded from: {args.config_file}")
        if args.course_type != "TAFE":
            log.info(f"✓ Course type: {args.course_type}")
        if args.num_weeks and args.num_weeks != 20:
            log.info(f"✓ Course duration: {args.num_weeks} weeks")
        if args.delivery_mode != "face-to-face":
            log.info(f"✓ Delivery mode: {args.delivery_mode}")

        if args.no_llm:
            log.info("✓ Course initialized with template content only (LLM disabled)")
            log.info(f"✓ Model selected: {args.model} (not used due to --no-llm)")
        elif args.uoc_codes:
            log.info(f"UOC codes used: {', '.join(args.uoc_codes)}")
            log.info("✓ Course content generated using UOC data and language models")
            log.info(f"✓ Using AI model: {args.model}")
        elif mission_prompt:
            log.info("✓ Course guided by mission prompt")
            log.info(f"✓ Using AI model: {args.model}")
        else:
            log.info("✓ Course initialized with template content")
            log.info(f"✓ Using AI model: {args.model}")

        log.info("\nNext steps:")
        log.info("1. Review and update course information in 2 KAD/1 LAP/fields.md")
        log.info("2. Customize assessment tools in 2 KAD/5 Assess Tool/")
        log.info("3. Add learning materials to 1 Learning Materials/")
        log.info(
            "4. Run 'python -m src.main generate --target <course_path>' to generate documents"
        )
    except Exception as e:
        log.error(f"Failed to initialize course: {e}")
        return 1

    return 0


def generate_lap():
    lap(COURSE_CONTENT, OUTPUT_LOCATION)


def generate_assessments():
    assess_tool(COURSE_CONTENT, OUTPUT_LOCATION)


def generate_marking_guides():
    marking_guide_generator(COURSE_CONTENT, OUTPUT_LOCATION)


def generate_matrix():
    mapping_matrix(COURSE_CONTENT, OUTPUT_LOCATION)


def generate_resources():
    convert_assessment_resources(COURSE_CONTENT, OUTPUT_LOCATION)


def push(args):
    """Generate all content (push)"""

    # Resolve paths - prioritize positional argument, then --target, then current directory
    if args.course_directory:
        content_path = Path(args.course_directory).resolve()
        log.info(f"📁 Using positional argument: {content_path}")
    elif args.target:
        content_path = Path(args.target).resolve()
        log.info(f"📁 Using --target argument: {content_path}")
    else:
        content_path = Path.cwd().resolve()
        log.info(f"📁 No target specified, using current directory: {content_path}")

    if not content_path.exists():
        log.error(f"❌ Error: Content path {content_path} does not exist")
        log.info("💡 Please ensure the course directory exists before running push")
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
            log.info("Production mode: Using environment variables")
        else:
            # Fall back to testing mode if production directories aren't accessible
            COURSE_CONTENT = content_path
            OUTPUT_LOCATION = Path.cwd() / f"output_{content_path.name}"
            log.info(
                "Testing mode: Production directories not accessible, using local output"
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
            log.info("Test mode: Creating output in test_outputs directory")
        else:
            # Normal testing mode: create output in current directory
            OUTPUT_LOCATION = Path.cwd() / f"output_{content_path.name}"
            log.info("Testing mode: Creating output in current directory")

    log.info(f"COURSE_CONTENT: {COURSE_CONTENT}")
    log.info(f"OUTPUT_LOCATION: {OUTPUT_LOCATION}")

    # Ensure output directory exists
    OUTPUT_LOCATION.mkdir(parents=True, exist_ok=True)

    # Call the functions using the global variables (as expected by the functions)
    try:
        log.info("Starting LAP generation...")
        generate_lap()
        log.info("LAP generation completed successfully")
    except Exception as e:
        log.error(f"Error in LAP generation: {e}")

    try:
        log.info("Starting assessment generation...")
        generate_assessments()
        log.info("Assessment generation completed successfully")
    except Exception as e:
        log.error(f"Error in assessment generation: {e}")

    try:
        log.info("Starting marking guide generation...")
        generate_marking_guides()
        log.info("Marking guide generation completed successfully")
    except Exception as e:
        log.error(f"Error in marking guide generation: {e}")

    try:
        log.info("Starting mapping matrix generation...")
        generate_matrix()
        log.info("Mapping matrix generation completed successfully")
    except Exception as e:
        log.error(f"Error in mapping matrix generation: {e}")

    try:
        log.info("Starting assessment resources conversion...")
        generate_resources()
        log.info("Assessment resources conversion completed successfully")
    except Exception as e:
        log.error(f"Error in assessment resources conversion: {e}")


def validate(args):
    """Validate assessment mappings against UOC data"""
    from src.utils.assessment_validator import (
        validate_assessment_directory,
        validate_assessment_file,
    )
    from src.content_generator.init import CourseInitializer
    from src.utils.markdown import parse_md

    # Resolve paths - use current directory if no target specified
    if args.target:
        content_path = Path(args.target).resolve()
    else:
        content_path = Path.cwd().resolve()
        log.info(f"📁 No target specified, using current directory: {content_path}")

    if not content_path.exists():
        log.error(f"❌ Error: Content path {content_path} does not exist")
        return 1

    # Check if this is a course directory
    assessments_dir = content_path / "2 KAD" / "5 Assess Tool"
    if not assessments_dir.exists():
        log.error(f"❌ Error: No assessments directory found at {assessments_dir}")
        log.info("💡 Please ensure this is a valid course directory with assessments")
        return 1

    # Load course units (we need UOC data for validation)
    try:
        # Try to load from course config if it exists
        config_file = content_path / "course_config.yaml"
        if config_file.exists():
            course_initializer = CourseInitializer(config_file=config_file)
            units = course_initializer.units
        else:
            # Try to load from fields.md if it exists
            fields_file = content_path / "2 KAD" / "1 LAP" / "fields.md"
            if fields_file.exists():
                fields_data = parse_md(fields_file)
                units_data = fields_data.get("units", [])
                if units_data:
                    # Extract unit codes from the units data
                    from src.utils.uoc_api import UnitOfCompetency

                    units = []
                    for unit_data in units_data:
                        if isinstance(unit_data, dict) and "id" in unit_data:
                            unit_code = unit_data["id"]
                            try:
                                uoc = UnitOfCompetency(unit_code)
                                units.append(
                                    {
                                        "id": unit_code,
                                        "name": getattr(
                                            uoc.data, "title", f"Unit {unit_code}"
                                        ),
                                        "data": uoc.data,
                                    }
                                )
                                log.info(f"✅ Loaded UOC {unit_code}")
                            except Exception as e:
                                log.warning(f"⚠️  Could not load UOC {unit_code}: {e}")
                        elif isinstance(unit_data, str):
                            # Handle case where units is a list of strings
                            try:
                                uoc = UnitOfCompetency(unit_data)
                                units.append(
                                    {
                                        "id": unit_data,
                                        "name": getattr(
                                            uoc.data, "title", f"Unit {unit_data}"
                                        ),
                                        "data": uoc.data,
                                    }
                                )
                                log.info(f"✅ Loaded UOC {unit_data}")
                            except Exception as e:
                                log.warning(f"⚠️  Could not load UOC {unit_data}: {e}")
                else:
                    log.error("❌ No unit codes found in fields.md")
                    return 1
            else:
                log.error(
                    "❌ No course configuration found (course_config.yaml or fields.md)"
                )
                log.info(
                    "💡 Please run 'python -m src.main init' first to create a course"
                )
                return 1
    except Exception as e:
        log.error(f"❌ Error loading course units: {e}")
        return 1

    if not units:
        log.error("❌ No units loaded for validation")
        return 1

    log.info(f"✅ Loaded {len(units)} units for validation")

    # Validate assessments
    if args.assessment:
        # Validate specific assessment
        assessment_dir = assessments_dir / args.assessment
        if not assessment_dir.exists():
            log.error(f"❌ Assessment '{args.assessment}' not found")
            return 1

        assessment_file = assessment_dir / "assessment.md"
        if not assessment_file.exists():
            log.error(f"❌ Assessment file not found at {assessment_file}")
            return 1

        log.info(f"🔍 Validating assessment: {args.assessment}")
        is_valid, errors, warnings = validate_assessment_file(assessment_file, units)

        if is_valid:
            log.info(f"✅ Assessment '{args.assessment}' validation passed")
            if warnings:
                for warning in warnings:
                    log.warning(f"⚠️  {warning}")
        else:
            log.error(f"❌ Assessment '{args.assessment}' validation failed")
            for error in errors:
                log.error(f"   Error: {error}")

            if args.fix:
                log.info(f"🔄 Attempting to fix assessment '{args.assessment}'...")
                # TODO: Implement fix logic
                log.warning("⚠️  Auto-fix functionality not yet implemented")

            return 1
    else:
        # Validate all assessments
        log.info("🔍 Validating all assessments...")
        results = validate_assessment_directory(assessments_dir, units)

        if not results:
            log.warning("⚠️  No assessment files found for validation")
            return 0

        valid_count = 0
        total_count = len(results)

        for assessment_name, (is_valid, errors, warnings) in results.items():
            if is_valid:
                log.info(f"✅ {assessment_name}: Validation passed")
                valid_count += 1
                if warnings:
                    for warning in warnings:
                        log.warning(f"   ⚠️  {warning}")
            else:
                log.error(f"❌ {assessment_name}: Validation failed")
                for error in errors:
                    log.error(f"   Error: {error}")

        log.info(
            f"📊 Validation Summary: {valid_count}/{total_count} assessments passed"
        )

        if valid_count < total_count:
            if args.fix:
                log.info("🔄 Attempting to fix failed assessments...")
                # TODO: Implement fix logic
                log.warning("⚠️  Auto-fix functionality not yet implemented")
            return 1
        else:
            log.info("All validations passed!")
            return 0


def analyze_word_document(args):
    """Delegate to docx_analyzer package."""
    from docx_analyzer.cli import analyze_word_document as _analyze
    return _analyze(args)


def create_config(args):
    """Create a new configuration file"""
    # Use sensible defaults if no arguments provided
    if not args.create:
        # Generate a default filename based on current directory or course name
        default_name = "course_config.yaml"
        log.info(
            f"📝 No configuration file name specified. Using default: {default_name}"
        )
        log.info("💡 Tip: Use --create <filename> to specify a custom name")
        config_name = default_name
    else:
        config_name = args.create
        if not config_name.endswith((".yaml", ".yml", ".json")):
            config_name += ".yaml"

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config_path = output_dir / config_name

    if config_path.exists():
        log.warning(f"⚠️  Warning: Configuration file {config_path} already exists.")
        response = input("Do you want to overwrite it? (y/N): ")
        if response.lower() != "y":
            log.info("Configuration file creation cancelled.")
            return 0

    # Create configuration template based on type
    template_type = args.template
    config_content = generate_config_template(template_type)

    try:
        with open(config_path, "w") as f:
            f.write(config_content)

        log.info(f"✅ Configuration file created successfully: {config_path}")
        log.info(f"📋 Template type: {template_type.upper()}")
        log.info(f"📁 Location: {config_path.absolute()}")

        log.info("\n📝 Next steps:")
        log.info("1. Edit the configuration file with your specific course details")
        log.info(
            f"2. Use it with: python -m src.main init --course-name 'Your Course' --config-file {config_path}"
        )

        log.info("\n💡 Tips:")
        log.info("- Update the institution name and delivery details")
        log.info("- Add your UOC codes to the units section")
        log.info("- Customize assessment weights and due dates")
        log.info("- Adjust learning phases to match your course structure")

        # Show template-specific tips
        if template_type == "tafe":
            log.info("- The TAFE template includes common AI/ML UOC codes")
            log.info("- Assessment structure follows TAFE best practices")
        elif template_type == "commercial":
            log.info("- Commercial template is optimized for professional training")
            log.info("- 12-week structure with hybrid delivery focus")
        elif template_type == "accelerated":
            log.info("- Accelerated template for intensive learning")
            log.info("- 8-week structure with online delivery focus")

        return 0
    except Exception as e:
        log.error(f"❌ Failed to create configuration file: {e}")
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
        log.error(f"❌ Course directory not found: {course_directory}")
        return

    if reverse:
        log.info(f"Converting notebooks to markdown in {course_directory}...")
        created_files = batch_convert_notebook_to_md(course_path, pattern)
        log.info(f"✅ Converted {len(created_files)} notebooks to markdown files")
    else:
        log.info(f"Converting markdown files to notebooks in {course_directory}...")
        created_files = batch_convert_md_to_notebook(course_path, pattern)
        log.info(f"✅ Converted {len(created_files)} markdown files to notebooks")

    for file_path in created_files:
        log.info(f"  📄 {file_path}")


def list_models():
    """List available AI models for content generation"""
    try:
        from src.gptgen.model_factory import list_available_models

        models = list_available_models()
        log.info("Available AI models for content generation:")
        log.info("=" * 50)
        for model in models:
            log.info(f"• {model}")
        log.info("=" * 50)
        log.info(f"Total: {len(models)} models available")
        return 0
    except Exception as e:
        log.error(f"❌ Error listing models: {e}")
        return 1


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
    elif args.command == "validate":
        return validate(args)
    elif args.command == "list-models":
        return list_models()
    elif args.command == "analyze":
        return analyze_word_document(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    exit(main())
