"""Fictional, clearly labelled illustrated demo with no external image downloads."""
from __future__ import annotations

import io
from PIL import Image, ImageDraw, ImageFont

from .core import new_project, add_photo, save_project
from .ai import generate_local_story

SCENES = [
    ("Beach afternoons", "1998-01-14", "Gold Coast, Queensland", "Mum, Dad, my sister and me",
     "Dad taught us to swim that summer, and we stayed until the sun began to set.",
     ("#f9deb5", "#74b5be", "#eab975")),
    ("Our little backyard", "2002-09-08", "Our first family home", "My sister and me",
     "We spent whole afternoons building imaginary worlds in the garden.",
     ("#d9e9e4", "#8fb9a2", "#e4b78f")),
    ("A new beginning", "2010-12-02", "School graduation", "My classmates and me",
     "After years of studying together, this was the day we celebrated finishing school.",
     ("#f4decf", "#9da9bb", "#6b768d")),
    ("Time together", "2018-06-21", "Blue Mountains", "Our family",
     "We walked the trails, shared stories, and enjoyed a rare weekend together.",
     ("#d8e5e6", "#94b3aa", "#5e867a")),
]


# Approximate public coordinates for two of the fictional scenes, written into the demo
# images' EXIF so the Map view has something to show. Other scenes deliberately have none.
DEMO_GPS = {0: (-28.0167, 153.4000), 3: (-33.7125, 150.3119)}  # Gold Coast, Katoomba


def _exif_for(date: str, gps: tuple[float, float] | None) -> Image.Exif:
    from PIL.TiffImagePlugin import IFDRational
    exif = Image.Exif()
    exif[36867] = date.replace("-", ":") + " 10:00:00"  # DateTimeOriginal
    if gps:
        def dms(value: float):
            value = abs(value); d = int(value); m = int((value - d) * 60)
            s = round(((value - d) * 60 - m) * 60, 2)
            return (IFDRational(d, 1), IFDRational(m, 1), IFDRational(int(s * 100), 100))
        gps_ifd = exif.get_ifd(0x8825)
        gps_ifd.update({1: "S" if gps[0] < 0 else "N", 2: dms(gps[0]),
                        3: "W" if gps[1] < 0 else "E", 4: dms(gps[1])})
    return exif


def illustrated_card(title: str, colors: tuple[str, str, str], n: int,
                     date: str = "", gps: tuple[float, float] | None = None) -> bytes:
    """A non-photographic placeholder; never presented as a genuine user's photo."""
    w, h = 1000, 690
    img = Image.new("RGB", (w, h), colors[0]); d = ImageDraw.Draw(img)
    d.ellipse((690, 80, 870, 260), fill="#fff5cf")
    if n == 0:
        d.rectangle((0, 330, w, 535), fill=colors[1]); d.rectangle((0, 535, w, h), fill=colors[2])
        for x, y in ((360, 455), (455, 470), (520, 465), (610, 450)):
            d.ellipse((x-25,y-95,x+25,y-45), fill="#455e63")
            d.line((x,y-35,x,y+45), fill="#455e63", width=22)
    elif n == 1:
        d.rectangle((0, 465, w, h), fill=colors[1]); d.rectangle((180, 260, 680, 500), fill=colors[2]);
        d.polygon([(130,270),(430,110),(730,270)],fill="#805b60")
        d.rectangle((385, 365, 470, 500), fill="#f3e5d3")
        d.ellipse((70,170,250,445),fill="#7cad9a");d.rectangle((145,300,175,510),fill="#72645c")
    elif n == 2:
        d.rectangle((0, 500, w, h), fill=colors[1]); d.polygon([(310,280),(510,190),(710,280),(710,480),(310,480)], fill=colors[2]);
        for x in (365,465,565,665): d.line((x,285,x,410), fill="#ffffff",width=12)
        d.ellipse((455,275,555,375),fill="#e9d09f")
        d.polygon([(410,290),(510,200),(610,290)],fill="#304a5e")
    else:
        d.polygon([(0,515),(330,180),(600,515)],fill=colors[1]); d.polygon([(340,515),(700,155),(1000,515)],fill=colors[2]);
        d.rectangle((0,515,w,h), fill="#a4bcb0")
        for x in (150,370,650,840):
            d.line((x,580,x,425), fill="#4b766b",width=16)
            d.polygon([(x-65,490),(x,325),(x+65,490)], fill="#5c8c7d")
    d.rounded_rectangle((45,540,610,650), 19, fill="#f8f4eb")
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 32)
    except OSError:
        font = ImageFont.load_default()
    d.text((75,574),title,fill="#173140",font=font)
    bio = io.BytesIO()
    if date:
        img.save(bio, format="JPEG", quality=87, exif=_exif_for(date, gps))
    else:
        img.save(bio, format="JPEG", quality=87)
    return bio.getvalue()


def make_demo_project(root):
    project = new_project("The Moments That Made Us")
    project["subtitle"] = "A fictional family story - sample project"
    project["intro"] = "This book uses synthetic illustrations and invented sample memories to demonstrate the workflow. Replace every sample with your own photographs and experiences."
    project["dedication"] = "For the people who make ordinary days extraordinary."
    save_project(root, project)
    for idx, (title, date, place, people, memory, palette) in enumerate(SCENES):
        add_photo(root, project, f"demo_illustration_{idx + 1}.jpg", illustrated_card(title, palette, idx, date, DEMO_GPS.get(idx)))
        p = project["photos"][-1]
        p.update({"caption": title, "event_date": date, "place": place,
                  "people": people, "memory": memory,
                  "observation": "Illustrative demo artwork (not AI analysis)."})
    project["chapters"] = generate_local_story(project)
    save_project(root, project)
    return project


