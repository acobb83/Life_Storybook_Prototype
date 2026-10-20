import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from pypdf import PdfReader

from storybook.core import (InvalidPhoto, add_photo, chronological_photos, select_photos,
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


def test_ask_for_a_story_filters_by_year_and_place(tmp_path):
    p = make_demo_project(tmp_path)
    assert [x["caption"] for x in select_photos(p, (1997, 2003))] == ["Beach afternoons", "Our little backyard"]
    assert [x["caption"] for x in select_photos(p, places=["Blue Mountains"])] == ["Time together"]
    assert len(select_photos(p)) == 4


def test_story_request_is_sent_to_writer(tmp_path):
    p = new_project()
    add_photo(tmp_path, p, "a.jpg", jpg_bytes())
    p["story_request"] = "Tell the story of our holidays"
    client = MockClient({"chapters": []})
    generate_ai_story(client, "gpt-4.1-mini", p)
    sent = json.loads(client.args[0]["input"][1]["content"])
    assert sent["user_story_request"] == "Tell the story of our holidays"


def test_demo_has_map_points_for_some_scenes(tmp_path):
    p = make_demo_project(tmp_path)
    located = [x["caption"] for x in p["photos"] if x["metadata"]["gps"]]
    assert located == ["Beach afternoons", "Time together"]


def test_filenames_are_not_sent_to_writer(tmp_path):
    p = new_project()
    add_photo(tmp_path, p, "school_years_age_10.jpg", jpg_bytes())
    client = MockClient({"chapters": []})
    generate_ai_story(client, "gpt-4.1-mini", p)
    sent = client.args[0]["input"][1]["content"]
    assert "age_10" not in sent and "filename" not in sent


def test_place_lookup_prefers_city_and_ignores_ordinary_words():
    from storybook.travel import lookup_place
    assert lookup_place("Paris, France")["name"] == "Paris"
    assert lookup_place("Shinjuku, Tokyo")["country"] == "Japan"
    assert lookup_place("a trip to Japan")["name"] == "Japan"
    assert lookup_place("Our first family home") is None


def test_travel_demo_groups_trips_in_order(tmp_path):
    from storybook.demo import make_travel_demo_project
    from storybook.travel import build_trips
    p = make_travel_demo_project(tmp_path)
    stops, unmapped = build_trips(p["photos"])
    assert [s["name"] for s in stops] == ["Tokyo", "Kyoto", "Singapore", "Sydney", "Paris"]
    assert [len(s["photo_ids"]) for s in stops] == [2, 1, 2, 1, 2]
    assert stops[0]["when"] == "2019-04-12 – 2019-04-13"
    assert len(unmapped) == 1
    assert [c["title"] for c in p["chapters"]][0] == "Tokyo, Japan · 2019-04"


def test_trip_chapters_use_only_user_notes(tmp_path):
    from storybook.travel import build_trips, chapters_from_trips
    p = new_project()
    add_photo(tmp_path, p, "a.jpg", jpg_bytes())
    p["photos"][0].update({"place": "Kyoto", "event_date": "2019-04-15", "memory": "Green tea."})
    stops, _ = build_trips(p["photos"])
    chapters = chapters_from_trips(stops, p["photos"])
    assert chapters[0]["text"] == "Green tea."
    assert chapters[0]["photo_ids"] == [p["photos"][0]["id"]]


def test_place_suggestion_uses_stripped_image_and_respects_no_evidence(tmp_path):
    from storybook.ai import suggest_place
    image_path = tmp_path / "test.jpg"
    image_path.write_bytes(jpg_bytes(True))
    client = MockClient({"city": "Kyoto", "country": "Japan", "evidence": "A sign reads Kyoto.",
                         "confidence": "medium"})
    result = suggest_place(client, "gpt-4.1-mini", image_path)
    assert result == {"place": "Kyoto, Japan", "evidence": "A sign reads Kyoto.", "confidence": "medium"}
    img_url = client.args[0]["input"][1]["content"][1]["image_url"]
    with Image.open(io.BytesIO(base64.b64decode(img_url.split(",", 1)[1]))) as image:
        assert not image.getexif()
    none = suggest_place(MockClient({"city": "Paris", "country": "", "evidence": "Nothing clear.",
                                     "confidence": "none"}), "m", image_path)
    assert none["place"] == "" and none["confidence"] == "none"


def test_every_book_type_builds_a_draft(tmp_path):
    from storybook.demo import make_travel_demo_project
    from storybook.book_types import BOOK_TYPES, TYPE_ORDER, apply_type, local_chapters
    assert set(TYPE_ORDER) == set(BOOK_TYPES)
    p = make_travel_demo_project(tmp_path)
    for key in TYPE_ORDER:
        apply_type(p, key)
        chapters = local_chapters(p, p["photos"])
        placed = [pid for ch in chapters for pid in ch["photo_ids"]]
        assert sorted(placed) == sorted(x["id"] for x in p["photos"]), key  # every photo, exactly once
        assert p["cover_kicker"] == BOOK_TYPES[key]["kicker"]
    apply_type(p, "year")
    assert [c["title"] for c in local_chapters(p, p["photos"])][0] == "April 2019"
    apply_type(p, "family")
    assert [c["title"] for c in local_chapters(p, p["photos"])] == ["The 2010s", "The 2020s"]


def test_changing_type_keeps_a_custom_title(tmp_path):
    from storybook.book_types import apply_type
    p = new_project()
    p["title"] = ""
    apply_type(p, "business")
    assert p["title"] == "Project Record" and p["voice"] == "Clear and professional"
    p["title"] = "Fit-out of Level 3"
    apply_type(p, "year")
    assert p["title"] == "Fit-out of Level 3" and p["cover_kicker"] == "A YEAR IN REVIEW"


def test_writer_receives_book_type_guidance(tmp_path):
    p = new_project()
    add_photo(tmp_path, p, "a.jpg", jpg_bytes())
    client = MockClient({"chapters": []})
    generate_ai_story(client, "gpt-4.1-mini", p, book_label="Business record", guidance="Be factual.")
    sent = json.loads(client.args[0]["input"][1]["content"])
    assert sent["photobook_type"] == "Business record" and sent["photobook_structure"] == "Be factual."


def test_pdf_cover_uses_type_label(tmp_path):
    p = make_demo_project(tmp_path)
    p["cover_kicker"] = "IN LOVING MEMORY"
    text = " ".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(generate_pdf(p, tmp_path))).pages)
    assert "IN LOVING MEMORY" in text


