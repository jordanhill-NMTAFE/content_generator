from pathlib import Path
from markdown_it import MarkdownIt
from markdown_it.token import Token
from docx import Document
from docx.document import Document as _Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.shared import qn
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph
from docx.enum.style import WD_STYLE_TYPE
from docx.table import Table
import frontmatter
import re
from bs4 import BeautifulSoup  # Import for HTML parsing
import sys


def apply_table_cell_padding(
    table: Table, top_padding: float = 0.5, bottom_padding: float = 0.5
):
    """
    Apply padding to all cells in a table.

    :param table: The table to apply padding to
    :param top_padding: Top padding in points (default: 0.5)
    :param bottom_padding: Bottom padding in points (default: 0.5)
    """
    for row in table.rows:
        for cell in row.cells:
            # Apply top and bottom padding to the cell
            cell.vertical_alignment = WD_ALIGN_PARAGRAPH.CENTER
            # Set cell margins using the cell's paragraph format
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_before = Pt(top_padding)
                paragraph.paragraph_format.space_after = Pt(bottom_padding)


MARKDOWN_STYLES = {
    "h1": {"regex": re.compile(r"^#{1} (.*)", re.MULTILINE), "style": "Heading 1"},
    "h2": {"regex": re.compile(r"^#{2} (.*)", re.MULTILINE), "style": "Heading 2"},
    "h3": {"regex": re.compile(r"^#{3} (.*)", re.MULTILINE), "style": "Heading 3"},
    "h4": {"regex": re.compile(r"^#{4} (.*)", re.MULTILINE), "style": "Heading 4"},
    "h5": {"regex": re.compile(r"^#{5} (.*)", re.MULTILINE), "style": "Heading 5"},
    "h6": {"regex": re.compile(r"^#{6} (.*)", re.MULTILINE), "style": "Heading 6"},
    "bold/italic": {
        "regex": re.compile(r"(\*{1,2})([^*]*?)(\*{1,2})"),
        "style": "bold/italic",
    },
    "code": {"regex": re.compile(r"`{3}([^`]*)`{3}"), "style": "code"},
    "bullets": {
        "regex": re.compile(r"^([' ',\t]*)[*\-+]\s(.*)$", re.MULTILINE),
        "style": "List Bullet",
    },
    # "numbers": {
    #     "regex": re.compile(r"^([' ',\t]*)\d{1,}\.\s(.*)$", re.MULTILINE),
    #     "style": "List Number",
    # },
    "link": {"regex": re.compile(r"(?<!!)\[(.*)\]\((.*)\)")},
    "image": {"regex": re.compile(r"!\[(.*)\]\((.*)\)")},
    "linebreak": {"regex": re.compile(r"^\-{3}$", re.MULTILINE)},
    # Add more patterns if needed, like lists, links, etc.
}


