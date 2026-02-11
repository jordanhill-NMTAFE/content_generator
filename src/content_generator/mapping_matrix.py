from itertools import chain
import os
from os import environ as env
import click
from docx import Document
from docx.shared import Pt, Inches
from docx.table import Table, _Cell, _Column
from docx.styles.styles import Styles
from docx.styles.style import _ParagraphStyle
from docx.enum.style import WD_STYLE_TYPE, WD_BUILTIN_STYLE as WD_STYLE
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.document import Document as _Document
from docx.shared import Pt
from docx.section import _Header, _Footer, Section, Sections
from docx.text.paragraph import Paragraph
from pathlib import Path
from pandas import DataFrame

from src.utils.markdown import markdown_to_word, parse_md
from src.utils.math import add_tuples
from src.utils.uoc_api import UnitOfCompetency
from docx.enum.text import WD_ALIGN_PARAGRAPH
from frontmatter import Post

from src.utils.uoc_api import UnitOfCompetencyError
from src.content_generator.oo_mapping_matrix import MappingMatrixData

import logging

log = logging.getLogger(__name__)


# normal_bold = _ParagraphStyle()
# normal_bold.font.bold = True

assert "ROOT_DIR" in env, "ROOT_DIR is undefined. This should be set automatically by the gen command."

# Absolute Path of course content folder from env
assert "COURSE_CONTENT" in env, "COURSE_CONTENT is undefined. Create ~/.config/content-generator/.env with COURSE_CONTENT=/path/to/course-content"
assert "OUTPUT_LOCATION" in env, "OUTPUT_LOCATION is undefined. Create ~/.config/content-generator/.env with OUTPUT_LOCATION=/path/to/output"

COURSE_CONTENT = Path(env["COURSE_CONTENT"]).resolve()
OUTPUT_LOCATION = Path(env["OUTPUT_LOCATION"]).resolve()

# Source code locations:
ROOT = env["ROOT_DIR"]  # repo root location
# Templates are located relative to the package, not the working directory
TEMPLATES = Path(__file__).parent.parent / "templates"

# Implementation Specific
TEMPLATE = TEMPLATES / Path("Assessment Mapping Matrix (F122A8).docx")
OUTPUT_FILE = Path("Assessment Mapping Matrix (F122A8).docx")

# Relative Path of Content Files (Input and Output):
ASSESSMENTS = Path("2 KAD/5 Assess Tool/")
MAPPING_MATRIX = Path("2 KAD/7 Assess Mapping Matrix/")


import re
from typing import List, Dict


def parse_markdown_headers(md_content: str) -> List[Dict[str, str]]:
    """
    Parses a Markdown string into an iterable of sections based on Markdown headers.

    :param md_content: A string containing the Markdown content.
    :return: A list of dictionaries with 'header' and 'content' keys.
    """

    # Define a regex to match markdown headers
    header_regex = re.compile(r"^(#{1})\s+(.*)", re.MULTILINE)

    sections = []
    last_pos = 0
    for match in header_regex.finditer(md_content):
        # Extract header level and text
        header_level = len(match.group(1))
        header_text = match.group(2).strip()

        # Find the position of the header
        start_pos = match.start()
        # Get content up to this header
        content = md_content[last_pos:start_pos].strip()

        # If there is a previous section, update its content
        if sections:
            sections[-1]["content"] = content

        # Create a new section for the current header
        section = {"header": header_text, "content": "", "level": header_level}
        sections.append(section)

        last_pos = match.end()

    # Add the content for the last section
    if sections:
        sections[-1]["content"] = md_content[last_pos:].strip()

    return sections


def _find_row_index(table: Table, search_text: str, column: int = 0) -> int | None:
    """Safely find the first row index in *table* whose cell in *column* contains *search_text*.

    Args:
        table: The docx Table to search in.
        search_text: Sub-string to locate in the target column.
        column: Column index to inspect (defaults to the first column).

    Returns:
        The integer row index if found, otherwise ``None``.
    """
    try:
        return next(
            (
                idx
                for idx, cell in enumerate(table.column_cells(column))
                if search_text in (cell.text or "")
            ),
            None,
        )
    except Exception:
        # Unexpected errors should not crash generation; return None so caller can decide.
        return None


