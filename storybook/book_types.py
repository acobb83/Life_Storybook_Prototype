"""Kinds of photobook. The type chosen up front shapes prompts, chapter grouping, the main
story view, the default writing voice and the book cover. Users can change it later."""
from __future__ import annotations

import calendar
import re

from .ai import generate_local_story
from .core import chronological_photos, photo_year
from .travel import build_trips, chapters_from_trips, photo_date

BOOK_TYPES: dict[str, dict] = {
    "life": {
        "label": "Life story", "icon": "📖",
        "blurb": "A life told in chapters, from the early days to now.",
        "good_for": "A parent's or grandparent's story, “my life so far”",
        "request_hint": "e.g. Tell the story of Mum's life, from childhood to today",
        "examples": ["Growing up", "Dad's working life", "My life so far"],
        "title": "Our Life in Pictures", "subtitle": "A collection of moments worth remembering",
        "kicker": "A LIFE STORY", "grouping": "era", "primary_view": "timeline",
        "voice": "Warm and reflective", "memory_label": "What do you remember?",
        "guidance": "Tell the life in chronological chapters by life stage (for example early years, "
                    "school, work, family), as far as the user's notes support.",
    },
    "travel": {
        "label": "Travel story", "icon": "🌏",
        "blurb": "Your trips on a world map, one chapter per destination.",
        "good_for": "A big holiday, a gap year, every trip you've taken together",
        "request_hint": "e.g. Relive our trip through Japan in 2019",
        "examples": ["Our honeymoon", "Japan 2019", "Every trip we've taken"],
        "title": "Our Travels", "subtitle": "Places we went and the moments we brought home",
        "kicker": "A TRAVEL STORY", "grouping": "destination", "primary_view": "travels",
        "voice": "Joyful and celebratory", "memory_label": "What happened here?",
        "guidance": "Make one chapter per destination in the order visited, using the place names the "
                    "user gave. Do not add sights, food or events the user did not mention.",
    },
    "milestone": {
        "label": "Milestone celebration", "icon": "🎉",
        "blurb": "Build up to a big day, ending with the celebration itself.",
        "good_for": "An 18th or 21st, a wedding, an anniversary, a retirement",
        "request_hint": "e.g. Celebrate Sophie's 18th, from her first steps to today",
        "examples": ["An 18th birthday", "A 40th anniversary", "A retirement"],
        "title": "A Celebration", "subtitle": "The moments that led to this day",
        "kicker": "A CELEBRATION", "grouping": "era", "primary_view": "read",
        "voice": "Joyful and celebratory", "memory_label": "What do you remember?",
        "guidance": "Build chronologically toward the milestone named in the request and finish with "
                    "a short celebratory chapter. Do not invent details of the occasion.",
    },
    "year": {
        "label": "Year in review", "icon": "📅",
        "blurb": "Twelve months of moments, month by month.",
        "good_for": "A family's year, a baby's first year, a school year",
        "request_hint": "e.g. Our family's 2025, month by month",
        "examples": ["Our 2025", "Baby's first year", "Year 12"],
        "title": "Our Year", "subtitle": "Twelve months worth remembering",
        "kicker": "A YEAR IN REVIEW", "grouping": "month", "primary_view": "timeline",
        "voice": "Warm and reflective", "memory_label": "What do you remember?",
        "guidance": "Make one chapter per month in order (combine quiet months into a season if "
                    "there are few photos).",
    },
    "memorial": {
        "label": "In memory of", "icon": "🕯️",
        "blurb": "A gentle tribute to someone who has passed, in the words of those who loved them.",
        "good_for": "A funeral or memorial, an anniversary of a loss",
        "request_hint": "e.g. Remembering Grandpa Joe, 1938–2025",
        "examples": ["Remembering Grandpa", "For Mum", "A life well lived"],
        "title": "In Loving Memory", "subtitle": "Remembered with love",
        "kicker": "IN LOVING MEMORY", "grouping": "era", "primary_view": "read",
        "voice": "Gentle and poetic", "memory_label": "What do you remember about them?",
        "guidance": "Write a respectful, gentle tribute that celebrates their life using only the "
                    "memories given. Do not speculate about illness, death or private matters.",
    },
    "family": {
        "label": "Family history", "icon": "🌳",
        "blurb": "Generations of photos and stories, decade by decade.",
        "good_for": "Old scanned photos, a family reunion, a heritage project",
        "request_hint": "e.g. Our family from the 1950s to today",
        "examples": ["Three generations", "Our family since 1950", "Where we came from"],
        "title": "Our Family Story", "subtitle": "Across the generations",
        "kicker": "A FAMILY HISTORY", "grouping": "decade", "primary_view": "timeline",
        "voice": "Simple and factual", "memory_label": "What is the story behind this photo?",
        "guidance": "Organise chapters by decade or generation in order. Old photos often have "
                    "uncertain dates: keep the user's wording such as 'around 1960'.",
    },
    "business": {
        "label": "Business record", "icon": "🏢",
        "blurb": "A dated, factual record of a project, site, event or company's story.",
        "good_for": "Project or site progress, an event recap, a company history, a handover pack",
        "request_hint": "e.g. Document the office fit-out from site handover to opening day",
        "examples": ["Site progress 2025", "Annual conference recap", "Our first ten years"],
        "title": "Project Record", "subtitle": "A photographic record of the work",
        "kicker": "A PROJECT RECORD", "grouping": "month", "primary_view": "timeline",
        "voice": "Clear and professional", "memory_label": "What does this photo record?",
        "people_label": "Team, client or partners involved",
        "guidance": "Write a clear, factual record in a professional third-person voice, in date order, "
                    "one chapter per month or project phase. State what was done, where and when, using "
                    "only the user's notes. No marketing claims, no invented figures, and only name "
                    "people or companies the user named.",
    },
}
TYPE_ORDER = ["life", "travel", "milestone", "year", "memorial", "family", "business"]

