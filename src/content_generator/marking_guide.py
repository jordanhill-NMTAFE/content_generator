import os
from os import environ as env
import click
from docx import Document
from docx.table import Table, _Cell
from docx.styles.styles import Styles
from docx.enum.style import WD_STYLE_TYPE
from pathlib import Path
import re
from typing import List, Dict

from src.utils.markdownit import markdown_to_word, parse_md
from src.utils.math import add_tuples

# Ensure we have access to a root dir for the templates
assert "ROOT_DIR" in env, "ROOT_DIR is undefined"
# Absolute Path of course content folder from env
assert "COURSE_CONTENT" in env, "COURSE_CONTENT is undefined"
assert "OUTPUT_LOCATION" in env, "OUTPUT_LOCATION is undefined"

COURSE_CONTENT = Path(env["COURSE_CONTENT"]).resolve()
OUTPUT_LOCATION = Path(env["OUTPUT_LOCATION"]).resolve()

# Source code locations:
ROOT = env["ROOT_DIR"]  # repo root location
TEMPLATES = Path("templates/")

# Implementation Specific
TEMPLATE = TEMPLATES / Path(
    "Instructions to Assessors and Marking Guide (F122A13).docx"
)
OUTPUT_FILE = Path("Instructions to Assessors and Marking Guide (F122A13).docx")

# Relative Path of Content Files (Input and Output):
MARKING_GUIDES = Path("2 KAD/6 Marking Guide/")


def marking_guide_generator(course_directory: Path, output_location: Path):
    """
    Generate marking guide Word documents from markdown files.

    :param course_directory: Path to the course content directory
    :param output_location: Path to the output directory
    """
    assert course_directory.is_dir()
    assert output_location.is_dir()

    marking_guides_dir = course_directory / MARKING_GUIDES

    if not marking_guides_dir.exists():
        print(f"Marking guides directory not found: {marking_guides_dir}")
        return

    for marking_guide in marking_guides_dir.rglob("marking_guide.md"):
        print(f"Processing marking guide: {marking_guide}")

        # Load and prepare the Word document
        normal_doc = Document()  # Load normal.dotx styles
        doc: Document = Document(ROOT / TEMPLATE)
        styles: Styles = doc.styles
        normal_styles: Styles = normal_doc.styles

        # Copy styles from normal.dotx to template
        for style in normal_styles:
            if style.name not in doc.styles:
                try:
                    doc.styles.add_style(style.name, WD_STYLE_TYPE.PARAGRAPH)
                except:
                    pass  # Style might already exist or be built-in

        # Define output path
        output_path = (
            output_location
            / MARKING_GUIDES
            / Path(marking_guide.parent.name)
            / OUTPUT_FILE
        )

        if not marking_guide.is_file():
            continue

        # Parse the markdown file
        markdown = parse_md(marking_guide)

        # Populate the Word document
        populate_marking_guide_template(doc, markdown)

        # Ensure output directory exists
        output_path.parent.mkdir(exist_ok=True, parents=True)

        # Save the document
        doc.save(output_path)
        print(f"Generated marking guide: {output_path}")