# ------------------------- Fictional travel demo -------------------------
# (caption, date, typed place, camera GPS or None, memory, scene style, palette)
TRAVELS = [
    ("Blossoms by the river", "2019-04-12", "Shinjuku, Tokyo", (35.6895, 139.6917),
     "Our first morning in Japan. We walked for hours under the blossoms, jet-lagged and happy.",
     "city", ("#fbe3ea", "#e7a6bd", "#5d6b8a")),
    ("Lanterns at dusk", "2019-04-13", "Asakusa, Tokyo", None,
     "We found a tiny restaurant down a side street and pointed at the menu.", "night",
     ("#2c3561", "#e98d6b", "#1d2443")),
    ("Temple gardens", "2019-04-15", "Kyoto", (35.0116, 135.7681),
     "A slow day of gardens and green tea before the train home.", "hills",
     ("#e4efe0", "#94b89a", "#5f8770")),
    ("Gardens by the bay", "2022-08-08", "Marina Bay, Singapore", (1.2834, 103.8607),
     "A stopover that turned into our favourite two days of the year.", "city",
     ("#dff1f1", "#6fb7b7", "#3f6f86")),
    ("Hawker centre dinner", "2022-08-09", "Singapore", None,
     "Chilli crab, sticky hands, and far too much food.", "night",
     ("#283a5a", "#f2b84b", "#18263d")),
    ("Harbour ferry", "2024-11-21", "Sydney Harbour, Sydney", (-33.8568, 151.2153),
     "We took the ferry at sunset to celebrate the new job.", "harbour",
     ("#fde6cf", "#7cb3d4", "#3e6e91")),
    ("Morning by the river", "2025-05-16", "Paris, France", (48.8566, 2.3522),
     "Croissants on a bench by the river. Rain, then sunshine.", "city",
     ("#ece8f5", "#a28ac9", "#5a5f86")),
    ("Up the hill", "2025-05-17", "Montmartre, Paris", None,
     "We climbed every step and watched the city light up.", "hills",
     ("#f3e3d6", "#c99a8a", "#6e5a6e")),
    ("A village we never learned the name of", "2025-05-19", "A little village on the drive south", None,
     "We stopped for lunch and stayed all afternoon.", "hills",
     ("#eef0dc", "#b7c58f", "#7a8a5c")),
]


def travel_postcard(title: str, style: str, colors: tuple[str, str, str], seed: int) -> Image.Image:
    """A simple illustrated postcard; synthetic artwork, never a real photo."""
    import random
    rnd = random.Random(seed)
    w, h = 1000, 690
    img = Image.new("RGB", (w, h), colors[0]); d = ImageDraw.Draw(img)
    d.ellipse((700, 70, 860, 230), fill="#fff5cf" if style != "night" else "#f4f1e0")
    if style == "night":
        for _ in range(40):
            x, y = rnd.randint(0, w), rnd.randint(0, 300)
            d.ellipse((x, y, x + 3, y + 3), fill="#f4f1e0")
    if style == "hills":
        d.polygon([(0, 480), (250, 300), (520, 470), (760, 280), (1000, 450), (1000, h), (0, h)], fill=colors[1])
        d.polygon([(0, 560), (400, 430), (1000, 540), (1000, h), (0, h)], fill=colors[2])
    else:
        base = 520 if style == "harbour" else 560
        x = 0
        while x < w:
            bw, bh = rnd.randint(50, 110), rnd.randint(90, 330)
            d.rectangle((x, base - bh, x + bw - 6, base), fill=colors[2])
            for wy in range(base - bh + 18, base - 10, 30):
                for wx in range(x + 10, x + bw - 16, 22):
                    if rnd.random() < (0.55 if style == "night" else 0.25):
                        d.rectangle((wx, wy, wx + 8, wy + 12), fill="#ffe7a3" if style == "night" else colors[0])
            x += bw
        d.rectangle((0, base, w, h), fill=colors[1])
        if style == "harbour":
            d.polygon([(380, 600), (620, 600), (590, 640), (410, 640)], fill="#f8f4eb")
            d.rectangle((470, 560, 530, 600), fill="#f8f4eb")
    d.rounded_rectangle((45, 560, 760, 650), 19, fill="#f8f4eb")
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 30)
    except OSError:
        font = ImageFont.load_default()
    d.text((75, 588), title[:40], fill="#1f2d4a", font=font)
    return img


def make_travel_demo_project(root):
    from .travel import build_trips, chapters_from_trips
    project = new_project("Our Travels")
    project["subtitle"] = "A fictional travel story - sample project"
    project["intro"] = ("This collection uses synthetic postcard illustrations and invented memories to "
                        "demonstrate the Travels view. Replace them with your own photos.")
    project["story_request"] = "Relive our travels"
    save_project(root, project)
    for idx, (caption, date, place, gps, memory, style, palette) in enumerate(TRAVELS):
        img = travel_postcard(caption, style, palette, idx)
        bio = io.BytesIO()
        img.save(bio, format="JPEG", quality=87, exif=_exif_for(date, gps))
        add_photo(root, project, f"travel_postcard_{idx + 1}.jpg", bio.getvalue())
        project["photos"][-1].update({"caption": caption, "event_date": date, "place": place,
                                      "memory": memory,
                                      "observation": "Illustrative demo artwork (not AI analysis)."})
    stops, _ = build_trips(project["photos"])
    project["chapters"] = chapters_from_trips(stops, project["photos"])
    save_project(root, project)
    return project