def _ensure_rows(table: Table, up_to_row: int) -> None:
    """Ensure *table* has at least ``up_to_row + 1`` rows, appending as required."""
    while len(table.rows) <= up_to_row:
        table.add_row()


def _get_or_create_element_header(table: Table, label: str) -> int:
    """Return the row index for *label* (e.g. "Element 6").

    If it doesn't exist, append a new header row at the end of the table and
    return its index.
    """
    row_index = _find_row_index(table, label)
    if row_index is not None:
        return row_index

    # Header not present – append new row at the bottom.
    row_index = len(table.rows)
    row = table.add_row()
    row.cells[0].text = label
    # Bold the header text to mimic template style (best effort).
    if row.cells[0].paragraphs and row.cells[0].paragraphs[0].runs:
        row.cells[0].paragraphs[0].runs[0].bold = True

    log.info(
        f"Added missing header row '{label}' at index {row_index} to accommodate additional UoC elements."
    )
    return row_index


def _is_row_empty(row) -> bool:
    """Check if *row* has no visible text in any cell."""
    return all((cell.text or "").strip() == "" for cell in row.cells)


def _remove_row(table: Table, row_idx: int) -> None:
    """Delete row *row_idx* from *table* (in-place)."""
    row = table.rows[row_idx]
    tbl = row._tr
    tbl.getparent().remove(tbl)


def _cleanup_unused_rows(table: Table, max_element_idx: int) -> None:
    """Remove completely empty rows from the table.

    Args:
        table: Target docx Table.
        max_element_idx: Highest element number present in the UoC data (unused in simplified version).
    """
    # Iterate bottom-up to avoid index shifts when deleting rows.
    for idx in range(len(table.rows) - 1, -1, -1):
        # Skip the first two header rows (template headings).
        if idx < 2:
            continue

        row = table.rows[idx]

        # Remove completely empty rows.
        if _is_row_empty(row):
            _remove_row(table, idx)