def populate_marking_guide_template(doc: Document, markdown):
    """
    Populate the Word template with marking guide content.

    :param doc: Word document object
    :param markdown: Parsed markdown with frontmatter and content
    """
    # Table 0: Header information (Qualification and Units being assessed)
    if len(doc.tables) > 0:
        header_table = doc.tables[0]

        # Qualification information
        if len(header_table.rows) > 0 and len(header_table.rows[0].cells) > 1:
            qual_cell = header_table.cell(0, 1)
            qual_info = markdown.metadata.get(
                "qualification_national_code_and_title", ""
            )
            qual_cell.text = qual_info

        # Units being assessed (Table 0, Row 1)
        # Assumes template has been updated to remove content controls and use standard 2-cell structure
        if len(header_table.rows) > 1:
            row1 = header_table.rows[1]

            # Ensure Row 1 has 2 cells (if template was fixed)
            if len(row1.cells) >= 2:
                # Write units directly to [1,1] - the content cell
                unit_cell = header_table.cell(1, 1)
                units = markdown.metadata.get("units", [])

                if units:
                    unit_text = "\n".join(
                        f"{unit.get('id', '')} {unit.get('name', '')}" for unit in units
                    )
                    # Replace placeholder text with actual unit data
                    unit_cell.text = f"{unit_text}\n"
            else:
                print(
                    f"⚠️  Warning: Table 0, Row 1 has {len(row1.cells)} cells, expected 2. Template may need content control removal."
                )

    # Table 1: Assessment task information
    if len(doc.tables) > 1:
        task_table = doc.tables[1]
        if len(task_table.rows) > 0 and len(task_table.rows[0].cells) > 1:
            task_cell = task_table.cell(0, 1)
            assessment_name = markdown.metadata.get("name", "")
            task_cell.text = assessment_name

    # Table 2: Prerequisites (confirmed by "Pre-requisite Units" paragraph)
    if len(doc.tables) > 2:
        prereq_table = doc.tables[2]
        prerequisites = markdown.metadata.get("prerequisites", [])

        # Populate rows 1-2 with prerequisites (row 0 is header, row 3 is disclaimer)
        for i, prereq in enumerate(
            prerequisites[:2]
        ):  # Template has 2 data rows (rows 1-2)
            row_index = i + 1  # Skip header row (row 0)
            if (
                row_index < len(prereq_table.rows) - 1
            ):  # Don't overwrite disclaimer row (row 3)
                if len(prereq_table.rows[row_index].cells) > 1:
                    code_cell = prereq_table.cell(row_index, 0)
                    name_cell = prereq_table.cell(row_index, 1)
                    code_cell.text = prereq.get("id", "")
                    name_cell.text = prereq.get("name", "")

    # Table 3: Assessment details (location, date, duration, etc.)
    if len(doc.tables) > 3:
        details_table = doc.tables[3]
        # This table contains assessment logistics - can be populated from frontmatter if available

        # Available fields based on template analysis:
        # Row 0: Location | Date
        # Row 1: Duration | Resources
        # Row 2: OSH/WHS | Instructions to Students
        # Row 3: Instructions To Assessors | Details for assessment set-up
        # Rows 4-6: Empty (additional space)

        # Example population (uncomment and add YAML fields as needed):
        # if "assessment_location" in markdown.metadata:
        #     details_table.cell(0, 0).text = f"Location: {markdown.metadata['assessment_location']}"
        # if "assessment_date" in markdown.metadata:
        #     details_table.cell(0, 1).text = f"Date: {markdown.metadata['assessment_date']}"
        pass

    # Table 4: Marking criteria and benchmarks - Insert the whole markdown content here
    if len(doc.tables) > 4:
        criteria_table = doc.tables[4]
        if len(criteria_table.rows) > 0 and len(criteria_table.rows[0].cells) > 0:
            criteria_cell = criteria_table.cell(0, 0)
            criteria_cell.text = ""

            # Clear existing content (following assessment_tools.py pattern)
            for paragraph in criteria_cell.paragraphs:
                p = paragraph._element
                p.getparent().remove(p)
            criteria_cell._tc.clear_content()

            # Add the entire markdown content (body, not frontmatter) to the cell
            markdown_content = markdown.content  # Use .content attribute, not .get()
            if markdown_content:
                markdown_to_word(markdown_content, doc, criteria_cell)
    else:
        print(
            f"ERROR: Document only has {len(doc.tables)} tables, cannot access table 4"
        )


@click.command()
def run_cli():
    """
    CLI tool to generate marking guide Word documents from markdown files.
    """
    marking_guide_generator(COURSE_CONTENT, OUTPUT_LOCATION)


if __name__ == "__main__":
    run_cli()
