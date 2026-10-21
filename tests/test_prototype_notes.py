import re
from pathlib import Path

from storybook.prototype_notes import EXPERIENCE, KINDS, NOTES, SOURCE_PLANS, notes_by_kind

APP = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")


def test_every_marker_in_the_app_has_a_note():
    used = set(re.findall(r'proto_(?:note|badge)\("([a-z_]+)"', APP)) | set(re.findall(r'NOTES\["([a-z_]+)"\]', APP))
    assert used, "the app should show prototype markers"
    assert used <= set(NOTES), f"missing notes: {used - set(NOTES)}"


def test_notes_are_complete_and_use_known_kinds():
    for key, note in NOTES.items():
        assert note["kind"] in KINDS, key
        for field in ("title", "here", "full"):
            assert note[field].strip(), f"{key}.{field} is empty"
    grouped = notes_by_kind()
    assert sum(len(items) for items in grouped.values()) == len(NOTES)
    assert all(grouped[kind] for kind in KINDS), "each kind should have at least one example"
    assert EXPERIENCE


def test_planned_sources_say_how_they_will_work():
    # Only OneDrive keeps syncing; the others are one-off choices or downloads.
    assert "sync" in SOURCE_PLANS["OneDrive"]
    assert "sync" not in SOURCE_PLANS["Google Photos"] and "Picker" in SOURCE_PLANS["Google Photos"]
    assert "data download" in SOURCE_PLANS["Instagram"]
