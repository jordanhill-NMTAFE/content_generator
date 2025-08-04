"""Module for fetching and parsing training.gov.au unit of competencies using API"""

from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Dict, Any, List, Optional

import requests
import typer
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

import logging

log = logging.getLogger(__name__)


app = typer.Typer(help="🎓 Australian VET Unit of Competency (UOC) Tool")

# If there is an error in the underlying html formatting then we have to explicitly add the element so it renders properly


def next_tag(element: Tag) -> Tag:
    try:
        return next(filter(lambda e: isinstance(e, Tag), element.next_siblings))
    except StopIteration:
        return None


def previous_tag(element: Tag) -> Tag:
    try:
        return next(filter(lambda e: isinstance(e, Tag), element.previous_siblings))
    except StopIteration:
        return None


## Helper Functions
def unpack_soup(soup: BeautifulSoup, recursion_count: int = 0) -> dict[str, list[str]]:
    """
    Unpack a nested ul element into a dictionary.
    """
    # Define a base case for recursion and a recursion limit to prevent stack overflow
    if (
        not soup
        or not hasattr(soup, "name")
        or soup.name != "ul"
        or recursion_count > 10
    ):
        return {}

    unpacked = {}
    for element in soup:
        if hasattr(element, "name") and element.name == "li":
            for child in element.children:
                next_tag_child = next_tag(child)
                if (
                    isinstance(child, NavigableString)
                    and next_tag_child
                    and hasattr(next_tag_child, "name")
                    and next_tag_child.name == "ul"
                ):
                    key = child.string
                    unpacked[key] = unpack_soup(next_tag_child, recursion_count + 1)
                    continue
                if (
                    hasattr(child, "string")
                    and child.string
                    and child.string in EXCEPTIONS.keys()
                    and EXCEPTIONS[child.string] in unpacked.keys()
                ):
                    unpacked[EXCEPTIONS[child.string]][child.string] = {}
                    continue
                if isinstance(child, NavigableString) and child.string:
                    key = child.string
                    unpacked[key] = {}
    return unpacked


EXCEPTIONS = {
    "clustering algorithms": "key algorithms used to run unlabelled data, including:",
    "association algorithms": "key algorithms used to run unlabelled data, including:",
    "neural network algorithms": "key algorithms used to run unlabelled data, including:",
}


class UOCSections(Enum):
    """
    Enumeration representing different sections of a Unit of Competency.
    """

    MODIFICATION_HISTORY = "Modification history"
    APPLICATION = "Application"
    PERFORMANCE_EVIDENCE = "Performance evidence"
    KNOWLEDGE_EVIDENCE = "Knowledge evidence"
    ELEMENTS_AND_CRITERIA = "Elements and performance criteria"
    ASSESSMENT_CONDITIONS = "Assessment conditions"
    UNIT_SECTOR = "Unit sector"

    @property
    def attribute_name(self) -> str:
        """
        Convert enum value to snake_case to use it as an attribute name.
        """
        return self.name.lower()


@dataclass
class UnitOfCompetencyData:
    """
    Data class representing the extracted information from a Unit of Competency.
    """

    unit_code: str
    aqf_level: int
    modification_history: str = ""
    application: str = ""
    performance_evidence: dict[str, list[str]] = field(default_factory=dict)
    performance_skills: dict[str, list[str]] = field(default_factory=dict)
    knowledge_evidence: dict[str, list[str]] = field(default_factory=dict)
    elements_and_criteria: dict[str, str] = field(default_factory=dict)
    assessment_conditions: dict[str, list[str]] = field(default_factory=dict)
    unit_sector: str = ""

    def __str__(self) -> str:
        return f"{self.unit_code} - {self.aqf_level}"


class UnitOfCompetencyError(requests.HTTPError):
    """Base class for all errors in this module"""


class UnitOfCompetencyNotFoundError(UnitOfCompetencyError):
    """Raised when a unit of competency cannot be found"""

    def __init__(self, unit_code: str):
        self.unit_code = unit_code
        self.message = f"Unit of competency {unit_code} not found"
        super().__init__(self.message)


