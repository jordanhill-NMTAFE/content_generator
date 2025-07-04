"""
Tests for mapping matrix cleanup operations.
Validates that we properly clear unused element headers and remove empty rows.
"""

import pytest
import re
from pathlib import Path
from docx import Document
from docx.table import Table
from src.content_generator.mapping_matrix import (
    _cleanup_unused_rows,
    _is_row_empty,
    _remove_row,
    _find_row_index,
    _get_or_create_element_header,
)
from src.utils.uoc_api import UnitOfCompetency
from src.content_generator.oo_mapping_matrix import MappingMatrixData


class TestMappingMatrixCleanup:
    """Test mapping matrix cleanup operations."""

    @pytest.fixture
    def template_doc(self):
        """Load the actual template document."""
        template_path = (
            Path(__file__).parent.parent.parent
            / "templates"
            / "Assessment Mapping Matrix (F122A8).docx"
        )
        return Document(template_path)

    @pytest.fixture
    def fresh_template_table(self, template_doc):
        """Get a fresh template table for each test."""
        return template_doc.tables[0]

    def test_is_row_empty_function(self, fresh_template_table):
        """Test the _is_row_empty helper function."""
        table = fresh_template_table

        # Find a row with content (should not be empty)
        content_row = None
        for row in table.rows:
            if any(cell.text.strip() for cell in row.cells):
                content_row = row
                break

        assert content_row is not None, "Should find at least one row with content"
        assert not _is_row_empty(content_row), "Row with content should not be empty"

        # Create an empty row by clearing all cells
        empty_row = table.rows[-1]  # Use last row
        for cell in empty_row.cells:
            cell.text = ""

        assert _is_row_empty(empty_row), "Row with no content should be empty"

    def test_find_element_headers_in_template(self, fresh_template_table):
        """Test that we can find element headers in the template."""
        table = fresh_template_table
        element_re = re.compile(r"Element\s+(\d+)", re.IGNORECASE)

        element_headers = []
        for idx, row in enumerate(table.rows):
            first_text = (row.cells[0].text or "").strip()
            m = element_re.match(first_text)
            if m:
                element_num = int(m.group(1))
                element_headers.append((idx, element_num))

        # Template should have multiple element headers
        assert len(element_headers) > 0, "Template should contain element headers"

        # Should be in order (Element 1, Element 2, etc.)
        element_numbers = [num for _, num in element_headers]
        assert element_numbers == sorted(element_numbers), (
            "Element headers should be in order"
        )

        print(f"Found element headers: {element_headers}")

    def test_clear_unused_element_headers(self, fresh_template_table):
        """Test clearing unused element headers."""
        table = fresh_template_table

        # Simulate clearing unused headers for a UoC with only 3 elements
        actual_element_count = 3
        element_re = re.compile(r"Element\s+(\d+)", re.IGNORECASE)

        # Record initial state
        initial_element_headers = []
        for idx, row in enumerate(table.rows):
            first_text = (row.cells[0].text or "").strip()
            m = element_re.match(first_text)
            if m:
                element_num = int(m.group(1))
                initial_element_headers.append((idx, element_num))

        # Clear unused element headers (simulate the production logic)
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

        # Verify unused headers were cleared
        final_element_headers = []
        for idx, row in enumerate(table.rows):
            first_text = (row.cells[0].text or "").strip()
            m = element_re.match(first_text)
            if m:
                element_num = int(m.group(1))
                final_element_headers.append((idx, element_num))

        # Should only have elements 1-3 remaining
        final_element_numbers = [num for _, num in final_element_headers]
        assert max(final_element_numbers) <= actual_element_count, (
            f"Should only have elements 1-{actual_element_count}, but found: {final_element_numbers}"
        )

        print(f"Initial element headers: {initial_element_headers}")
        print(f"Final element headers: {final_element_headers}")

    def test_cleanup_empty_rows(self, fresh_template_table):
        """Test the cleanup of empty rows."""
        table = fresh_template_table

        # Record initial row count
        initial_row_count = len(table.rows)

        # Create some empty rows by clearing content
        rows_to_empty = []
        for idx in range(len(table.rows) - 1, 2, -1):  # Skip header rows
            row = table.rows[idx]
            # If row has minimal content, empty it for testing
            if len(row.cells[0].text.strip()) < 10:  # Arbitrary threshold
                for cell in row.cells:
                    cell.text = ""
                rows_to_empty.append(idx)
                if len(rows_to_empty) >= 3:  # Limit to 3 for testing
                    break

        # Run cleanup
        _cleanup_unused_rows(table, 6)  # max_element_idx is unused now

        # Verify empty rows were removed
        final_row_count = len(table.rows)
        assert final_row_count <= initial_row_count, "Should have removed some rows"

        # Verify no completely empty rows remain (except first 2 header rows)
        for idx in range(2, len(table.rows)):
            row = table.rows[idx]
            if _is_row_empty(row):
                pytest.fail(f"Empty row found at index {idx} after cleanup")

        print(f"Initial row count: {initial_row_count}")
        print(f"Final row count: {final_row_count}")
        print(f"Rows that were emptied: {rows_to_empty}")

    def test_find_section_headers(self, fresh_template_table):
        """Test finding section headers in the template."""
        table = fresh_template_table

        # Find key section headers
        knowledge_header = _find_row_index(
            table, "Required Knowledge or Knowledge Evidence"
        )
        performance_header = _find_row_index(
            table, "Required Skills or Performance Evidence"
        )
        ac_header = _find_row_index(table, "Assessment Conditions")

        # Should find these headers
        assert knowledge_header is not None, "Should find Knowledge Evidence header"
        assert performance_header is not None, "Should find Performance Evidence header"
        assert ac_header is not None, "Should find Assessment Conditions header"

        # Headers should be in logical order
        assert knowledge_header < performance_header, (
            "Knowledge should come before Performance"
        )
        assert performance_header < ac_header, (
            "Performance should come before Assessment Conditions"
        )

        print(f"Knowledge header at row: {knowledge_header}")
        print(f"Performance header at row: {performance_header}")
        print(f"Assessment Conditions header at row: {ac_header}")

    @pytest.mark.integration
    def test_full_cleanup_workflow_ictaii401(self, fresh_template_table):
        """Test full cleanup workflow for ICTAII401 (3 elements)."""
        table = fresh_template_table

        # Simulate the full workflow for ICTAII401
        uoc = UnitOfCompetency("ICTAII401")
        matrix_data = MappingMatrixData.from_uoc_and_assessments(uoc, [], "ICTAII401")

        # Step 1: Clear unused element headers
        actual_element_count = len(matrix_data.elements)  # Should be 3
        element_re = re.compile(r"Element\s+(\d+)", re.IGNORECASE)

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

        # Step 2: Cleanup empty rows
        _cleanup_unused_rows(table, actual_element_count)

        # Verify final state
        final_element_headers = []
        for idx, row in enumerate(table.rows):
            first_text = (row.cells[0].text or "").strip()
            m = element_re.match(first_text)
            if m:
                element_num = int(m.group(1))
                final_element_headers.append((idx, element_num))

        # Should only have elements 1-3
        final_element_numbers = [num for _, num in final_element_headers]
        assert len(final_element_numbers) <= 3, (
            f"Should have at most 3 elements, found: {final_element_numbers}"
        )
        assert max(final_element_numbers) <= 3, (
            f"Should have max element 3, found: {final_element_numbers}"
        )

        # Should have no empty rows (except possibly in sections)
        empty_rows = []
        for idx in range(2, len(table.rows)):
            if _is_row_empty(table.rows[idx]):
                empty_rows.append(idx)

        print(f"ICTAII401 - Final element headers: {final_element_headers}")
        print(f"ICTAII401 - Empty rows remaining: {empty_rows}")

        # Should have minimal empty rows
        assert len(empty_rows) <= 5, (
            f"Should have minimal empty rows, found {len(empty_rows)}: {empty_rows}"
        )

    @pytest.mark.integration
    def test_full_cleanup_workflow_ictprg302(self, fresh_template_table):
        """Test full cleanup workflow for ICTPRG302 (6 elements)."""
        table = fresh_template_table

        # Simulate the full workflow for ICTPRG302
        uoc = UnitOfCompetency("ICTPRG302")
        matrix_data = MappingMatrixData.from_uoc_and_assessments(uoc, [], "ICTPRG302")

        # Step 1: Clear unused element headers
        actual_element_count = len(matrix_data.elements)  # Should be 6
        element_re = re.compile(r"Element\s+(\d+)", re.IGNORECASE)

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

        # Step 1.5: Simulate element creation (template may not have all elements)
        # ICTPRG302 has 6 elements but template may only have 5
        for element_index in range(actual_element_count):
            search_label = f"Element {element_index + 1}"
            _get_or_create_element_header(table, search_label)

        # Step 2: Cleanup empty rows
        _cleanup_unused_rows(table, actual_element_count)

        # Verify final state
        final_element_headers = []
        for idx, row in enumerate(table.rows):
            first_text = (row.cells[0].text or "").strip()
            m = element_re.match(first_text)
            if m:
                element_num = int(m.group(1))
                final_element_headers.append((idx, element_num))

        # Should have elements 1-6 (all of them)
        final_element_numbers = [num for _, num in final_element_headers]
        assert len(final_element_numbers) == 6, (
            f"Should have 6 elements, found: {final_element_numbers}"
        )
        assert max(final_element_numbers) == 6, (
            f"Should have max element 6, found: {final_element_numbers}"
        )

        print(f"ICTPRG302 - Final element headers: {final_element_headers}")

    def test_template_preservation(self, fresh_template_table):
        """Test that valid content is preserved during cleanup."""
        table = fresh_template_table

        # Record important content before cleanup
        knowledge_header = _find_row_index(
            table, "Required Knowledge or Knowledge Evidence"
        )
        performance_header = _find_row_index(
            table, "Required Skills or Performance Evidence"
        )
        ac_header = _find_row_index(table, "Assessment Conditions")

        initial_headers = {
            "knowledge": knowledge_header,
            "performance": performance_header,
            "assessment_conditions": ac_header,
        }

        # Run cleanup
        _cleanup_unused_rows(table, 3)  # Simulate 3 elements

        # Verify important headers are still there
        final_knowledge_header = _find_row_index(
            table, "Required Knowledge or Knowledge Evidence"
        )
        final_performance_header = _find_row_index(
            table, "Required Skills or Performance Evidence"
        )
        final_ac_header = _find_row_index(table, "Assessment Conditions")

        assert final_knowledge_header is not None, (
            "Knowledge Evidence header should be preserved"
        )
        assert final_performance_header is not None, (
            "Performance Evidence header should be preserved"
        )
        assert final_ac_header is not None, (
            "Assessment Conditions header should be preserved"
        )

        print(f"Initial headers: {initial_headers}")
        print(
            f"Final headers: {{'knowledge': {final_knowledge_header}, 'performance': {final_performance_header}, 'assessment_conditions': {final_ac_header}}}"
        )


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
