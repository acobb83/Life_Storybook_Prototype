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


def illustrated_card(title: str, colors: tuple[str, str, str], n: int) -> bytes:
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
    bio = io.BytesIO(); img.save(bio, format="JPEG", quality=87)
    return bio.getvalue()


def make_demo_project(root):
    project = new_project("The Moments That Made Us")
    project["subtitle"] = "A fictional family story - sample project"
    project["intro"] = "This book uses synthetic illustrations and invented sample memories to demonstrate the workflow. Replace every sample with your own photographs and experiences."
    project["dedication"] = "For the people who make ordinary days extraordinary."
    save_project(root, project)
    for idx, (title, date, place, people, memory, palette) in enumerate(SCENES):
        add_photo(root, project, f"demo_illustration_{idx + 1}.jpg", illustrated_card(title,palette,idx))
        p = project["photos"][-1]
        p.update({"caption": title, "event_date": date, "place": place,
                  "people": people, "memory": memory,
                  "observation": "Illustrative demo artwork (not AI analysis)."})
    project["chapters"] = generate_local_story(project)
    save_project(root, project)
    return project
