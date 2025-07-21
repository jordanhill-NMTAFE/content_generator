#!/usr/bin/env python3

from src.utils.uoc_api import UnitOfCompetency


def examine_uoc_structure(unit_code):
    print(f"\n=== UOC Structure for {unit_code} ===")
    uoc = UnitOfCompetency(unit_code)

    print(f"Unit Title: {getattr(uoc.data, 'title', 'N/A')}")
    print(f"Unit Description: {getattr(uoc.data, 'description', 'N/A')}")

    print("\nElements and Criteria:")
    if hasattr(uoc.data, "elements_and_criteria"):
        for i, (element, criteria) in enumerate(uoc.data.elements_and_criteria.items()):
            element_num = i + 1
            print(f"\nElement {element_num}: {element}")
            for criteria_key, criteria_desc in criteria.items():
                print(f"  {criteria_key}: {criteria_desc}")
    else:
        print("No elements_and_criteria found")

    print("\nKnowledge Evidence:")
    if hasattr(uoc.data, "knowledge_evidence"):
        for element, subelements in uoc.data.knowledge_evidence.items():
            print(f"  {element}: {subelements}")
    else:
        print("No knowledge_evidence found")

    print("\nPerformance Evidence:")
    if hasattr(uoc.data, "performance_evidence"):
        for element, subelements in uoc.data.performance_evidence.items():
            print(f"  {element}: {subelements}")
    else:
        print("No performance_evidence found")


if __name__ == "__main__":
    examine_uoc_structure("ICTPRG435")
    examine_uoc_structure("ICTCLD401")