def ensure_markdown_styles(document: Document):
    """
    Ensure all required markdown styles exist in the document with sensible defaults.
    Creates custom styles with 'MD ' prefix to avoid modifying existing document styles.

    :param document: docx Document object to enhance
    """
    styles = document.styles

    # Create custom Heading styles with 'MD ' prefix to avoid conflicts
    for level in range(1, 7):
        custom_heading_style_name = f"MD Heading {level}"

        # Only create if it doesn't exist - never modify existing styles
        if custom_heading_style_name not in styles:
            try:
                heading_style = styles.add_style(
                    custom_heading_style_name, WD_STYLE_TYPE.PARAGRAPH
                )

                # Apply consistent heading formatting
                font = heading_style.font
                if level == 1:
                    font.size = Pt(18)
                    font.bold = True
                    font.color.rgb = RGBColor(0x2F, 0x5F, 0x8F)  # Dark blue
                elif level == 2:
                    font.size = Pt(16)
                    font.bold = True
                    font.color.rgb = RGBColor(0x1F, 0x4F, 0x7F)  # Darker blue
                elif level == 3:
                    font.size = Pt(14)
                    font.bold = True
                    font.color.rgb = RGBColor(0x0F, 0x3F, 0x6F)  # Even darker blue
                elif level == 4:
                    font.size = Pt(12)
                    font.bold = True
                    font.color.rgb = RGBColor(0x4F, 0x4F, 0x4F)  # Dark gray
                else:
                    font.size = Pt(11)
                    font.bold = True
                    font.color.rgb = RGBColor(0x6F, 0x6F, 0x6F)  # Medium gray

                # Add proper spacing
                heading_style.paragraph_format.space_before = Pt(12)
                heading_style.paragraph_format.space_after = Pt(6)

            except Exception:
                continue  # Style creation failed, skip

    # Create custom Normal paragraph style for markdown content
    if "MD Normal" not in styles:
        try:
            normal_style = styles.add_style("MD Normal", WD_STYLE_TYPE.PARAGRAPH)
            font = normal_style.font
            font.name = "Calibri"
            font.size = Pt(11)
            normal_style.paragraph_format.space_after = Pt(6)
            normal_style.paragraph_format.line_spacing = 1.15
        except Exception:
            pass

    # Create our custom Markdown Text style for predictable formatting
    if "MD Text" not in styles:
        try:
            markdown_text_style = styles.add_style("MD Text", WD_STYLE_TYPE.PARAGRAPH)
            font = markdown_text_style.font
            font.name = "Calibri"
            font.size = Pt(11)
            font.color.rgb = RGBColor(0x00, 0x00, 0x00)  # Pure black text

            # Clean paragraph formatting
            markdown_text_style.paragraph_format.space_after = Pt(6)
            markdown_text_style.paragraph_format.line_spacing = 1.15
            markdown_text_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
            markdown_text_style.paragraph_format.left_indent = Pt(0)
            markdown_text_style.paragraph_format.right_indent = Pt(0)
            markdown_text_style.paragraph_format.first_line_indent = Pt(0)
        except Exception:
            pass

    # Create dedicated custom Blockquote style
    if "MD Blockquote" not in styles:
        try:
            blockquote_style = styles.add_style(
                "MD Blockquote", WD_STYLE_TYPE.PARAGRAPH
            )
            font = blockquote_style.font
            font.name = "Calibri"
            font.size = Pt(10)
            font.italic = True
            font.color.rgb = RGBColor(0x40, 0x40, 0x40)  # Dark gray

            # Add indentation and FORCE left alignment
            blockquote_style.paragraph_format.left_indent = Pt(18)
            blockquote_style.paragraph_format.right_indent = Pt(18)
            blockquote_style.paragraph_format.space_before = Pt(6)
            blockquote_style.paragraph_format.space_after = Pt(6)
            blockquote_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        except Exception:
            pass

    # Create custom Code Block style
    if "MD Code Block" not in styles:
        try:
            code_style = styles.add_style("MD Code Block", WD_STYLE_TYPE.PARAGRAPH)
            font = code_style.font
            font.name = "Consolas"  # Better monospace font
            font.size = Pt(9)
            font.color.rgb = RGBColor(0x00, 0x00, 0x00)  # Black text

            # Code block styling
            code_style.paragraph_format.left_indent = Pt(18)
            code_style.paragraph_format.right_indent = Pt(18)
            code_style.paragraph_format.space_before = Pt(6)
            code_style.paragraph_format.space_after = Pt(6)
            code_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
            code_style.paragraph_format.line_spacing = (
                1.0  # Tighter line spacing for code
            )
        except Exception:
            pass

    # Create custom List Bullet styles (including nested levels)
    bullet_styles = ["MD List Bullet", "MD List Bullet 2", "MD List Bullet 3"]
    for i, style_name in enumerate(bullet_styles):
        if style_name not in styles:
            try:
                bullet_style = styles.add_style(style_name, WD_STYLE_TYPE.PARAGRAPH)
                font = bullet_style.font
                font.name = "Calibri"
                font.size = Pt(11)
                bullet_style.paragraph_format.space_after = Pt(3)
                # Increase indentation for nested levels
                bullet_style.paragraph_format.left_indent = Pt(18 + (i * 18))
            except Exception:
                pass

    # Create custom List Number styles (including nested levels)
    number_styles = ["MD List Number", "MD List Number 2", "MD List Number 3"]
    for i, style_name in enumerate(number_styles):
        if style_name not in styles:
            try:
                number_style = styles.add_style(style_name, WD_STYLE_TYPE.PARAGRAPH)
                font = number_style.font
                font.name = "Calibri"
                font.size = Pt(11)
                number_style.paragraph_format.space_after = Pt(3)
                # Increase indentation for nested levels
                number_style.paragraph_format.left_indent = Pt(18 + (i * 18))
            except Exception:
                pass


