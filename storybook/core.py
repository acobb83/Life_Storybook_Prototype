"""Local project storage, photo validation, and metadata extraction."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

# A sensible PoC limit, not a guarantee against adversarial inputs.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 45_000_000
MAX_PHOTOS = 30
SUPPORTED_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "HEIF": ".heic"}
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class InvalidPhoto(ValueError):
    pass


def register_heif() -> bool:
    """HEIC is optional; pip install pillow-heif to enable it."""
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
        return True
    except ImportError:
        return False


def _num(v) -> float | None:
    """One EXIF number: IFDRational, (numerator, denominator), int or float. Blank (0/0) -> None."""
    try:
        if isinstance(v, tuple) and len(v) == 2:
            return None if not v[1] else float(v[0]) / float(v[1])
        f = float(v)
        return None if f != f else f  # NaN check
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None


def _ref(value, default: str) -> str:
    if isinstance(value, bytes):
        value = value.decode("ascii", "ignore")
    value = str(value or "").strip("\x00 ").upper()
    return value[:1] if value[:1] in ("N", "S", "E", "W") else default


def _gps_to_decimal(values, hemisphere: str) -> float | None:
    """Degrees/minutes/seconds (any of 1-3 parts; a blank part counts as 0) to signed decimal."""
    if values is None:
        return None
    parts = list(values) if isinstance(values, (tuple, list)) else [values]
    if not parts:
        return None
    nums = ([_num(x) for x in parts[:3]] + [None, None])[:3]
    if nums[0] is None:
        return None
    result = nums[0] + (nums[1] or 0) / 60 + (nums[2] or 0) / 3600
    if hemisphere in ("S", "W"):
        result = -abs(result)
    return round(result, 6)


def _valid_gps(lat, lon) -> bool:
    return (lat is not None and lon is not None and abs(lat) <= 90 and abs(lon) <= 180
            and not (abs(lat) < 1e-6 and abs(lon) < 1e-6))  # 0,0 is a "no fix" placeholder


_XMP_GPS = re.compile(rb"exif:GPS(Latitude|Longitude)(?:=\"|>)\s*([0-9.,]+)\s*([NSEW])", re.I)


def _xmp_gps(raw: bytes) -> dict | None:
    """GPS written as XMP (e.g. some editing and export tools): '33,52.128S' or '33,52,7.68S'."""
    found = {}
    for kind, value, ref in _XMP_GPS.findall(raw[:2_000_000]):
        nums = [float(x) for x in value.decode().split(",") if x]
        if not nums:
            continue
        dec = nums[0] + (nums[1] if len(nums) > 1 else 0) / 60 + (nums[2] if len(nums) > 2 else 0) / 3600
        found[kind.decode().lower()] = -dec if ref.upper() in (b"S", b"W") else dec
    lat, lon = found.get("latitude"), found.get("longitude")
    return {"latitude": round(lat, 6), "longitude": round(lon, 6)} if _valid_gps(lat, lon) else None


def extract_metadata(image: Image.Image, raw: bytes | None = None) -> dict:
    """Read EXIF (and XMP GPS as a fallback); never assume missing/incorrect timestamps are facts."""
    meta = {"capture_date": None, "date_source": None, "gps": None, "gps_source": None,
            "camera": None, "dimensions": list(image.size), "format": image.format}
    try:
        exif = image.getexif()
    except (AttributeError, OSError, ValueError, TypeError):
        exif = None
    try:
        if exif is not None and exif.get(274) in (5, 6, 7, 8):  # Orientation: rotated 90/270
            meta["dimensions"] = [image.size[1], image.size[0]]
    except (AttributeError, TypeError):
        pass
    if exif is not None:
        # Each part is read separately so one odd value can't wipe out the others.
        try:
            try:
                sub = exif.get_ifd(0x8769)  # Exif sub-IFD holds DateTimeOriginal on most cameras
            except (KeyError, AttributeError, OSError, ValueError, TypeError):
                sub = {}
            for tag in (36867, 36868, 306):  # DateTimeOriginal, DateTimeDigitized, DateTime
                value = sub.get(tag) or exif.get(tag)
                if value:
                    match = re.match(r"^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})", str(value).strip())
                    if match and match[1] != "0000":
                        meta["capture_date"] = f"{match[1]}-{match[2]}-{match[3]}"
                        meta["date_source"] = "EXIF camera timestamp (timezone unverified)"
                        break
        except (AttributeError, KeyError, OSError, ValueError, TypeError):
            pass
        try:
            make = str(exif.get(271, "") or "").strip("\x00 ")
            model = str(exif.get(272, "") or "").strip("\x00 ")
            meta["camera"] = " ".join(x for x in (make, model) if x)[:120] or None
        except (AttributeError, ValueError, TypeError):
            pass
        try:
            gps = exif.get_ifd(0x8825)  # GPSInfo
            if gps:
                lat = _gps_to_decimal(gps.get(2), _ref(gps.get(1), "N"))
                lon = _gps_to_decimal(gps.get(4), _ref(gps.get(3), "E"))
                if _valid_gps(lat, lon):
                    meta["gps"] = {"latitude": lat, "longitude": lon}
                    meta["gps_source"] = "EXIF"
        except (AttributeError, KeyError, OSError, ValueError, TypeError):
            pass
    if meta["gps"] is None and raw:
        xmp = _xmp_gps(raw)
        if xmp:
            meta["gps"], meta["gps_source"] = xmp, "XMP"
    return meta


def reread_metadata(root: Path, project: dict) -> int:
    """Re-read camera data for photos already uploaded (e.g. after a reader improvement).
    Only the camera metadata is replaced; the user's own notes are untouched. Returns how many
    photos now have a location."""
    for photo in project.get("photos", []):
        try:
            path = photo_path(root, project["id"], photo)
            raw = path.read_bytes()
            with Image.open(io.BytesIO(raw)) as img:
                img.load()  # some formats (e.g. PNG) only expose EXIF once fully loaded
                photo["metadata"] = extract_metadata(img, raw)
        except (OSError, ValueError, UnidentifiedImageError):
            continue
    save_project(root, project)
    return sum(bool(p.get("metadata", {}).get("gps")) for p in project.get("photos", []))


def _load_validated(data: bytes) -> tuple[Image.Image, str]:
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise InvalidPhoto("The image is empty or exceeds the 20 MB per-file limit.")
    try:
        img = Image.open(io.BytesIO(data))
        fmt = (img.format or "").upper()
        if fmt not in SUPPORTED_FORMATS:
            raise InvalidPhoto("Supported formats: JPEG, PNG, WebP and optional HEIC.")
        if img.width * img.height > MAX_PIXELS:
            raise InvalidPhoto("Image has too many pixels (45 MP limit).")
        img.load()
        return img, fmt
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as e:
        if isinstance(e, InvalidPhoto):
            raise
        raise InvalidPhoto(f"Invalid or damaged image: {e}") from e


def new_project(title: str = "Our Life in Pictures") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {"id": uuid.uuid4().hex, "title": title, "subtitle": "A collection of moments worth remembering",
            "dedication": "", "intro": "", "instructions": "", "voice": "Warm and reflective",
            "photos": [], "chapters": [], "created_at": now, "updated_at": now}


def _folder(root: Path, project_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", project_id):
        raise ValueError("Invalid project identifier")
    return Path(root) / project_id


def save_project(root: Path, project: dict) -> None:
    folder = _folder(root, project["id"])
    folder.mkdir(parents=True, exist_ok=True)
    project["updated_at"] = datetime.now(timezone.utc).isoformat()
    fd, tmp_path = tempfile.mkstemp(prefix=".project-", suffix=".json", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(project, stream, indent=2, ensure_ascii=False)
        os.replace(tmp_path, folder / "project.json")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def load_project(root: Path, project_id: str) -> dict:
    with (_folder(root, project_id) / "project.json").open(encoding="utf-8") as f:
        return json.load(f)


def list_projects(root: Path) -> list[dict]:
    result = []
    if not Path(root).exists():
        return result
    for file in Path(root).glob("*/project.json"):
        try:
            project = json.loads(file.read_text(encoding="utf-8"))
            if re.fullmatch(r"[0-9a-f]{32}", project.get("id", "")):
                result.append({"id": project["id"], "title": project.get("title", "Untitled"),
                               "book_type": project.get("book_type", ""),
                               "updated_at": project.get("updated_at", "")})
        except (OSError, ValueError):
            continue
    return sorted(result, key=lambda x: x["updated_at"], reverse=True)


def delete_project(root: Path, project_id: str) -> None:
    shutil.rmtree(_folder(root, project_id), ignore_errors=True)


def photo_path(root: Path, project_id: str, photo: dict) -> Path:
    filename = photo.get("path", "")
    if not re.fullmatch(r"images/[0-9a-f]{64}\.(jpg|png|webp|heic)", filename):
        raise ValueError("Unsafe photo path")
    return _folder(root, project_id) / filename


def add_photo(root: Path, project: dict, filename: str, data: bytes) -> bool:
    """Returns False for duplicates; never overwrite the original file."""
    digest = hashlib.sha256(data).hexdigest()
    if any(p["id"] == digest for p in project["photos"]):
        return False
    if len(project["photos"]) >= MAX_PHOTOS:
        raise InvalidPhoto(f"This prototype supports at most {MAX_PHOTOS} photographs per project.")
    img, fmt = _load_validated(data)
    try:
        metadata = extract_metadata(img, data)
    finally:
        img.close()
    folder = _folder(root, project["id"])
    (folder / "images").mkdir(parents=True, exist_ok=True)
    path = f"images/{digest}{SUPPORTED_FORMATS[fmt]}"
    (folder / path).write_bytes(data)
    name = re.sub(r"[\x00-\x1f\x7f]", "", Path(filename.replace("\\", "/")).name)[:140]
    project["photos"].append({"id": digest, "path": path, "filename": name, "metadata": metadata,
                              "observation": "", "caption": "", "event_date": "", "place": "",
                              "people": "", "memory": "", "analyzed": False})
    save_project(root, project)
    return True


DISPLAY_BG = "#F5EFE8"


def display_image(root: Path, project_id: str, photo: dict, max_edge: int = 1200,
                  frame: tuple[int, int] | None = None) -> bytes:
    """An upright JPEG for showing in the app. Phone cameras store many photos sideways with an
    EXIF 'orientation' tag; browsers and resizing can ignore it, so we rotate here once.
    With `frame` (w, h) the whole photo is fitted inside a fixed box (no cropping) so grids line up.
    Results are cached next to the project's images."""
    if not re.fullmatch(r"[0-9a-f]{64}", photo.get("id", "")):
        raise ValueError("Invalid photo id")
    tag = f"f{frame[0]}x{frame[1]}" if frame else f"m{max_edge}"
    cache = _folder(root, project_id) / "thumbs" / f"{photo['id']}_{tag}.jpg"
    if cache.exists():
        return cache.read_bytes()
    with Image.open(photo_path(root, project_id, photo)) as src:
        img = ImageOps.exif_transpose(src).convert("RGB")
    if frame:
        img.thumbnail(frame)
        canvas = Image.new("RGB", frame, DISPLAY_BG)
        canvas.paste(img, ((frame[0] - img.width) // 2, (frame[1] - img.height) // 2))
        img = canvas
    else:
        img.thumbnail((max_edge, max_edge))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    data = buffer.getvalue()
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(data)
    except OSError:
        pass  # caching is a nicety; display still works
    return data


def remove_display_cache(root: Path, project_id: str, photo_id: str) -> None:
    if re.fullmatch(r"[0-9a-f]{64}", photo_id or ""):
        for f in (_folder(root, project_id) / "thumbs").glob(f"{photo_id}_*.jpg"):
            f.unlink(missing_ok=True)


def jpeg_preview_bytes(path: Path, max_edge: int = 1280, quality: int = 80) -> bytes:
    """Normalise orientation and strip EXIF/GPS from the image sent to a model."""
    with Image.open(path) as src:
        rgb = ImageOps.exif_transpose(src).convert("RGB")
        rgb.thumbnail((max_edge, max_edge))
        buffer = io.BytesIO()
        rgb.save(buffer, format="JPEG", quality=quality)
        return buffer.getvalue()


def photo_year(photo: dict) -> int | None:
    """Year from the user's corrected date, falling back to the (unverified) camera date."""
    value = photo.get("event_date") or photo.get("metadata", {}).get("capture_date") or ""
    match = re.search(r"\b(18\d{2}|19\d{2}|20\d{2}|21\d{2})\b", str(value))
    return int(match[1]) if match else None


def select_photos(project: dict, years: tuple[int, int] | None = None,
                  places: list[str] | None = None, include_undated: bool = True) -> list[dict]:
    """The memories that match an 'Ask for a story' request, in chronological order."""
    chosen = []
    for photo in chronological_photos(project):
        year = photo_year(photo)
        if years and year is not None and not (years[0] <= year <= years[1]):
            continue
        if years and year is None and not include_undated:
            continue
        if places and photo.get("place", "").strip() not in places:
            continue
        chosen.append(photo)
    return chosen


def chronological_photos(project: dict) -> list[dict]:
    def sortkey(p):
        value = p.get("event_date", "") or p.get("metadata", {}).get("capture_date") or ""
        match = re.search(r"\b(18\d{2}|19\d{2}|20\d{2}|21\d{2})(?:-(\d{2})(?:-(\d{2}))?)?", value)
        return (0, int(match[1]), int(match[2] or 1), int(match[3] or 1)) if match else (1, 9999, 12, 31)
    return sorted(project.get("photos", []), key=sortkey)
