from pathlib import Path
from markdown_it import MarkdownIt
from markdown_it.token import Token
from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.shared import qn
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph
import frontmatter
import re
from bs4 import BeautifulSoup  # Import for HTML parsing


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


def parse_md(path: Path) -> frontmatter.Post:
    assert path.is_file()
    assert path.exists()
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
    md = MarkdownIt().enable("html_block").enable("html_inline")
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

    for token in tokens:
        if token.type == "heading_open":
            level = int(token.tag[1])
            style = f"Heading {level}"
            current_paragraph = add_paragraph(document, parent, style=style)
        elif token.type == "heading_close":
            current_paragraph = None
        elif token.type == "paragraph_open":
            if len(list_style_stack) > 0:
                continue
            current_paragraph = add_paragraph(document, parent)
        elif token.type == "paragraph_close":
            if len(list_style_stack) > 0:
                continue
            current_paragraph = None
        elif token.type == "inline":
            if current_paragraph is None:
                current_paragraph = add_paragraph(document, parent)
            process_inline(token.children, current_paragraph)
        elif token.type == "fence":
            # Code block
            current_paragraph = add_paragraph(document, parent, style="Code")
            run = current_paragraph.add_run(token.content)
            run.font.name = "Courier New"
            run.font.size = Pt(10)
        elif token.type == "bullet_list_open":
            list_style_stack.append("List Bullet")
        elif token.type == "ordered_list_open":
            list_style_stack.append("List Number")
        elif token.type == "bullet_list_close" or token.type == "ordered_list_close":
            if list_style_stack:
                list_style_stack.pop()
        elif token.type == "list_item_open":
            style = list_style_stack[-1] if list_style_stack else None
            current_paragraph = add_paragraph(document, parent, style=style)
        elif token.type == "list_item_close":
            current_paragraph = None
        elif token.type == "html_inline" or token.type == "html_block":
            # Handle HTML content
            process_html(token.content, document, parent)
        elif token.type == "blockquote_open":
            current_paragraph = add_paragraph(document, parent, style="Quote")
        elif token.type == "blockquote_close":
            current_paragraph = None
        elif token.type == "hr":
            for _ in range(10):
                current_paragraph = empty_paragraph(document, parent)
            continue
            document.add_page_break()
        else:
            # Handle other token types if necessary
            pass


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
            run = paragraph.add_run(token.content)
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
        add_paragraph(document, parent)
        add_table_from_html(element, parent or document)
    elif element.name in ["p", "div"]:
        if parent is None:
            paragraph = add_paragraph(document)
        elif isinstance(parent, _Cell):
            paragraph = parent.add_paragraph()
        else:
            paragraph = add_paragraph(document, parent)
        for child in element.contents:
            handle_html_elements(child, document, paragraph)
    elif element.name == "br":
        # Line break
        if parent is None:
            paragraph = add_paragraph(document)
            paragraph.add_run().add_break()
        elif isinstance(parent, _Cell):
            paragraph = parent.add_paragraph()
        else:
            paragraph = add_paragraph(document, parent)
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