def parse_md(path: Path) -> frontmatter.Post:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Path is not a file: {path}")

    # Load the markdown file and parse the front matter
    with open(path, "r", encoding="utf-8") as file:
        parsed_md = frontmatter.load(file)
        # Remove HTML comments
        parsed_md.content = re.sub(
            r"<!--.*?-->", "", parsed_md.content, flags=re.DOTALL
        )
    return parsed_md


def markdown_to_word(doc_content: str, document: Document, parent=None):
    """
    Parse the given Markdown content and apply styles to a Word document or a specified parent container.

    :param doc_content: String containing Markdown content.
    :param document: docx Document object.
    :param parent: Optional. Parent container such as a table cell in the document.
                   If none is provided, new paragraphs are added to the document.
    """
    # Ensure all required markdown styles exist with sensible defaults
    ensure_markdown_styles(document)

    md = MarkdownIt().enable("html_block").enable("html_inline").enable("table")
    tokens = md.parse(doc_content)
    process_tokens(tokens, document, parent)


def process_tokens(tokens: list, document: Document, parent=None):
    """
    Process parsed markdown tokens and build the Word document accordingly.

    :param tokens: List of tokens parsed by markdown_it.
    :param document: docx Document object.
    :param parent: Optional parent container.
    """
    list_style_stack = []
    current_paragraph = None
    in_blockquote = False  # Track if we're inside a blockquote

    # Table state tracking
    in_table = False
    in_thead = False
    table_data = []  # List of rows, each row is a list of cells
    current_row = []
    current_cell_content = []
    is_header_cell = False

    for token in tokens:
        if token.type == "heading_open":
            level = int(token.tag[1])
            style = f"MD Heading {level}"
            current_paragraph = add_paragraph(document, parent, style=style)
            list_style_stack.clear()
        elif token.type == "heading_close":
            current_paragraph = None

        elif token.type == "paragraph_open":
            if len(list_style_stack) > 0:
                continue
            # Use Blockquote style if we're inside a blockquote, otherwise use our Markdown Text style
            style = "MD Blockquote" if in_blockquote else "MD Text"
            current_paragraph = add_paragraph(document, parent, style=style)
            # Ensure left alignment for blockquote paragraphs
            if in_blockquote and current_paragraph:
                current_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        elif token.type == "paragraph_close":
            if len(list_style_stack) > 0:
                continue
            current_paragraph = None
        elif token.type == "inline":
            # Skip if we're inside a table - table inline content is handled separately
            if in_table:
                cell_text = get_inline_text(token.children)
                current_cell_content.append(cell_text)
                continue
            if current_paragraph is None:
                # Use Blockquote style if we're inside a blockquote, otherwise use our Markdown Text style
                style = "MD Blockquote" if in_blockquote else "MD Text"
                current_paragraph = add_paragraph(document, parent, style=style)
                # Ensure left alignment for blockquote paragraphs
                if in_blockquote and current_paragraph:
                    current_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            process_inline(token.children, current_paragraph)
        elif token.type == "fence":
            # Code block - use "MD Code Block" style if available, otherwise "Quote"
            code_style = (
                "MD Code Block" if "MD Code Block" in document.styles else "Quote"
            )
            current_paragraph = add_paragraph(document, parent, style=code_style)
            run = current_paragraph.add_run(token.content)
            # Only set font properties and alignment if using fallback Quote style
            if code_style == "Quote":
                run.font.name = "Courier New"
                run.font.size = Pt(10)
                # Ensure left alignment for code blocks using Quote style
                if current_paragraph:
                    current_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        elif token.type == "bullet_list_open":
            list_style_stack.append("MD List Bullet")
        elif token.type == "ordered_list_open":
            list_style_stack.append("MD List Number")
        elif token.type == "bullet_list_close" or token.type == "ordered_list_close":
            if list_style_stack:
                list_style_stack.pop()
        elif token.type == "list_item_open":
            # Handle nested lists by checking the nesting level
            nesting_level = token.level if hasattr(token, "level") else 0
            style = list_style_stack[-1] if list_style_stack else None

            # For nested lists, we need to adjust the style
            if style and nesting_level > 0:
                if style == "MD List Bullet":
                    # Use different bullet styles for different levels
                    nested_styles = [
                        "MD List Bullet",
                        "MD List Bullet 2",
                        "MD List Bullet 3",
                    ]
                    target_style = nested_styles[
                        min(nesting_level, len(nested_styles) - 1)
                    ]
                    # Fall back to base style if nested style doesn't exist
                    style = (
                        target_style
                        if target_style in document.styles
                        else "MD List Bullet"
                    )
                elif style == "MD List Number":
                    # Use different number styles for different levels
                    nested_styles = [
                        "MD List Number",
                        "MD List Number 2",
                        "MD List Number 3",
                    ]
                    target_style = nested_styles[
                        min(nesting_level, len(nested_styles) - 1)
                    ]
                    # Fall back to base style if nested style doesn't exist
                    style = (
                        target_style
                        if target_style in document.styles
                        else "MD List Number"
                    )

            current_paragraph = add_paragraph(document, parent, style=style)
        elif token.type == "list_item_close":
            current_paragraph = None
        elif token.type == "html_inline" or token.type == "html_block":
            # Handle HTML content
            process_html(token.content, document, parent)
        elif token.type == "blockquote_open":
            # Set blockquote state first
            in_blockquote = True
            # Use "MD Blockquote" style if available, otherwise fall back to "Quote"
            blockquote_style = (
                "MD Blockquote" if "MD Blockquote" in document.styles else "Quote"
            )
            current_paragraph = add_paragraph(document, parent, style=blockquote_style)
            # Explicitly set left alignment for blockquotes
            if current_paragraph:
                current_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        elif token.type == "blockquote_close":
            current_paragraph = None
            in_blockquote = False
        elif token.type == "hr":
            # Render horizontal rule as a paragraph with a bottom border
            hr_paragraph = add_paragraph(document, parent)
            hr_paragraph.paragraph_format.space_before = Pt(6)
            hr_paragraph.paragraph_format.space_after = Pt(6)
            # Add a bottom border to simulate a horizontal line
            pPr = hr_paragraph._p.get_or_add_pPr()
            pBdr = OxmlElement('w:pBdr')
            bottom = OxmlElement('w:bottom')
            bottom.set(qn('w:val'), 'single')
            bottom.set(qn('w:sz'), '6')  # Line thickness
            bottom.set(qn('w:space'), '1')
            bottom.set(qn('w:color'), 'CCCCCC')  # Light gray color
            pBdr.append(bottom)
            pPr.append(pBdr)
            current_paragraph = None
        elif token.type == "code_block":
            # Handle indented code blocks - use "MD Code Block" style if available, otherwise "Quote"
            code_style = (
                "MD Code Block" if "MD Code Block" in document.styles else "Quote"
            )
            current_paragraph = add_paragraph(document, parent, style=code_style)
            run = current_paragraph.add_run(token.content)
            # Only set font properties and alignment if using fallback Quote style
            if code_style == "Quote":
                run.font.name = "Courier New"
                run.font.size = Pt(10)
                # Ensure left alignment for code blocks using Quote style
                if current_paragraph:
                    current_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT

        # Markdown table handling
        elif token.type == "table_open":
            in_table = True
            table_data = []
            current_row = []
        elif token.type == "table_close":
            in_table = False
            # Create Word table from collected data
            if table_data:
                add_table_from_markdown(table_data, document if parent is None else parent)
            table_data = []
        elif token.type == "thead_open":
            in_thead = True
        elif token.type == "thead_close":
            in_thead = False
        elif token.type == "tbody_open":
            pass  # Just continue processing
        elif token.type == "tbody_close":
            pass  # Just continue processing
        elif token.type == "tr_open":
            current_row = []
        elif token.type == "tr_close":
            if current_row:
                table_data.append({"cells": current_row, "is_header": in_thead})
            current_row = []
        elif token.type == "th_open":
            is_header_cell = True
            current_cell_content = []
        elif token.type == "th_close":
            current_row.append({"content": "".join(current_cell_content), "is_header": True})
            current_cell_content = []
            is_header_cell = False
        elif token.type == "td_open":
            is_header_cell = False
            current_cell_content = []
        elif token.type == "td_close":
            current_row.append({"content": "".join(current_cell_content), "is_header": False})
            current_cell_content = []

        else:
            # Handle other token types if necessary
            pass