def mapping_matrix(course_directory: Path, output_location: Path):
    assert course_directory.is_dir()
    assert output_location.is_dir()

    assessments = course_directory / ASSESSMENTS
    unit_assessment_mapping = {}

    for assessment in sorted(assessments.rglob("assessment.md")):
        if not assessment.is_file():
            continue

        markdown = parse_md(assessment)
        name = markdown.get("name")
        units = markdown.get("units")

        for unit in units:
            unit_assessment_mapping.setdefault(
                unit["id"],
                {
                    "assessments": [],
                    "unit": unit,
                    "qualification": markdown.get(
                        "qualification_national_code_and_title"
                    ),
                },
            )
            unit_assessment_mapping.get(unit["id"]).get("assessments").append(markdown)

    for unit_index, (id, mapping_matrix) in enumerate(unit_assessment_mapping.items()):
        # Filter assessments: include only those with at least one mapping entry
        original_assessments = mapping_matrix.get("assessments", [])
        valid_assessments = [
            a for a in original_assessments if len(a.get("mapping", [])) > 0
        ]
        excluded_assessments = [
            a for a in original_assessments if a not in valid_assessments
        ]

        if excluded_assessments:
            log.warning(
                f"[assessments] Unit {id}: excluding {len(excluded_assessments)} assessment(s) that contain no mapping questions – "
                + ", ".join(a.get("name", "<unnamed>") for a in excluded_assessments)
            )

        # The docx table template has a fixed number of columns (first is UoC data, the rest are for assessments)
        doc: _Document = Document(ROOT / TEMPLATE)
        table = doc.tables[0]
        max_assessment_columns = (
            len(table.columns) - 1
        )  # subtract the first description column

        if len(valid_assessments) > max_assessment_columns:
            log.warning(
                f"[assessments] Unit {id}: template only provides {max_assessment_columns} assessment columns but {len(valid_assessments)} valid assessments were found. "
                "Only the first set will be included in the matrix. Consider extending the template if you need more columns."
            )
            valid_assessments = valid_assessments[:max_assessment_columns]

        # Replace assessments list in mapping_matrix so subsequent logic only deals with valid ones
        mapping_matrix["assessments"] = valid_assessments

        styles: Styles = doc.styles
        unit = mapping_matrix.get("unit")
        header: _Header = doc.sections[0].header
        table_header: Table = header.tables[0]

        # Set Unit national codes and titles
        cell: _Cell = table_header.cell(1, 1)
        cell.text = f"{unit.get('id')} {unit.get('name')}"

        # Set qualification national codes and titles
        cell: _Cell = table_header.cell(0, 1)
        cell.text = f"{mapping_matrix.get('qualification')}"

        # --- Re-label assessment columns (row 0 = number, row 1 = title) and blank any unused columns ---
        for col_idx in range(max_assessment_columns):
            if col_idx < len(valid_assessments):
                assessment = valid_assessments[col_idx]
                table.cell(0, 1 + col_idx).text = f"Assessment {col_idx + 1}"
                table.cell(1, 1 + col_idx).text = assessment.get("name", "")
            else:
                # Clear header cells for unused columns so they don't appear in the final output.
                table.cell(0, 1 + col_idx).text = ""
                table.cell(1, 1 + col_idx).text = ""
                # Also clear every body cell beneath this column to avoid stale template data.
                for row in table.rows[2:]:
                    row.cells[1 + col_idx].text = ""

        # Build OO mapping data structure using only valid assessments
        try:
            uoc: UnitOfCompetency = UnitOfCompetency(id)
        except UnitOfCompetencyError as e:
            logger.error(f"Skipping mapping matrix for {id}: {e}")
            continue
        assessments = mapping_matrix.get("assessments")
        matrix_data = MappingMatrixData.from_uoc_and_assessments(uoc, assessments, id)

        # --- Clear unused element headers from template ---
        # Template typically has Element 1-6 headers, but we only need what exists in the UoC
        actual_element_count = len(matrix_data.elements)
        element_re = re.compile(r"Element\s+(\d+)", re.IGNORECASE)

        # Clear unused element headers (iterate backwards to avoid index shifts)
        for idx in range(len(table.rows) - 1, -1, -1):
            if idx < 2:  # Skip header rows
                continue
            row = table.rows[idx]
            first_text = (row.cells[0].text or "").strip()
            m = element_re.match(first_text)
            if m:
                element_num = int(m.group(1))
                if element_num > actual_element_count:
                    # Clear the header row
                    for cell in row.cells:
                        cell.text = ""

        # --- Elements & Criteria ---
        criteria_row_idx = 0  # Track which row in the criteria array we're on
        for element_index, element in enumerate(matrix_data.elements):
            search_label = f"Element {element_index + 1}"
            element_header = _get_or_create_element_header(table, search_label)
            for index, criterium in enumerate(element["criteria"]):
                _ensure_rows(table, element_header + 1 + index)
                table.cell(element_header + 1 + index, 0).text = criterium

                # Fill mapping columns using criteria_array
                for assessment_index in range(len(matrix_data.assessments)):
                    question_num = matrix_data.criteria_array[
                        criteria_row_idx, assessment_index
                    ]
                    cell_text = str(question_num) if question_num > 0 else ""
                    table.cell(
                        element_header + 1 + index, 1 + assessment_index
                    ).text = cell_text

                criteria_row_idx += 1  # Move to next row in criteria array

        # --- Knowledge Evidence ---
        knowledge_header = _find_row_index(
            table, "Required Knowledge or Knowledge Evidence"
        )
        if knowledge_header is not None:
            needed_rows = len(matrix_data.knowledge_evidence)
            # Insert rows directly after the knowledge header if not enough exist
            for i in range(needed_rows):
                target_row = knowledge_header + 1 + i
                if len(table.rows) <= target_row:
                    # Insert after the header row
                    table.add_row()
                    # Move the new row to the correct position (after header)
                    row = table.rows[-1]
                    tbl = table._tbl
                    tbl.remove(row._tr)
                    tbl.insert(target_row, row._tr)
            for index, knowledge in enumerate(matrix_data.knowledge_evidence):
                cell = table.cell(knowledge_header + 1 + index, 0)
                cell.text = knowledge["element"]
                if cell.paragraphs and cell.paragraphs[0].runs:
                    cell.paragraphs[0].runs[0].bold = True
                subelements = knowledge["subelements"]
                if isinstance(subelements, dict) and len(subelements) > 0:
                    for sub_element, nested in subelements.items():
                        paragraph = cell.add_paragraph()
                        paragraph.paragraph_format.left_indent = Pt(18)
                        paragraph.paragraph_format.space_after = Pt(0)
                        paragraph.add_run(sub_element)
                        if isinstance(nested, dict) and len(nested) > 0:
                            for nested_item in nested:
                                nested_paragraph = cell.add_paragraph()
                                nested_paragraph.paragraph_format.left_indent = Pt(36)
                                nested_paragraph.paragraph_format.space_after = Pt(0)
                                nested_paragraph.add_run(nested_item)
                elif isinstance(subelements, (list, set)) and len(subelements) > 0:
                    for sub_element in subelements:
                        paragraph = cell.add_paragraph()
                        paragraph.paragraph_format.left_indent = Pt(18)
                        paragraph.paragraph_format.space_after = Pt(0)
                        paragraph.add_run(sub_element)
                # Fill mapping columns using knowledge_array
                for assessment_index in range(len(matrix_data.assessments)):
                    question_num = matrix_data.knowledge_array[index, assessment_index]
                    cell_text = str(question_num) if question_num > 0 else ""
                    table.cell(
                        knowledge_header + 1 + index, 1 + assessment_index
                    ).text = cell_text

        # --- Performance Evidence ---
        performance_header = _find_row_index(
            table, "Required Skills or Performance Evidence"
        )
        if performance_header is not None:
            counter = 0
            for index, performance in enumerate(matrix_data.performance_evidence):
                _ensure_rows(table, performance_header + 1 + index + counter)
                cell = table.cell(performance_header + 1 + index + counter, 0)
                cell.text = performance["element"]
                if ":" in cell.text and cell.paragraphs and cell.paragraphs[0].runs:
                    cell.paragraphs[0].runs[0].bold = True
                subelements = performance["subelements"]
                if len(subelements) > 0:
                    for sub_element, indented_elements in subelements.items():
                        counter += 1
                        _ensure_rows(table, performance_header + 1 + index + counter)
                        cell = table.cell(performance_header + 1 + index + counter, 0)
                        cell.text = sub_element
                        for indented_element in indented_elements:
                            paragraph = cell.add_paragraph()
                            paragraph.paragraph_format.left_indent = Inches(0.5)
                            paragraph.paragraph_format.space_after = Pt(0)
                            paragraph.add_run(indented_element)

                # Fill mapping columns using performance_array
                for assessment_index in range(len(matrix_data.assessments)):
                    question_num = matrix_data.performance_array[
                        index, assessment_index
                    ]
                    cell_text = str(question_num) if question_num > 0 else ""
                    table.cell(
                        performance_header + 1 + index + counter, 1 + assessment_index
                    ).text = cell_text

        # --- Assessment Conditions ---
        ac_header = _find_row_index(table, "Assessment Conditions")
        if ac_header is not None:
            for index, ac in enumerate(matrix_data.assessment_conditions):
                row_index = ac_header + 1 + index
                _ensure_rows(table, row_index)
                cell = table.cell(row_index, 0)
                cell.text = ac["element"]
                if ":" in cell.text:
                    cell.paragraphs[0].runs[0].bold = True
                subelements = ac["subelements"]
                if len(subelements) > 0:
                    for sub_element in subelements:
                        paragraph = cell.add_paragraph()
                        paragraph.paragraph_format.left_indent = Inches(0.5)
                        paragraph.paragraph_format.space_after = Pt(0)
                        paragraph.add_run(sub_element)
                cell = table.cell(row_index, 1)
                for other_cell in (
                    table.cell(row_index, idx) for idx in range(2, len(table.columns))
                ):
                    cell.merge(other_cell)

        # --- Cleanup empty rows only ---
        _cleanup_unused_rows(table, len(matrix_data.elements))

        output: Path = output_location / MAPPING_MATRIX / (id + " " + str(OUTPUT_FILE))
        output.parent.mkdir(exist_ok=True, parents=True)
        doc.save(output)


@click.command()
# @click.argument("course_directory", type=click.Path(exists=True, path_type=Path))
def run_cli():
    """
    CLI tool to write YAML header data from Markdown file to Word document as custom properties.
    """
    mapping_matrix(COURSE_CONTENT, OUTPUT_LOCATION)


if __name__ == "__main__":
    run_cli()
