from pathlib import Path

from src.content_generator.oo_mapping_matrix import mapping_matrix as oo_mapping_matrix
from src.content_generator.assessment_tools import assess_tool
from src.content_generator.lap import lap

from src.content_generator.mapping_matrix import mapping_matrix


# Use example directory that exists in the project
COURSE_CONTENT = Path("example/AISS-ICTSS00120")
OUTPUT_LOCATION = Path("example")


def test_generate_lap():
    lap(COURSE_CONTENT, OUTPUT_LOCATION)


def test_generate_assessments():
    assess_tool(COURSE_CONTENT, OUTPUT_LOCATION)


def test_generate_mapping_matrix():
    mapping_matrix(COURSE_CONTENT, OUTPUT_LOCATION)


def test_generate_oo_mapping_matrix():
    oo_mapping_matrix(COURSE_CONTENT, OUTPUT_LOCATION)