def get_inline_text(tokens: list) -> str:
    """
    Extract plain text from inline tokens.

    :param tokens: List of inline tokens.
    :return: Plain text string.
    """
    text_parts = []
    for token in tokens:
        if token.type == "text":
            text_parts.append(token.content)
        elif token.type == "code_inline":
            text_parts.append(token.content)
        elif token.type == "softbreak" or token.type == "hardbreak":
            text_parts.append(" ")
        elif hasattr(token, "children") and token.children:
            text_parts.append(get_inline_text(token.children))
    return "".join(text_parts)


def add_table_from_markdown(table_data: list, target):
    """
    Create a Word table from markdown table data.

    :param table_data: List of row dictionaries with 'cells' and 'is_header' keys.
    :param target: Document or cell to add the table to.
    """
    if not table_data:
        return

    # Calculate dimensions
    num_rows = len(table_data)
    num_cols = max(len(row["cells"]) for row in table_data) if table_data else 0

    if num_rows == 0 or num_cols == 0:
        return

    # Create the table
    table = target.add_table(rows=num_rows, cols=num_cols)
    table.style = "Table Grid"

    # Apply padding to all cells
    apply_table_cell_padding(table)

    # Populate the table
    for row_idx, row_data in enumerate(table_data):
        for col_idx, cell_data in enumerate(row_data["cells"]):
            if col_idx < num_cols:
                cell = table.cell(row_idx, col_idx)
                cell.text = cell_data["content"]

                # Apply bold formatting for header cells
                if cell_data["is_header"] or row_data["is_header"]:
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.bold = True


