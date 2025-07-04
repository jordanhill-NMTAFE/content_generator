import pytest
from src.utils.uoc_api import UnitOfCompetency
from src.content_generator.oo_mapping_matrix import MappingMatrixData


@pytest.mark.integration
def test_mapping_matrix_data_structure():
    # Fetch a real UOC
    uoc = UnitOfCompetency("ICTPRG302")
    unit_id = "ICTPRG302"
    # Use actual criteria keys from the UoC
    element_1 = "1. Establish application task"
    element_2 = "2. Apply language syntax and layout"
    crit_1_1 = "1.1 Clarify task with required personnel"
    crit_1_2 = "1.2 Identify design specifications, programming standards and guidelines according to task requirements"
    crit_2_1 = "2.1 Apply basic language syntax rules"
    # Use actual knowledge keys from the UoC
    knowledge_keys = list(uoc.data.knowledge_evidence.values())[0].keys()
    knowledge_1 = list(knowledge_keys)[0] if knowledge_keys else None
    knowledge_2 = list(knowledge_keys)[1] if len(knowledge_keys) > 1 else None
    # Use actual performance keys from the UoC
    performance_keys = list(uoc.data.performance_evidence.keys())
    performance_1 = performance_keys[0] if performance_keys else None
    # Use actual skills keys from the UoC (same as performance for this structure)
    skills_1 = performance_keys[0] if performance_keys else None
    # Create a dummy assessment with valid mappings for all sections
    assessments = [
        {
            "name": "Assessment 1",
            "mapping": [
                {
                    "criteria": {unit_id: [crit_1_1, crit_1_2]},
                    "knowledge": {unit_id: [1]},
                    "performance": {unit_id: [1]},
                    "skills": {unit_id: [1]},
                },
                {
                    "criteria": {unit_id: [crit_2_1]},
                    "knowledge": {unit_id: [2]},
                    "performance": {unit_id: [2]},
                    "skills": {unit_id: [2]},
                },
            ],
        }
    ]
    # Build the mapping matrix data
    matrix_data = MappingMatrixData.from_uoc_and_assessments(uoc, assessments, unit_id)
    # Check the mapping array shape
    assert matrix_data.mapping_array.shape[1] == max(
        len(a["mapping"]) for a in assessments
    )
    # Check that at least one mapping exists
    assert matrix_data.mapping_array.sum() > 0
    # Check row/col labels
    assert "row_labels" in matrix_data.mapping_labels
    assert "col_labels" in matrix_data.mapping_labels
    # Check element mappings
    for k, v in matrix_data.element_mappings.items():
        assert isinstance(v, list)
    # Check knowledge mappings
    for k, v in matrix_data.knowledge_mappings.items():
        assert isinstance(v, list)
    # Check performance mappings
    for k, v in matrix_data.performance_mappings.items():
        assert isinstance(v, list)
    # Check skills mappings
    for k, v in matrix_data.skills_mappings.items():
        assert isinstance(v, list)
    # Assert that the mappings for the first knowledge, performance, and skills are non-empty
    if knowledge_1:
        assert matrix_data.knowledge_mappings[knowledge_1], (
            f"No mapping for knowledge: {knowledge_1}"
        )
    if performance_1:
        assert matrix_data.performance_mappings[performance_1] is not None
    if skills_1:
        assert matrix_data.skills_mappings[skills_1] is not None
    # Print for debug
    print("Mapping array:", matrix_data.mapping_array)
    print("Element mappings:", matrix_data.element_mappings)
    print("Knowledge mappings:", matrix_data.knowledge_mappings)
    print("Performance mappings:", matrix_data.performance_mappings)
    print("Skills mappings:", matrix_data.skills_mappings)
    print("Row labels:", matrix_data.mapping_labels["row_labels"])
    print("Col labels:", matrix_data.mapping_labels["col_labels"])


