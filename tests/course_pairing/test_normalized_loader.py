"""Tests for the normalized-pathways loader (no real AWS; fake table)."""

import pytest

from course_pairing.normalize_pathways import (
    build_normalized_item,
    build_all,
    write_items,
    apply_to_table,
    SOURCE_TABLE,
    NORMALIZED_VERSION,
)

SUBJECTS = {"DMT", "ENGL", "EWRT", "ESL", "MATH", "ADMJ"}

SOURCE_RECORD = {
    "program_name": "Example Program",
    "village": "Physical Sciences and Technology",
    "credential_type": "COA",
    "source_file": "2025 Example.pdf",
    "page_number": 1,
    "years": {
        "year_1": {
            "fall": {"required_courses": ["DMT 53"], "additional_courses": []},
            "winter": {
                "required_courses": ["MATH as required"],
                "additional_courses": ["DMT 60A or DMT 65A"],
            },
        }
    },
}


class FakeBatch:
    def __init__(self, store):
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def put_item(self, Item):
        # Mimic DynamoDB: put overwrites by primary key -> idempotent reruns.
        self.store[Item["pathway_id"]] = Item


class FakeTable:
    def __init__(self):
        self.store = {}

    def batch_writer(self):
        return FakeBatch(self.store)


def test_build_item_shape_and_metadata():
    item = build_normalized_item(SOURCE_RECORD, SUBJECTS)
    assert item["pathway_id"] == "2025 Example.pdf#1"
    assert item["normalization_version"] == NORMALIZED_VERSION
    assert item["program_name"] == "Example Program"
    assert item["village"] == "Physical Sciences and Technology"
    # normalized quarters carry the cleaned lists
    fall = item["years"]["year_1"]["fall"]
    assert fall["normalized_courses"] == ["DMT 53"]
    winter = item["years"]["year_1"]["winter"]
    assert winter["normalized_courses"] == ["DMT 60A", "DMT 65A"]
    assert winter["unresolved_entries"] == ["MATH as required"]


def test_build_item_does_not_carry_source_course_arrays():
    """The normalized item stores only cleaned lists, not the verbose source."""
    item = build_normalized_item(SOURCE_RECORD, SUBJECTS)
    fall = item["years"]["year_1"]["fall"]
    assert set(fall.keys()) == {"normalized_courses", "unresolved_entries"}


def test_build_item_does_not_mutate_source():
    import copy
    original = copy.deepcopy(SOURCE_RECORD)
    build_normalized_item(SOURCE_RECORD, SUBJECTS)
    assert SOURCE_RECORD == original


def test_pathway_id_prefers_existing_key():
    rec = dict(SOURCE_RECORD, pathway_id="explicit#9")
    assert build_normalized_item(rec, SUBJECTS)["pathway_id"] == "explicit#9"


def test_write_items_and_idempotent_rerun():
    table = FakeTable()
    items = build_all([SOURCE_RECORD], SUBJECTS)
    assert write_items(table, items) == 1
    assert len(table.store) == 1
    snapshot = dict(table.store)
    # Re-running writes the same key -> same content, no duplication.
    write_items(table, items)
    assert table.store == snapshot
    assert len(table.store) == 1


def test_apply_refuses_source_table():
    items = build_all([SOURCE_RECORD], SUBJECTS)
    with pytest.raises(ValueError, match="Refusing to write to the source table"):
        apply_to_table(items, SOURCE_TABLE, create_table=False)