def process_inline(tokens: list, paragraph: Paragraph):
    """
    Process inline tokens within a paragraph.

    :param tokens: List of inline tokens.
    :param paragraph: The current paragraph object.
    """
    bold = False
    italic = False
    skip = False

    for i, token in enumerate(tokens):
        if skip:
            skip = False
            continue
        if token.type == "text":
            # Split content by newlines and handle each part
            content_parts = token.content.split("\n")

            for j, part in enumerate(content_parts):
                if j > 0:
                    # Add a line break for each newline in the original text
                    paragraph.add_run().add_break()

                # Add run even for empty parts to preserve spacing
                run = paragraph.add_run(part)
                if bold:
                    run.bold = True
                if italic:
                    run.italic = True
        elif token.type == "code_inline":
            run = paragraph.add_run(token.content)
            run.font.name = "Courier New"
            run.font.size = Pt(10)
        elif token.type == "strong_open":
            bold = True
        elif token.type == "strong_close":
            bold = False
        elif token.type == "em_open":
            italic = True
        elif token.type == "em_close":
            italic = False
        elif token.type == "link_open":
            href = dict(token.attrs).get("href", "")
            # Collect text inside the link
            link_text = ""
            if tokens[i + 1].type == "text":
                link_text = tokens[i + 1].content
                skip = True
            else:
                link_text = href
            add_hyperlink(paragraph, link_text, href)
        elif token.type == "image":
            src = dict(token.attrs).get("src", "")
            alt = dict(token.attrs).get("alt", "")
            try:
                paragraph.add_run().add_picture(src)
            except Exception:
                paragraph.add_run(alt)
        elif token.type == "softbreak":
            # Handle soft line breaks (single newlines within paragraphs)
            paragraph.add_run().add_break()
        elif token.type == "hardbreak":
            # Handle hard line breaks (two spaces + newline in markdown)
            paragraph.add_run().add_break()
        elif token.type == "html_inline":
            # Process inline HTML
            process_html(token.content, document=paragraph.part, parent=paragraph)
        else:
            # Handle other inline tokens if necessary
            pass