def _gps_jpeg(gps: dict | None = None, date_in_subifd: str | None = None, xmp: bytes | None = None) -> bytes:
    img = Image.new("RGB", (400, 300), "#88aacc")
    exif = Image.Exif()
    if date_in_subifd:
        exif.get_ifd(0x8769)[36867] = date_in_subifd
    if gps:
        exif.get_ifd(0x8825).update(gps)
    buff = io.BytesIO()
    img.save(buff, format="JPEG", exif=exif)
    data = buff.getvalue()
    if xmp:
        seg = b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta><rdf:Description " + xmp + b"/></x:xmpmeta>"
        data = data[:2] + b"\xff\xe1" + (len(seg) + 2).to_bytes(2, "big") + seg + data[2:]
    return data


def test_gps_read_from_common_phone_formats():
    from PIL.TiffImagePlugin import IFDRational as Rat
    sydney = (-33.8688, 151.2093)
    cases = [
        _gps_jpeg({1: "S", 2: (Rat(33, 1), Rat(52, 1), Rat(768, 100)),
                   3: "E", 4: (Rat(151, 1), Rat(12, 1), Rat(3348, 100))}, "2024:11:21 18:05:00"),
        _gps_jpeg({1: "S", 2: (Rat(33, 1), Rat(52128, 1000), Rat(0, 0)),       # blank seconds
                   3: "E", 4: (Rat(151, 1), Rat(12558, 1000), Rat(0, 0))}),
        _gps_jpeg({1: "S", 2: (Rat(338688, 10000),), 3: "E", 4: (Rat(1512093, 10000),)}),  # degrees only
        _gps_jpeg({1: "S\x00", 2: (Rat(33, 1), Rat(52, 1), Rat(768, 100)),     # padded hemisphere
                   3: "E\x00", 4: (Rat(151, 1), Rat(12, 1), Rat(3348, 100))}),
        _gps_jpeg(xmp=b'exif:GPSLatitude="33,52.128S" exif:GPSLongitude="151,12.558E"'),  # XMP only
    ]
    for data in cases:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            gps = extract_metadata(img, data)["gps"]
        assert gps and (round(gps["latitude"], 3), round(gps["longitude"], 3)) == (round(sydney[0], 3), round(sydney[1], 3))
    with Image.open(io.BytesIO(cases[0])) as img:
        assert extract_metadata(img, cases[0])["capture_date"] == "2024-11-21"  # DateTimeOriginal in Exif sub-IFD