GROUPING_TEXT = {
    "era": "life stage, in date order",
    "destination": "destination, in the order you visited",
    "month": "month",
    "decade": "decade",
}


def get_type(project: dict) -> dict:
    return BOOK_TYPES.get(project.get("book_type") or "life", BOOK_TYPES["life"])


def apply_type(project: dict, key: str, set_defaults: bool = True) -> None:
    """Set the photobook type. Title/subtitle/voice defaults only replace untouched defaults."""
    old = get_type(project) if project.get("book_type") else None
    new = BOOK_TYPES[key]
    project["book_type"] = key
    project["cover_kicker"] = new["kicker"]
    if set_defaults:
        for field in ("title", "subtitle"):
            if not project.get(field) or (old and project.get(field) == old[field]) or \
                    project.get(field) in ("Our Life in Pictures", "A collection of moments worth remembering"):
                project[field] = new[field]
        if not old or project.get("voice") == old["voice"]:
            project["voice"] = new["voice"]


def _notes(photos: list[dict]) -> str:
    """Join the user's own captions and memories; nothing is invented."""
    lines = []
    for p in photos:
        moment = (p.get("caption", "").strip() or p.get("observation", "").strip()).rstrip(".!? ")
        memory = p.get("memory", "").strip()
        text = " ".join(x for x in ((moment + ".") if moment else "", memory) if x)
        lines.append(text or "Add a memory to tell the story behind this photo.")
    return "\n\n".join(lines)


def _group(photos: list[dict], key_fn, title_fn) -> list[dict]:
    groups: dict = {}
    for p in chronological_photos({"photos": photos}):
        groups.setdefault(key_fn(p), []).append(p)
    ordered = sorted(groups, key=lambda k: (k is None, k or ""))
    return [{"title": title_fn(k), "text": _notes(groups[k]), "photo_ids": [p["id"] for p in groups[k]]}
            for k in ordered]


def _month_key(p: dict) -> str | None:
    m = re.search(r"\b(1[89]\d{2}|20\d{2}|21\d{2})-(\d{2})", photo_date(p))
    if m:
        return f"{m[1]}-{m[2]}"
    year = photo_year(p)
    return f"{year}" if year else None


def _month_title(k: str | None) -> str:
    if k is None:
        return "Moments without a date"
    if "-" in k:
        y, m = k.split("-")
        return f"{calendar.month_name[int(m)]} {y}"
    return k


def _decade_key(p: dict) -> str | None:
    year = photo_year(p)
    return f"{year // 10 * 10}" if year else None


def local_chapters(project: dict, photos: list[dict]) -> list[dict]:
    """A no-AI draft grouped the way this photobook type expects."""
    grouping = get_type(project)["grouping"]
    if grouping == "destination":
        stops, unmapped = build_trips(photos)
        chapters = chapters_from_trips(stops, photos)
        if unmapped:
            chapters.append({"title": "Along the way", "text": _notes(unmapped),
                             "photo_ids": [p["id"] for p in unmapped]})
        return chapters
    if grouping == "month":
        return _group(photos, _month_key, _month_title)
    if grouping == "decade":
        return _group(photos, _decade_key, lambda k: f"The {k}s" if k else "Undated photographs")
    return generate_local_story(dict(project, photos=photos))
