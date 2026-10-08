import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from pypdf import PdfReader

from storybook.core import (InvalidPhoto, add_photo, chronological_photos,
                            extract_metadata, jpeg_preview_bytes, list_projects,
                            load_project, new_project, photo_path, save_project)
from storybook.ai import analyse_photo, generate_ai_story, generate_local_story, normalize_chapters
from storybook.book_pdf import generate_pdf
from storybook.demo import make_demo_project


def jpg_bytes(with_exif=False):
    img = Image.new("RGB", (800, 500), "#8cbab0")
    buff = io.BytesIO()
    if with_exif:
        exif = Image.Exif()
        exif[36867] = "2001:04:15 09:30:00"
        exif[271] = "Nikon"
        img.save(buff, format="JPEG", exif=exif)
    else:
        img.save(buff, format="JPEG")
    return buff.getvalue()


def test_exif_dates_and_camera_are_read():
    with Image.open(io.BytesIO(jpg_bytes(True))) as img:
        metadata = extract_metadata(img)
    assert metadata["capture_date"] == "2001-04-15"
    assert "Nikon" in metadata["camera"]
    assert metadata["gps"] is None


def test_upload_duplicates_and_saved_project(tmp_path):
    p = new_project("Tiny story")
    assert add_photo(tmp_path, p, "folder/pic.jpeg", jpg_bytes(True))
    assert not add_photo(tmp_path, p, "pic_copy.jpeg", jpg_bytes(True))
    assert len(p["photos"]) == 1
    assert p["photos"][0]["filename"] == "pic.jpeg"
    assert photo_path(tmp_path, p["id"], p["photos"][0]).exists()
    assert load_project(tmp_path, p["id"])["title"] == "Tiny story"
    assert list_projects(tmp_path)[0]["id"] == p["id"]


def test_invalid_upload_refused(tmp_path):
    p = new_project()
    with pytest.raises(InvalidPhoto):
        add_photo(tmp_path, p, "fake.jpg", b"not a jpeg")
    with pytest.raises(InvalidPhoto):
        add_photo(tmp_path, p, "too_large.jpg", b"0" * (20 * 1024 * 1024 + 1))


def test_preview_strips_exif(tmp_path):
    path = tmp_path / "image.jpg"
    path.write_bytes(jpg_bytes(True))
    cleaned = jpeg_preview_bytes(path)
    with Image.open(io.BytesIO(cleaned)) as img:
        assert not img.getexif().get(36867)
        assert img.size == (800, 500)


def test_chronology_and_local_story(tmp_path):
    p = new_project()
    add_photo(tmp_path, p, "a.jpg", jpg_bytes(True))
    second = Image.new("RGB", (800, 501), "#116977")
    b = io.BytesIO(); second.save(b, format="JPEG")
    add_photo(tmp_path, p, "b.jpg", b.getvalue())
    p["photos"][1]["event_date"] = "1998-05-10"
    p["photos"][1]["memory"] = "Our first family picnic."
    assert chronological_photos(p)[0]["filename"] == "b.jpg"
    chapters = generate_local_story(p)
    assert len(chapters) == 1
    assert "Our first family picnic" in chapters[0]["text"]
    assert len(chapters[0]["photo_ids"]) == 2


class MockClient:
    def __init__(self, payload):
        self.payload = payload
        self.args = []
        self.responses = self

    def create(self, **kwargs):
        self.args.append(kwargs)
        return SimpleNamespace(output_text=json.dumps(self.payload))


def test_ai_image_call_contains_stripped_photo(tmp_path):
    image_path = tmp_path / "test.jpg"
    image_path.write_bytes(jpg_bytes(True))
    client = MockClient({"observation": "A tree next to a house.", "question": "Where was this?"})
    response = analyse_photo(client, "gpt-4.1-mini", image_path)
    assert response["question"] == "Where was this?"
    img_url = client.args[0]["input"][1]["content"][1]["image_url"]
    data = base64.b64decode(img_url.split(",",1)[1])
    with Image.open(io.BytesIO(data)) as image:
        assert not image.getexif()


def test_ai_story_data_is_grounded_and_all_photos_included(tmp_path):
    p = new_project()
    add_photo(tmp_path, p, "a.jpg", jpg_bytes())
    p["photos"][0]["people"] = "Auntie Jo"
    p["photos"][0]["memory"] = "We made pancakes."
    client = MockClient({"chapters": [{"title": "Breakfast", "text": "We made pancakes.",
                                     "photo_ids": [p["photos"][0]["id"]]}]})
    chapters = generate_ai_story(client, "gpt-4.1-mini", p)
    assert len(chapters) == 1
    assert chapters[0]["photo_ids"] == [p["photos"][0]["id"]]
    sent = json.loads(client.args[0]["input"][1]["content"])
    assert sent["photos"][0]["user_people"] == "Auntie Jo"
    assert "gps" not in str(sent).lower()
    assert normalize_chapters([], p["photos"])[0]["photo_ids"] == [p["photos"][0]["id"]]


def test_full_demo_to_pdf(tmp_path):
    p = make_demo_project(tmp_path)
    assert len(p["photos"]) == 4
    assert len(p["chapters"]) == 4
    p["title"] = "Moments & Memories"
    p["chapters"][0]["text"] += "\n\nOur story is still being written."
    save_project(tmp_path, p)
    data = generate_pdf(load_project(tmp_path, p["id"]), tmp_path)
    assert data[:5] == b"%PDF-"
    reader = PdfReader(io.BytesIO(data))
    assert len(reader.pages) >= 3
    extracted = " ".join((page.extract_text() or "") for page in reader.pages)
    assert "Moments & Memories" in extracted
    assert "CHAPTER" in extracted
    assert "Our story is still being written" in extracted
    assert any(page.get("/Resources", {}).get("/XObject") for page in reader.pages)
