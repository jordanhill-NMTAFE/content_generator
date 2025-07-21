#!/usr/bin/env python3
"""
Utility script to inspect Unit of Competency (UOC) structure.
Use this to see what criteria are available for mapping.
"""

import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.uoc_api import UnitOfCompetency, UnitOfCompetencyError


def inspect_uoc(unit_code: str):
    """Inspect a UOC and show its structure."""
    try:
        print(f"=== Inspecting Unit: {unit_code} ===\n")

        uoc = UnitOfCompetency(unit_code)

        print("📋 ELEMENTS AND CRITERIA:")
        print("-" * 40)
        for element, criteria in uoc.data.elements_and_criteria.items():
            print(f"\n🔹 {element}")
            if isinstance(criteria, dict):
                for criterion_key, criterion_desc in criteria.items():
                    print(f"   {criterion_key}: {criterion_desc}")
            elif isinstance(criteria, list):
                for i, criterion in enumerate(criteria, 1):
                    print(f"   {element.split()[1]}.{i}: {criterion}")
            else:
                print(f"   {criteria}")

        print(f"\n📚 KNOWLEDGE EVIDENCE:")
        print("-" * 40)
        if hasattr(uoc.data, "knowledge_evidence"):
            for knowledge_item, details in uoc.data.knowledge_evidence.items():
                print(f"\n🔹 {knowledge_item}")
                if isinstance(details, list):
                    for i, item in enumerate(details, 1):
                        print(f"   {i}: {item}")
                elif isinstance(details, dict):
                    for key, values in details.items():
                        print(f"   {key}")
                        if isinstance(values, list):
                            for value in values:
                                print(f"     - {value}")

        print(f"\n🎯 PERFORMANCE EVIDENCE:")
        print("-" * 40)
        if hasattr(uoc.data, "performance_evidence"):
            for performance_item, details in uoc.data.performance_evidence.items():
                print(f"\n🔹 {performance_item}")
                if isinstance(details, list):
                    for i, item in enumerate(details, 1):
                        print(f"   {i}: {item}")
                elif isinstance(details, dict):
                    for key, values in details.items():
                        print(f"   {key}")
                        if isinstance(values, list):
                            for value in values:
                                print(f"     - {value}")

        print(f"\n✅ SUMMARY FOR MAPPING:")
        print("-" * 40)
        print("Available criteria numbers for mapping:")
        for element, criteria in uoc.data.elements_and_criteria.items():
            if isinstance(criteria, dict):
                criteria_numbers = list(criteria.keys())
                print(f"  {element}: {criteria_numbers}")

    except UnitOfCompetencyError as e:
        print(f"❌ Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python inspect_uoc.py <UNIT_CODE>")
        print("Example: python inspect_uoc.py ICTAII502")
        sys.exit(1)

    unit_code = sys.argv[1].upper()
    inspect_uoc(unit_code)
