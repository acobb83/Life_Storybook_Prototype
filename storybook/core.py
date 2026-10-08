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


def _gps_float(v) -> float:
    return float(v)


def _gps_to_decimal(values, hemisphere: str) -> float | None:
    try:
        degrees, minutes, seconds = (_gps_float(x) for x in values)
        result = degrees + minutes / 60 + seconds / 3600
        if hemisphere in ("S", "W"):
            result = -result
        return round(result, 6)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError):
        return None


def extract_metadata(image: Image.Image) -> dict:
    """Read EXIF; never assume missing/incorrect timestamps are facts."""
    meta = {"capture_date": None, "date_source": None, "gps": None,
            "camera": None, "dimensions": list(image.size), "format": image.format}
    try:
        exif = image.getexif()
        for tag in (36867, 36868, 306):  # DateTimeOriginal, DateTimeDigitized, DateTime
            value = exif.get(tag)
            if value:
                s = str(value).strip()
                match = re.match(r"^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})", s)
                if match:
                    meta["capture_date"] = f"{match[1]}-{match[2]}-{match[3]}"
                    meta["date_source"] = "EXIF camera timestamp (timezone unverified)"
                    break
        make = str(exif.get(271, "") or "").strip()
        model = str(exif.get(272, "") or "").strip()
        meta["camera"] = " ".join(x for x in (make, model) if x)[:120] or None
        from PIL import ExifTags
        gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
        if gps:
            lat_ref = gps.get(1, "N")
            lon_ref = gps.get(3, "E")
            if isinstance(lat_ref, bytes): lat_ref = lat_ref.decode("ascii", "ignore")
            if isinstance(lon_ref, bytes): lon_ref = lon_ref.decode("ascii", "ignore")
            lat, lon = _gps_to_decimal(gps.get(2, ()), str(lat_ref)), _gps_to_decimal(gps.get(4, ()), str(lon_ref))
            if lat is not None and lon is not None and abs(lat) <= 90 and abs(lon) <= 180:
                meta["gps"] = {"latitude": lat, "longitude": lon}
    except (AttributeError, KeyError, OSError, ValueError, TypeError):
        # EXIF is optional and is notoriously inconsistent across devices.
        pass
    return meta


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
        metadata = extract_metadata(img)
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


def jpeg_preview_bytes(path: Path, max_edge: int = 1280, quality: int = 80) -> bytes:
    """Normalise orientation and strip EXIF/GPS from the image sent to a model."""
    with Image.open(path) as src:
        rgb = ImageOps.exif_transpose(src).convert("RGB")
        rgb.thumbnail((max_edge, max_edge))
        buffer = io.BytesIO()
        rgb.save(buffer, format="JPEG", quality=quality)
        return buffer.getvalue()


def chronological_photos(project: dict) -> list[dict]:
    def sortkey(p):
        value = p.get("event_date", "") or p.get("metadata", {}).get("capture_date") or ""
        match = re.search(r"\b(18\d{2}|19\d{2}|20\d{2}|21\d{2})(?:-(\d{2})(?:-(\d{2}))?)?", value)
        return (0, int(match[1]), int(match[2] or 1), int(match[3] or 1)) if match else (1, 9999, 12, 31)
    return sorted(project.get("photos", []), key=sortkey)