class UnitOfCompetency:
    """
    Class representing a Unit of Competency from training.gov.au.
    Responsible for fetching and parsing relevant data using the API.
    """

    base_url = "https://training.gov.au/api/"
    api_version = "1.0"

    def __init__(self, unit_code: str, sections: Iterable[UOCSections] = UOCSections):
        # Extract AQF level from unit code (also validates unit code)
        match = re.search(r"\d", unit_code)
        if not match:
            raise UnitOfCompetencyError(f"Invalid unit code {unit_code}")
        self.aqf_level = int(match.group())
        self.unit_code = unit_code
        self.sections = sections

        # Initialize variables
        self.application = ""
        self.performance_evidence = {}
        self.performance_skills = {}
        self.knowledge_evidence = {}
        self.elements_and_criteria = {}
        self.assessment_conditions = {}
        self.modification_history = ""
        self.unit_sector = ""

        # Fetch and process data
        self.data = self._get_data()

    def _get_data(self) -> UnitOfCompetencyData:
        try:
            release_info = self._fetch_release_info()
            content_bundles = release_info.get("contentBundles", [])
            for bundle in content_bundles:
                bundle_id = bundle["id"]
                # Fetch the content of the bundle
                bundle_content = self._fetch_bundle_content(bundle_id)
                # Process the content to extract sections
                self._process_bundle_content(bundle_content)
            return UnitOfCompetencyData(
                unit_code=self.unit_code,
                aqf_level=self.aqf_level,
                application=self.application,
                performance_evidence=self.performance_evidence,
                performance_skills=self.performance_skills,
                knowledge_evidence=self.knowledge_evidence,
                elements_and_criteria=self.elements_and_criteria,
                assessment_conditions=self.assessment_conditions,
                modification_history=self.modification_history,
                unit_sector=self.unit_sector,
            )
        except Exception as e:
            raise UnitOfCompetencyError(
                f"Error fetching data for unit {self.unit_code}: {e}"
            )

    def _fetch_release_info(self) -> dict:
        # https://training.gov.au/api/training/ICTPRG302/releases/1?api-version=1.0

        url = f"{self.base_url}training/{self.unit_code}/releases/1?api-version={self.api_version}"
        log.debug(f"Fetching release info from {url}")
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logging.error(f"Failed to fetch release info {url}: {e}")
            raise UnitOfCompetencyNotFoundError(self.unit_code) from e

    def _fetch_bundle_content(self, bundle_id: str) -> dict:
        url = (
            f"{self.base_url}content/bundle/{bundle_id}?api-version={self.api_version}"
        )
        log.debug(f"Fetching bundle content from {url}")
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logging.error(f"Failed to fetch bundle content {url}: {e}")
            raise UnitOfCompetencyError(f"Error fetching bundle content: {e}")

    def _process_bundle_content(self, bundle_content: dict):
        items = bundle_content.get("items", [])
        for item in items:
            title = item.get("title")
            content = item.get("content")

            if not content:
                continue  # Skip if there's no content

            try:
                # Parse content with BeautifulSoup
                soup = BeautifulSoup(content, "html.parser")

                if title == UOCSections.MODIFICATION_HISTORY.value:
                    self.modification_history = soup.get_text(strip=True)
                elif title == UOCSections.APPLICATION.value:
                    self.application = soup.get_text(strip=True)
                elif title == UOCSections.PERFORMANCE_EVIDENCE.value:
                    self.performance_evidence, self.performance_skills = (
                        self._parse_performance_evidence(soup)
                    )
                elif title == UOCSections.KNOWLEDGE_EVIDENCE.value:
                    self.knowledge_evidence = self._parse_knowledge_evidence(soup)
                elif title == UOCSections.ELEMENTS_AND_CRITERIA.value:
                    self.elements_and_criteria = self._parse_elements_and_criteria(soup)
                elif title == UOCSections.ASSESSMENT_CONDITIONS.value:
                    self.assessment_conditions = self._parse_assessment_conditions(soup)
                elif title == UOCSections.UNIT_SECTOR.value:
                    self.unit_sector = soup.get_text(strip=True)
                else:
                    # Handle other sections or ignore
                    log.debug(f"Ignoring unrecognized section: {title}")
            except Exception as e:
                log.error(f"Error parsing section '{title}': {e}")
                # For debugging, let's continue with other sections instead of failing completely
                continue

    def _parse_assessment_conditions(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        assessment_conditions = {}  # Dictionary to store the elements and sub-points

        # Check if soup.div exists and is not None
        if not soup.div:
            log.warning("No div element found in assessment conditions section")
            return assessment_conditions

        for element in filter(lambda e: isinstance(e, Tag), soup.div):
            next_tag_element = next_tag(element)
            if (
                element.name == "p"
                and len(element.text) > 0
                and next_tag_element
                and next_tag_element.name == "ul"
            ):
                assessment_conditions[element.text] = unpack_soup(next_tag_element)
                continue
            if element.name == "p" and len(element.text) > 0:
                assessment_conditions[element.text] = {}
                continue

        return assessment_conditions

    def _parse_performance_evidence(
        self, soup: BeautifulSoup
    ) -> tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        performance_evidence = {}  # Dictionary to store the main performance evidence
        performance_skills = {}  # Dictionary to store the performance skills

        # Check if soup.div exists and is not None
        if not soup.div:
            log.warning("No div element found in performance evidence section")
            return performance_evidence, performance_skills

        is_skills_section = False  # Track whether we're in the skills section
        elements = list(filter(lambda e: isinstance(e, Tag), soup.div))

        for i, element in enumerate(elements):
            # Check if this paragraph indicates the start of the skills section
            if (
                element.name == "p"
                and "In the course of the above, the candidate must:" in element.text
            ):
                is_skills_section = True
                # The next element should be a ul with the skills
                if i + 1 < len(elements) and elements[i + 1].name == "ul":
                    performance_skills[element.text] = unpack_soup(elements[i + 1])
                else:
                    performance_skills[element.text] = {}
                continue

            # Handle ul elements that follow skills section paragraph
            if element.name == "ul" and is_skills_section:
                # This ul is already handled above when we found the skills section paragraph
                continue

            next_tag_element = next_tag(element)

            if (
                element.name == "p"
                and len(element.text) > 0
                and next_tag_element
                and next_tag_element.name == "ul"
                and not is_skills_section  # Only for performance evidence, not skills
            ):
                performance_evidence[element.text] = unpack_soup(next_tag_element)
                continue

            if element.name == "p" and len(element.text) > 0 and not is_skills_section:
                performance_evidence[element.text] = {}
                continue

        return performance_evidence, performance_skills

    def _parse_knowledge_evidence(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """
        Parse the 'Knowledge Evidence' section of a Unit of Competency.
        """
        knowledge_evidence = {}  # Dictionary to store the elements and sub-points

        # Check if soup.div exists and is not None
        if not soup.div:
            log.warning("No div element found in knowledge evidence section")
            return knowledge_evidence

        for element in filter(lambda e: isinstance(e, Tag), soup.div):
            next_tag_element = next_tag(element)
            if (
                element.name == "p"
                and len(element.text) > 0
                and next_tag_element
                and next_tag_element.name == "ul"
            ):
                knowledge_evidence[element.text] = unpack_soup(next_tag_element)
                continue
            # elif element.name == "ul":
            #     performance_evidence.update(unpack_soup(element))
            if element.name == "p" and len(element.text) > 0:
                knowledge_evidence[element.text] = {}
                continue

        return knowledge_evidence

    def _parse_elements_and_criteria(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        Parse the 'Elements and Criteria' section of a Unit of Competency.
        """
        # Assuming content is in a structured format like HTML with a table
        elements = {}
        table = soup.find("table")
        if not table:
            return elements

        rows = table.find_all("tr")
        for row in rows[2:]:  # Skip header row
            cols = row.find_all("td")
            if len(cols) >= 2:
                element = cols[0].get_text(strip=True)
                criteria = unpack_soup(cols[1].ul)
                elements[element] = criteria
        return elements

    def __str__(self) -> str:
        sections_strings = []

        for section in self.sections:
            attr_name = section.attribute_name
            value = getattr(self.data, attr_name)
            if value:
                if isinstance(value, dict):
                    elements_strings = []
                    for key, sublist in value.items():
                        subpoints = "\n".join(f"- {point}" for point in sublist)
                        elements_strings.append(f"{key}\n{subpoints}")
                    section_string = f"{section.value}\n" + "\n\n".join(
                        elements_strings
                    )
                else:
                    section_string = f"{section.value}\n{value}"
                sections_strings.append(section_string)

        return "\n\n".join(sections_strings)

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}({self.unit_code!r}, {self.sections!r})"


@app.command()
def show(
    unit_code: str = typer.Argument(
        ..., help="Unit of Competency code (e.g., ICTPRG302)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed debug information"
    ),
    sections_only: bool = typer.Option(
        False, "--sections", "-s", help="Show available sections only"
    ),
):
    """
    📖 Display Unit of Competency information (default command).

    Examples:
        uoc show ICTPRG302           # Show full UOC details
        uoc show ICTPRG302 -v       # Show with debug info
        uoc show --sections ICTPRG302       # Show sections only
    """
    try:
        if verbose:
            import logging

            logging.basicConfig(level=logging.DEBUG)

        uoc = UnitOfCompetency(unit_code)

        if sections_only:
            print(f"📋 Available sections for {unit_code}:")
            for section in uoc.sections:
                print(f"  • {section.value}")
        else:
            print(f"📖 Unit of Competency: {unit_code}")
            print("=" * 60)
            print(uoc)

    except UnitOfCompetencyNotFoundError:
        print(f"❌ Unit '{unit_code}' not found on training.gov.au")
        print("💡 Check the unit code spelling and try again")
        raise typer.Exit(1)
    except UnitOfCompetencyError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(1)


# Make 'show' the default command when no subcommand is specified
def main_entry():
    """Main entry point that defaults to 'show' command if no subcommand given."""
    import sys

    # If no arguments or first arg is not a known command, prepend 'show'
    args = sys.argv[1:]
    known_commands = ["show", "compare", "search", "raw"]

    if not args or (args[0] not in known_commands and not args[0].startswith("-")):
        sys.argv.insert(1, "show")

    app()


def main_callback():
    """Empty callback - not used in this structure"""
    pass


@app.command()
def compare(
    unit1: str = typer.Argument(..., help="First unit code"),
    unit2: str = typer.Argument(..., help="Second unit code"),
):
    """
    🔍 Compare two Units of Competency side by side.
    """
    try:
        uoc1 = UnitOfCompetency(unit1)
        uoc2 = UnitOfCompetency(unit2)

        print(f"📊 Comparing {unit1} vs {unit2}")
        print("=" * 60)

        print(f"\n📝 {unit1} Elements: {len(uoc1.data.elements_and_criteria)}")
        print(f"📝 {unit2} Elements: {len(uoc2.data.elements_and_criteria)}")

        # Count criteria
        criteria1 = sum(
            len(criteria) for criteria in uoc1.data.elements_and_criteria.values()
        )
        criteria2 = sum(
            len(criteria) for criteria in uoc2.data.elements_and_criteria.values()
        )
        print(f"📋 {unit1} Criteria: {criteria1}")
        print(f"📋 {unit2} Criteria: {criteria2}")

        # Knowledge evidence
        ke1 = next(iter(uoc1.data.knowledge_evidence.values()))
        ke2 = next(iter(uoc2.data.knowledge_evidence.values()))
        ke1_count = len(ke1) if isinstance(ke1, (list, dict)) else 0
        ke2_count = len(ke2) if isinstance(ke2, (list, dict)) else 0
        print(f"🧠 {unit1} Knowledge items: {ke1_count}")
        print(f"🧠 {unit2} Knowledge items: {ke2_count}")

    except (UnitOfCompetencyNotFoundError, UnitOfCompetencyError) as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(1)


@app.command()
def search(
    term: str = typer.Argument(..., help="Search term"),
    unit_code: str = typer.Argument(..., help="Unit code to search in"),
):
    """
    🔍 Search for text within a Unit of Competency.
    """
    try:
        uoc = UnitOfCompetency(unit_code)
        uoc_text = str(uoc).lower()
        search_term = term.lower()

        if search_term in uoc_text:
            print(f"✅ Found '{term}' in {unit_code}")

            # Show context around matches
            lines = str(uoc).split("\n")
            matches = []
            for i, line in enumerate(lines):
                if search_term in line.lower():
                    matches.append((i, line.strip()))

            print(f"\n📍 Found {len(matches)} match(es):")
            for line_num, line in matches[:5]:  # Show first 5 matches
                print(f"  Line {line_num + 1}: {line}")

        else:
            print(f"❌ '{term}' not found in {unit_code}")

    except (UnitOfCompetencyNotFoundError, UnitOfCompetencyError) as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(1)


@app.command()
def raw(
    unit_code: str = typer.Argument(..., help="Unit code"),
):
    """
    🔧 Show raw UOC data structure (for debugging).
    """
    try:
        uoc = UnitOfCompetency(unit_code)
        print(f"🔧 Raw data for {unit_code}:")
        print("=" * 60)
        print(uoc.data)
    except (UnitOfCompetencyNotFoundError, UnitOfCompetencyError) as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    main_entry()