def add_paragraph(document: Document, parent=None, style=None) -> Paragraph:
    """
    Add a paragraph to the document or parent container.

    :param document: docx Document object.
    :param parent: Optional parent container.
    :param style: Style of the paragraph.
    :return: The newly added Paragraph object.
    """
    if parent is None:
        return document.add_paragraph(style=style)
    else:
        # if len(parent.paragraphs) > 0 and (
        #     parent.paragraphs[-1].style == style or style is None
        # ):
        #     return parent.paragraphs[-1]
        return parent.add_paragraph(style=style)


def empty_paragraph(document: Document, parent=None, style=None) -> Paragraph:
    """
    Add a paragraph to the document or parent container.

    :param document: docx Document object.
    :param parent: Optional parent container.
    :param style: Style of the paragraph.
    :return: The newly added Paragraph object.
    """
    if parent is None:
        return document.add_paragraph(style=style)
    else:
        return parent.add_paragraph(style=style)


def process_html(html_content: str, document: Document, parent=None):
    """
    Process HTML content and add it to the document.

    :param html_content: HTML content as a string.
    :param document: docx Document object.
    :param parent: Optional parent container.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    handle_html_elements(soup, document, parent)


def handle_html_elements(element, document: Document, parent=None):
    """
    Recursively handle HTML elements and add them to the document.

    :param element: BeautifulSoup element or NavigableString.
    :param document: docx Document object.
    :param parent: Optional parent container (e.g., Paragraph, _Cell, Run).
    """
    from docx.table import _Cell
    from docx.text.paragraph import Paragraph
    from docx.text.run import Run

    if isinstance(element, str):
        # Handle text content
        if parent is None:
            paragraph = add_paragraph(document)
            paragraph.add_run(element)
        elif isinstance(parent, _Cell):
            paragraph = parent.add_paragraph()
            paragraph.add_run(element)
        elif isinstance(parent, Paragraph):
            parent.add_run(element)
        elif isinstance(parent, Run):
            parent.add_text(element)
        else:
            # Handle other cases or raise an error
            pass
    elif element.name == "table":
        add_paragraph(document, parent, style="MD Text")
        add_table_from_html(element, parent or document)
    elif element.name in ["p", "div"]:
        if parent is None:
            paragraph = add_paragraph(document, style="MD Text")
        elif isinstance(parent, _Cell):
            paragraph = parent.add_paragraph()
        else:
            paragraph = add_paragraph(document, parent, style="MD Text")
        for child in element.contents:
            handle_html_elements(child, document, paragraph)
    elif element.name == "br":
        # Line break
        if parent is None:
            paragraph = add_paragraph(document, style="MD Text")
            paragraph.add_run().add_break()
        elif isinstance(parent, _Cell):
            paragraph = parent.add_paragraph()
        else:
            paragraph = add_paragraph(document, parent, style="MD Text")
        paragraph.add_run().add_break()
    elif element.name in ["strong", "b", "em", "i", "span"]:
        # Handle inline formatting
        if parent is None:
            paragraph = add_paragraph(document)
        elif isinstance(parent, _Cell):
            paragraph = parent.add_paragraph()
        else:
            paragraph = parent
        run = paragraph.add_run()
        if element.name in ["strong", "b"]:
            run.bold = True
        if element.name in ["em", "i"]:
            run.italic = True
        for child in element.contents:
            handle_html_elements(child, document, run)
    elif element.name == "a":
        # Handle hyperlinks
        href = element.get("href", "")
        link_text = "".join(element.stripped_strings)
        if parent is None:
            paragraph = add_paragraph(document)
        elif isinstance(parent, _Cell):
            paragraph = parent.add_paragraph()
        else:
            paragraph = parent
        add_hyperlink(paragraph, link_text, href)
    else:
        # Handle other elements
        for child in element.contents:
            handle_html_elements(child, document, parent)


def add_table_from_html(table_element, document: Document):
    """
    Convert an HTML table element to a Word table.

    :param table_element: The HTML <table> element.
    :param document: docx Document object.
    """
    rows = table_element.find_all("tr")
    if not rows:
        return

    # Calculate the maximum number of columns
    max_cols = 0
    for row in rows:
        cols = row.find_all(["td", "th"])
        col_count = 0
        for col in cols:
            colspan = int(col.get("colspan", 1))
            col_count += colspan
        if col_count > max_cols:
            max_cols = col_count

    # Create a grid to keep track of merged cells
    grid = [[None for _ in range(max_cols)] for _ in range(len(rows))]

    table = document.add_table(rows=len(rows), cols=max_cols)
    table.style = "Table Grid"  # You can set a custom style

    # Apply padding to all cells in the table
    apply_table_cell_padding(table)

    for i, row in enumerate(rows):
        j = 0
        cols = row.find_all(["td", "th"])
        for cell in cols:
            # Skip occupied cells
            while grid[i][j] is not None:
                j += 1

            rowspan = int(cell.get("rowspan", 1))
            colspan = int(cell.get("colspan", 1))

            # Get the text content
            cell_text = "".join(cell.stripped_strings)
            word_cell = table.cell(i, j)
            word_cell.text = cell_text

            # Apply bold formatting for header cells
            if cell.name == "th":
                for paragraph in word_cell.paragraphs:
                    for run in paragraph.runs:
                        run.bold = True

            # Mark the grid positions as occupied
            for r in range(i, i + rowspan):
                for c in range(j, j + colspan):
                    if r < len(grid) and c < max_cols:
                        grid[r][c] = (i, j)

            # Merge cells if needed
            if rowspan > 1 or colspan > 1:
                end_row = i + rowspan - 1
                end_col = j + colspan - 1
                word_cell.merge(table.cell(end_row, end_col))

            j += colspan  # Move to the next cell


def add_hyperlink(paragraph: Paragraph, text: str, url: str):
    """
    Add a hyperlink to a paragraph.

    :param paragraph: The paragraph to add the hyperlink to.
    :param text: The display text for the hyperlink.
    :param url: The URL the hyperlink points to.
    """
    # Get the document part
    part = paragraph.part
    # Create a relationship id
    r_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )

    # Create the w:hyperlink tag and add needed values
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    hyperlink.set(qn("w:history"), "1")

    # Create a w:r element
    new_run = OxmlElement("w:r")

    # Create a w:rPr element
    rPr = OxmlElement("w:rPr")

    # Style for hyperlink (Blue color and underlined)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0000FF")
    rPr.append(color)

    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rPr.append(underline)

    new_run.append(rPr)

    # Create the w:t element and set the text
    text_element = OxmlElement("w:t")
    text_element.text = text

    new_run.append(text_element)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
