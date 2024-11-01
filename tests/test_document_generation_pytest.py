import sys
import os
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.oo_mapping_matrix import mapping_matrix as oo_mapping_matrix
from src.assessment_tools import assess_tool
from src.lap import lap

from src.mapping_matrix import mapping_matrix

COURSE_CONTENT = Path("~/NMTAFE/Course Content/AI Skillset").expanduser()
OUTPUT_LOCATION = Path("~/NMTAFE/content_generator/example").expanduser()


def test_generate_lap():
    lap(COURSE_CONTENT, OUTPUT_LOCATION)


def test_generate_assessments():
    assess_tool(COURSE_CONTENT, OUTPUT_LOCATION)


def test_generate_mapping_matrix():
    mapping_matrix(COURSE_CONTENT, OUTPUT_LOCATION)


def test_generate_oo_mapping_matrix():
    oo_mapping_matrix(COURSE_CONTENT, OUTPUT_LOCATION)