def test_gps_zero_zero_placeholder_ignored():
    from PIL.TiffImagePlugin import IFDRational as Rat
    zero = (Rat(0, 1), Rat(0, 1), Rat(0, 1))
    data = _gps_jpeg({1: "N", 2: zero, 3: "E", 4: zero})
    with Image.open(io.BytesIO(data)) as img:
        assert extract_metadata(img, data)["gps"] is None


def test_reread_updates_existing_photos_and_keeps_notes(tmp_path):
    from PIL.TiffImagePlugin import IFDRational as Rat
    from storybook.core import reread_metadata
    p = new_project()
    add_photo(tmp_path, p, "a.jpg", _gps_jpeg({1: "S", 2: (Rat(33, 1), Rat(52, 1), Rat(0, 0)),
                                               3: "E", 4: (Rat(151, 1), Rat(12, 1), Rat(0, 0))}))
    p["photos"][0]["metadata"]["gps"] = None          # as an older reader would have stored it
    p["photos"][0]["memory"] = "Harbour at dusk."
    assert reread_metadata(tmp_path, p) == 1
    assert p["photos"][0]["metadata"]["gps"]["latitude"] < -33
    assert p["photos"][0]["memory"] == "Harbour at dusk."


def test_sideways_phone_photo_is_displayed_upright(tmp_path):
    from storybook.core import display_image, remove_display_cache
    portrait = Image.new("RGB", (300, 400), "#9cc8e8")
    portrait.paste(Image.new("RGB", (300, 100), "#5d8a5e"), (0, 300))          # grass at the bottom
    stored = portrait.transpose(Image.Transpose.ROTATE_90)                       # saved sideways...
    exif = Image.Exif()
    exif[274] = 6                                                                # ...with "rotate to view"
    buff = io.BytesIO()
    stored.save(buff, "JPEG", exif=exif)
    p = new_project()
    add_photo(tmp_path, p, "phone.jpg", buff.getvalue())
    photo = p["photos"][0]
    assert photo["metadata"]["dimensions"] == [300, 400]
    shown = Image.open(io.BytesIO(display_image(tmp_path, p["id"], photo)))
    assert shown.size == (300, 400)
    r, g, b = shown.getpixel((150, 380))
    assert g > r and g > b                                                       # grass is at the bottom
    framed = Image.open(io.BytesIO(display_image(tmp_path, p["id"], photo, frame=(480, 360))))
    assert framed.size == (480, 360)
    remove_display_cache(tmp_path, p["id"], photo["id"])
    assert not list((tmp_path / p["id"] / "thumbs").glob("*.jpg"))


def test_story_writer_camera_location_is_opt_in_and_city_level_by_default(tmp_path):
    from PIL.TiffImagePlugin import IFDRational as Rat
    p = new_project()
    add_photo(tmp_path, p, "harbour.jpg", _gps_jpeg({1: "S", 2: (Rat(33, 1), Rat(51, 1), Rat(24, 1)),
                                                     3: "E", 4: (Rat(151, 1), Rat(12, 1), Rat(55, 1))}))
    add_photo(tmp_path, p, "outback.jpg", _gps_jpeg({1: "S", 2: (Rat(22, 1), Rat(0, 1), Rat(0, 1)),
                                                     3: "E", 4: (Rat(140, 1), Rat(0, 1), Rat(0, 1))}))
    add_photo(tmp_path, p, "scan.jpg", jpg_bytes())

    def sent(**kw):
        client = MockClient({"chapters": []})
        generate_ai_story(client, "gpt-4.1-mini", p, **kw)
        return {ph["photo_id"]: ph.get("camera_location_unverified")
                for ph in json.loads(client.args[0]["input"][1]["content"])["photos"]}

    ids = {x["filename"]: x["id"] for x in p["photos"]}
    off = sent()
    assert all(v is None for v in off.values())                           # default: nothing sent
    city = sent(share_location="city")
    assert city[ids["harbour.jpg"]] == "near Sydney, Australia"
    assert city[ids["outback.jpg"]] == "approximately -22.0, 140.0"       # no known town nearby
    assert city[ids["scan.jpg"]] is None
    exact = sent(share_location="exact")
    assert exact[ids["harbour.jpg"]].startswith("-33.85")