@pytest.mark.integration
def test_mapping_matrix_data_structure_ictaii401():
    # Fetch a real UOC
    uoc = UnitOfCompetency("ICTAII401")
    unit_id = "ICTAII401"
    # Use actual criteria keys from the UoC
    element_keys = list(uoc.data.elements_and_criteria.keys())
    element_1 = element_keys[0]
    crit_keys = list(uoc.data.elements_and_criteria[element_1].keys())
    crit_1_1 = crit_keys[0]
    # Use actual knowledge keys from the UoC
    knowledge_blurb, KE = next(iter(uoc.data.knowledge_evidence.items()))
    knowledge_keys = list(KE.keys())
    knowledge_1 = knowledge_keys[0] if knowledge_keys else None
    # Use actual performance keys from the UoC
    performance_keys = list(uoc.data.performance_evidence.keys())
    performance_1 = performance_keys[0] if performance_keys else None
    # Use actual skills keys from the UoC (same as performance for this structure)
    skills_1 = performance_keys[0] if performance_keys else None
    # Use actual foundation skills keys from the UoC (if present)
    foundation_skills = getattr(uoc.data, "foundation_skills", [])
    fs_1 = foundation_skills[0] if foundation_skills else None
    # Create a dummy assessment with both index-based and string-based mappings for all types
    assessments = [
        {
            "name": "Assessment 1",
            "mapping": [
                {
                    "criteria": {unit_id: [1, crit_1_1]},  # index and string
                    "knowledge": {unit_id: [1, knowledge_1]},
                    "performance": {unit_id: [1, performance_1]},
                    "skills": {unit_id: [1, skills_1]},
                    "foundation_skills": {unit_id: [1, fs_1]} if fs_1 else {},
                },
            ],
        }
    ]
    # Build the mapping matrix data
    matrix_data = MappingMatrixData.from_uoc_and_assessments(uoc, assessments, unit_id)
    # Check the mapping array shape
    assert matrix_data.mapping_array.shape[1] == max(
        len(a["mapping"]) for a in assessments
    )
    # Check that at least one mapping exists
    assert matrix_data.mapping_array.sum() > 0
    # Check row/col labels
    assert "row_labels" in matrix_data.mapping_labels
    assert "col_labels" in matrix_data.mapping_labels
    # Check element mappings
    assert any(v for v in matrix_data.element_mappings.values()), (
        "No element mappings found!"
    )
    # Check knowledge mappings: every knowledge element in the UoC should be present
    unmapped_knowledge = []
    mapped_knowledge_count = 0
    for k in knowledge_keys:
        assert k in matrix_data.knowledge_mappings, (
            f"Missing knowledge mapping for: {k}"
        )
        if matrix_data.knowledge_mappings[k]:
            mapped_knowledge_count += 1
        else:
            unmapped_knowledge.append(k)
    assert mapped_knowledge_count > 0, "No knowledge elements are mapped!"
    if unmapped_knowledge:
        print("Unmapped knowledge elements:", unmapped_knowledge)
    # Check performance mappings
    assert any(v for v in matrix_data.performance_mappings.values()), (
        "No performance mappings found!"
    )
    # Check skills mappings
    assert any(v for v in matrix_data.skills_mappings.values()), (
        "No skills mappings found!"
    )
    # Check foundation skills mappings (if present)
    if foundation_skills:
        assert any(v for v in matrix_data.foundation_skills_mappings.values()), (
            "No foundation skills mappings found!"
        )
        for k in foundation_skills:
            assert k in matrix_data.foundation_skills_mappings, (
                f"Missing foundation skill mapping for: {k}"
            )
    # Print for debug
    print("Mapping array:", matrix_data.mapping_array)
    print("Element mappings:", matrix_data.element_mappings)
    print("Knowledge mappings:", matrix_data.knowledge_mappings)
    print("Performance mappings:", matrix_data.performance_mappings)
    print("Skills mappings:", matrix_data.skills_mappings)
    print("Foundation skills mappings:", matrix_data.foundation_skills_mappings)
    print("Row labels:", matrix_data.mapping_labels["row_labels"])
    print("Col labels:", matrix_data.mapping_labels["col_labels"])


def test_knowledge_mapping_number_and_string_logic(monkeypatch):
    """
    Validates that number-based and string-based knowledge mappings only map to the correct knowledge element,
    and that out-of-range numbers generate warnings, but valid numbers do not.
    """
    uoc = UnitOfCompetency("ICTAII401")
    unit_id = "ICTAII401"
    knowledge_blurb, KE = next(iter(uoc.data.knowledge_evidence.items()))
    knowledge_keys = list(KE.keys())
    # Prepare a mapping with:
    # - valid indices (1, 2)
    # - a valid string (knowledge_keys[2])
    # - an out-of-range index (99)
    # - an unmatched string ("not a real knowledge item")
    assessments = [
        {
            "name": "Test",
            "mapping": [
                {
                    "knowledge": {
                        unit_id: [
                            1,
                            2,
                            knowledge_keys[2],
                            99,
                            "not a real knowledge item",
                        ]
                    }
                },
            ],
        }
    ]
    warnings = []

    def fake_warning(msg):
        warnings.append(msg)

    monkeypatch.setattr(
        "src.content_generator.oo_mapping_matrix.logger.warning", fake_warning
    )
    matrix = MappingMatrixData.from_uoc_and_assessments(uoc, assessments, unit_id)
    # Only the correct elements should be mapped
    assert matrix.knowledge_mappings[knowledge_keys[0]] == [1], (
        "Index 1 should map to first knowledge element"
    )
    assert matrix.knowledge_mappings[knowledge_keys[1]] == [1], (
        "Index 2 should map to second knowledge element"
    )
    assert matrix.knowledge_mappings[knowledge_keys[2]] == [1], (
        "String key should map to third knowledge element"
    )
    # All other knowledge elements should be empty
    for k in knowledge_keys[3:]:
        assert matrix.knowledge_mappings[k] == [], f"No mapping expected for: {k}"
    # There should be a warning for the out-of-range index and unmatched string
    assert any("index 99 is out of range" in w for w in warnings), (
        "Should warn for out-of-range index"
    )
    assert any("not a real knowledge item" in w for w in warnings), (
        "Should warn for unmatched string"
    )
    # There should NOT be warnings for valid indices or valid string
    # Only fail if the warning is about the valid string key itself (not just appearing in options)
    assert not any(
        f"Could not place mapping value '{knowledge_keys[2]}'" in w for w in warnings
    ), "Should not warn for valid string key"
