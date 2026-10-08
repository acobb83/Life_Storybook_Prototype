"""Print-friendly A4 PDF book with embedded, correctly oriented photographs."""
from __future__ import annotations

import io
import os
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, PageBreak,
                                Image as RLImage, KeepTogether, HRFlowable)

from .core import chronological_photos, jpeg_preview_bytes, photo_path

INK = colors.HexColor("#173140")
MUTED = colors.HexColor("#5A7180")
TEAL = colors.HexColor("#2C7774")
CREAM = colors.HexColor("#F5F0E7")
W, H = A4


def _font_family() -> tuple[str, str]:
    regular_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial Unicode.ttf", "C:/Windows/Fonts/arial.ttf",
    ]
    bold_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
    ]
    if "LifeRegular" not in pdfmetrics.getRegisteredFontNames():
        regular = next((p for p in regular_paths if os.path.exists(p)), None)
        bold = next((p for p in bold_paths if os.path.exists(p)), None)
        if regular and bold:
            pdfmetrics.registerFont(TTFont("LifeRegular", regular))
            pdfmetrics.registerFont(TTFont("LifeBold", bold))
    if "LifeRegular" in pdfmetrics.getRegisteredFontNames():
        return ("LifeRegular", "LifeBold")
    return ("Helvetica", "Helvetica-Bold")


def _markup(text: str) -> str:
    return escape(str(text or "")).replace("\n", "<br/>")


def _image(path: Path, max_width: float = 495, max_height: float = 295) -> RLImage:
    preview = jpeg_preview_bytes(path, max_edge=1600, quality=86)
    bio = io.BytesIO(preview)
    width, height = ImageReader(io.BytesIO(preview)).getSize()
    scale = min(max_width / width, max_height / height)
    # The in-memory stream must stay alive until doc.build has finished.
    img = RLImage(bio, width=width * scale, height=height * scale)
    img.hAlign = "CENTER"
    return img


def generate_pdf(project: dict, root: Path, mark_draft: bool = True) -> bytes:
    if not project.get("photos"):
        raise ValueError("Please upload at least one photo before exporting.")
    if not project.get("chapters"):
        raise ValueError("Please create or add a story chapter before exporting.")
    reg, bold = _font_family()
    styles = {
        "cover_kicker": ParagraphStyle("cover_kicker", fontName=bold, fontSize=11,
            leading=19, textColor=TEAL, spaceAfter=24),
        "cover_title": ParagraphStyle("cover_title", fontName=bold, fontSize=29,
            leading=39, textColor=INK, spaceAfter=18),
        "cover_subtitle": ParagraphStyle("cover_subtitle", fontName=reg, fontSize=13,
            leading=21, textColor=MUTED, spaceAfter=20),
        "dedication": ParagraphStyle("dedication", fontName=reg, fontSize=11,
            leading=19, textColor=INK, alignment=TA_CENTER),
        "chapter_num": ParagraphStyle("chapter_num", fontName=bold, fontSize=9,
            leading=15, textColor=TEAL, spaceAfter=10),
        "chapter_title": ParagraphStyle("chapter_title", fontName=bold, fontSize=22,
            leading=30, textColor=INK, spaceAfter=18),
        "body": ParagraphStyle("body", fontName=reg, fontSize=10.4,
            leading=18, textColor=INK, spaceAfter=12, alignment=TA_LEFT),
        "caption": ParagraphStyle("caption", fontName=reg, fontSize=9,
            leading=15, textColor=MUTED, spaceBefore=8, spaceAfter=17, alignment=TA_CENTER),
        "small": ParagraphStyle("small", fontName=reg, fontSize=8.5,
            leading=14, textColor=MUTED, spaceAfter=10),
    }
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=59, bottomMargin=58,
                            leftMargin=55, rightMargin=55,
                            title=project.get("title", "Life Story"), author="Life Storybook Prototype")

    def paint_cover(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(CREAM)
        canvas.rect(0, 0, W, H, fill=1, stroke=0)
        canvas.setFillColor(TEAL)
        canvas.rect(0, H - 16, W, 16, fill=1, stroke=0)
        canvas.setStrokeColor(colors.HexColor("#D2D7CE"))
        canvas.line(56, 65, W-56, 65)
        canvas.setFont(reg, 8)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(W / 2, 48, "A PERSONAL COLLECTION OF MEMORIES")
        canvas.restoreState()

    def paint_page(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(CREAM)
        canvas.rect(0, H - 24, W, 24, fill=1, stroke=0)
        canvas.setFillColor(TEAL)
        canvas.rect(0, H - 24, 8, 24, fill=1, stroke=0)
        canvas.setFont(reg, 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(55, H - 38, (project.get("title") or "Life Story")[:62])
        canvas.line(55, 42, W-55, 42)
        canvas.drawRightString(W-55, 29, str(_doc.page))
        if mark_draft:
            canvas.drawString(55, 29, "PERSONAL DRAFT - PLEASE REVIEW")
        canvas.restoreState()

    flow = [Spacer(1, 50), Paragraph("LIFE STORYBOOK", styles["cover_kicker"]),
            Paragraph(_markup(project.get("title") or "Our Life in Pictures"), styles["cover_title"]),
            Paragraph(_markup(project.get("subtitle") or "A collection of moments worth remembering"),
                      styles["cover_subtitle"]), Spacer(1, 8)]
    ordered = chronological_photos(project)
    if ordered:
        flow.extend([_image(photo_path(root, project["id"], ordered[0]), 450, 320), Spacer(1, 23)])
    if project.get("dedication", "").strip():
        flow.append(Paragraph(_markup(project["dedication"]), styles["dedication"]))
    flow.append(PageBreak())
    if project.get("intro", "").strip():
        flow.extend([Paragraph("Before we begin", styles["chapter_title"]),
                     Paragraph(_markup(project["intro"]), styles["body"]), PageBreak()])
    photos = {p["id"]: p for p in project["photos"]}
    for chapter_number, chapter in enumerate(project["chapters"], 1):
        flow.append(Paragraph(f"CHAPTER {chapter_number:02d}", styles["chapter_num"]))
        flow.append(Paragraph(_markup(chapter.get("title", "A chapter of our story")), styles["chapter_title"]))
        body = (chapter.get("text") or "").strip()
        if body:
            for paragraph in body.split("\n\n"):
                if paragraph.strip():
                    flow.append(Paragraph(_markup(paragraph), styles["body"]))
        flow.append(Spacer(1, 10))
        flow.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#C8D9D4")))
        flow.append(Spacer(1, 20))
        for photo_id in chapter.get("photo_ids", []):
            photo = photos.get(photo_id)
            if not photo:
                continue
            cap = photo.get("caption", "").strip() or photo.get("filename", "Photograph")
            date = photo.get("event_date", "").strip()
            place = photo.get("place", "").strip()
            label = "  |  ".join([x for x in (cap, date, place) if x])
            # Photos are kept with their captions, and long chapters can flow over pages.
            flow.append(KeepTogether([
                _image(photo_path(root, project["id"], photo), 460, 265),
                Paragraph(_markup(label), styles["caption"]),
            ]))
        if chapter_number < len(project["chapters"]):
            flow.append(PageBreak())
    doc.build(flow, onFirstPage=paint_cover, onLaterPages=paint_page)
    return buf.getvalue()