def test_web_book_is_self_contained_and_safe(tmp_path):
    from storybook.book_html import build_book_data, generate_html
    from storybook.demo import make_travel_demo_project
    p = make_travel_demo_project(tmp_path)
    p["title"] = 'Trip </script><script>alert(1)</script> & more'
    p["chapters"][0]["text"] = "<img src=x onerror=alert(1)>"
    html = generate_html(p, tmp_path)
    assert html.count("</script>") == 1                       # user text can't close the script tag
    assert "<img src=x" not in html                            # nor inject markup
    assert html.count("data:image/jpeg;base64,") == 8 * 2 + 1  # 8 photos (+ map thumbnails) and the world map
    assert "unpkg.com" not in html and "cartocdn" not in html  # map works offline, no location sent anywhere
    assert "<title>Trip &lt;/script&gt;" in html
    city = build_book_data(p, tmp_path)["stops"][0]
    assert (city["lat"], city["lon"]) == (35.6762, 139.6503)   # snapped to Tokyo centre by default
    exact = build_book_data(p, tmp_path, precise_map=True)["stops"][0]
    assert (exact["lat"], exact["lon"]) == (35.6895, 139.6917) # the photo's own location
    assert build_book_data(p, tmp_path, include_map=False)["stops"] == []


def test_when_and_where_filled_from_camera_once(tmp_path):
    from PIL.TiffImagePlugin import IFDRational as Rat
    from storybook.travel import autofill_from_camera
    from storybook.core import reread_metadata
    p = new_project()
    doha = {1: "N", 2: (Rat(25, 1), Rat(17, 1), Rat(5007, 100)), 3: "E", 4: (Rat(51, 1), Rat(32, 1), Rat(1262, 100))}
    add_photo(tmp_path, p, "20260919_112106.jpg", _gps_jpeg(doha, "2026:09:19 11:21:06"))
    add_photo(tmp_path, p, "typed.jpg", _gps_jpeg(doha, "2026:09:20 09:00:00"))
    photo, typed = p["photos"]
    typed.update({"place": "The Corniche", "event_date": "September 2026"})
    assert autofill_from_camera(photo) and autofill_from_camera(typed)
    assert (photo["event_date"], photo["place"]) == ("2026-09-19", "Doha, Qatar")
    assert photo["place_source"] == "camera location" and photo["event_date_source"] == "camera"
    assert (typed["event_date"], typed["place"]) == ("September 2026", "The Corniche")   # never overwritten
    photo["place"] = ""                                       # the user clears it on purpose...
    autofill_from_camera(photo)
    assert photo["place"] == ""                               # ...and it stays clear
    reread_metadata(tmp_path, p)                              # an explicit re-check may fill it again
    autofill_from_camera(photo)
    assert photo["place"] == "Doha, Qatar"


def test_share_links_can_be_created_replaced_and_turned_off(tmp_path):
    from storybook.core import disable_share, enable_share, find_shared
    p = make_demo_project(tmp_path)
    token = enable_share(p)
    save_project(tmp_path, p)
    assert find_shared(tmp_path, token)["id"] == p["id"]
    assert find_shared(tmp_path, "x" * 24) is None and find_shared(tmp_path, "../../etc") is None
    new = enable_share(p, new_link=True)
    save_project(tmp_path, p)
    assert new != token and find_shared(tmp_path, token) is None and find_shared(tmp_path, new)
    disable_share(p)
    save_project(tmp_path, p)
    assert find_shared(tmp_path, new) is None
