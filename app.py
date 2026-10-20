"""Life Story prototype. Run with: streamlit run app.py"""
from __future__ import annotations

import html
import os
from pathlib import Path

import streamlit as st

from storybook.ai import DEFAULT_MODEL, analyse_photo, generate_ai_story, suggest_place
from storybook.book_pdf import generate_pdf
from storybook.book_types import (BOOK_TYPES, GROUPING_TEXT, TYPE_ORDER, apply_type, get_type,
                                  local_chapters)
from storybook.core import (InvalidPhoto, add_photo, chronological_photos, delete_project,
                            list_projects, load_project, new_project, photo_path, photo_year,
                            register_heif, save_project, select_photos)
from storybook.demo import make_demo_project, make_travel_demo_project
from storybook.travel import build_trips, chapters_from_trips, lookup_place

st.set_page_config(page_title="Life Story", page_icon="📖", layout="wide")
ROOT = Path(os.environ.get("LIFESTORY_DATA_DIR", Path(__file__).parent / "data")).expanduser().resolve()
ROOT.mkdir(parents=True, exist_ok=True)
HEIC_ENABLED = register_heif()

# Look and feel follows the Life Story deck: warm cream, navy ink, lavender/violet accents.
st.markdown("""<style>
.block-container {max-width: 1200px; padding-top: 1.6rem}
h1, h2, h3, h4 {color: #1F2D4A}
.ls-title {font-family: Georgia, 'Times New Roman', serif; font-style: italic; font-weight: 700;
           font-size: 3rem; line-height: 1.05; color: #1F2D4A; margin: 0}
.ls-book-title {font-family: Georgia, 'Times New Roman', serif; font-style: italic; font-weight: 700;
                font-size: 2.3rem; line-height: 1.1; color: #1F2D4A; margin: 0}
.ls-tagline {font-family: Georgia, serif; font-style: italic; color: #53617B; font-size: 1.1rem;
             margin: .35rem 0 1.1rem 0}
.ls-kicker {letter-spacing: .18em; font-size: .72rem; color: #5B47C7; font-weight: 700;
            text-transform: uppercase; margin-bottom: .35rem}
.ls-card {background: #FFFFFF; border: 1px solid #E6DFEF; border-radius: 14px; padding: 14px 16px;
          height: 100%}
.ls-card b {color: #1F2D4A}
.ls-card .ls-sub {color: #53617B; font-size: .86rem}
.ls-icon {display: inline-flex; width: 34px; height: 34px; border-radius: 50%; align-items: center;
          justify-content: center; margin-right: 8px; font-size: 1rem}
.ls-step1 {background: #F8DCCB} .ls-step2 {background: #D3E8DC} .ls-step3 {background: #E2DBEF}
.ls-type-icon {font-size: 2rem; line-height: 1}
.ls-source {background: #FFFFFF; border: 1px solid #E6DFEF; border-radius: 12px; padding: 12px;
            text-align: center; min-height: 112px}
.ls-source .ls-name {font-weight: 700; color: #1F2D4A; margin-top: 4px}
.ls-source .ls-via {color: #53617B; font-size: .78rem}
.ls-badge {display: inline-block; border-radius: 999px; padding: 1px 10px; font-size: .72rem;
           font-weight: 700; margin-top: 6px}
.ls-live {background: #D3E8DC; color: #22543D} .ls-planned {background: #EEE9F4; color: #6B6385}
[data-testid="stMetric"] {background: #FFFFFF; border: 1px solid #E6DFEF; padding: 12px 15px;
                          border-radius: 12px}
[data-testid="stSidebar"] .ls-title {font-size: 1.8rem}
</style>""", unsafe_allow_html=True)


def save(p):
    save_project(ROOT, p)
    st.session_state.pop("rendered_pdf", None)


def rerun_notice(note: str):
    st.session_state["flash_notice"] = note
    st.rerun()


def get_client(key: str):
    if not key:
        raise ValueError("Add an OpenAI API key in the sidebar to use AI features.")
    from openai import OpenAI
    return OpenAI(api_key=key, timeout=70.0, max_retries=1)


@st.dialog("Connect AI")
def ai_key_dialog(action: str):
    st.write(f"**{action}** uses AI. Paste an OpenAI API key to continue.")
    st.caption("The key is kept only for this browser session and never saved to your photobook. "
               "Each AI request may incur API charges. Only resized photos (location data removed) "
               "or the notes you choose are sent.")
    key = st.text_input("OpenAI API key", type="password", placeholder="sk-...")
    c1, c2 = st.columns(2)
    if c1.button("Connect", type="primary", use_container_width=True, disabled=not key.strip()):
        st.session_state["api_key"] = key.strip()
        rerun_notice(f"AI connected. Click “{action}” again to continue.")
    if c2.button("Not now", use_container_width=True):
        st.rerun()


def require_ai(action: str) -> bool:
    """True when a key is available; otherwise asks for one and returns False."""
    if api_key:
        return True
    ai_key_dialog(action)
    return False


def story_photo_ids(project: dict) -> list[str]:
    """Photos in story order: by chapter if a story exists, otherwise by date."""
    ids = [pid for ch in project.get("chapters", []) for pid in ch.get("photo_ids", [])]
    return ids or [p["id"] for p in chronological_photos(project)]


def needs_location(p: dict) -> bool:
    return not p.get("metadata", {}).get("gps") and not lookup_place(p.get("place", ""))


# -------------------- Sidebar / photobook selection --------------------
with st.sidebar:
    st.markdown('<p class="ls-title">Life Story</p>', unsafe_allow_html=True)
    st.caption("Human memories. Thoughtfully preserved.")
    projects = list_projects(ROOT)
    if not projects:
        p = new_project()
        save_project(ROOT, p)
        projects = list_projects(ROOT)
    project_ids = [p["id"] for p in projects]
    if st.session_state.get("active_project") not in project_ids:
        st.session_state["active_project"] = project_ids[0]
    label_by_id = {p["id"]: f"{BOOK_TYPES[p['book_type']]['icon'] if p.get('book_type') in BOOK_TYPES else '✳️'} "
                            f"{p['title']}" for p in projects}
    pick = st.selectbox("Your photobooks", project_ids,
                        index=project_ids.index(st.session_state["active_project"]),
                        format_func=lambda key: label_by_id.get(key, "Untitled"))
    if pick != st.session_state["active_project"]:
        st.session_state["active_project"] = pick
        st.session_state.pop("rendered_pdf", None)
        st.session_state.pop("choosing_type", None)
        st.rerun()
    if st.button("＋ New photobook", use_container_width=True, type="primary"):
        st.session_state["choosing_type"] = True
        st.rerun()
    st.caption("Or try a fictional demo:")
    d1, d2 = st.columns(2)
    if d1.button("📖 Life", use_container_width=True,
                 help="A fictional family life story with four synthetic illustrations."):
        sample = make_demo_project(ROOT)
        st.session_state["active_project"] = sample["id"]
        st.session_state.pop("choosing_type", None)
        rerun_notice("Loaded a fictional life story. All artwork and memories are synthetic.")
    if d2.button("🌏 Travel", use_container_width=True,
                 help="Fictional trips through Tokyo, Kyoto, Singapore, Sydney and Paris."):
        sample = make_travel_demo_project(ROOT)
        st.session_state["active_project"] = sample["id"]
        st.session_state["travel_stop"] = 1
        st.session_state.pop("choosing_type", None)
        rerun_notice("Loaded a fictional travel story. The map is in step 4 · Story views.")
    st.divider()
    with st.expander("AI settings (optional)", expanded=False):
        typed_key = st.text_input("OpenAI API key", type="password", value=st.session_state.get("api_key", ""),
                                  placeholder="sk-... (or set OPENAI_API_KEY)",
                                  help="Held in this session only; never written to project files.")
        if typed_key != st.session_state.get("api_key", ""):
            st.session_state["api_key"] = typed_key
        api_key = typed_key or os.getenv("OPENAI_API_KEY", "")
        model = st.text_input("Model", value=DEFAULT_MODEL, help="An image-capable OpenAI Responses API model.")
        st.caption("AI runs only when you click an AI button. API usage may incur charges.")
    st.caption("🟢 AI connected" if api_key else "⚪ AI not connected: you'll be asked for a key when an AI step needs one")

project = load_project(ROOT, st.session_state["active_project"])

with st.sidebar:
    if project.get("book_type"):
        with st.expander("Change photobook type", expanded=False):
            current = project["book_type"] if project["book_type"] in BOOK_TYPES else "life"
            new_type = st.selectbox("Type", TYPE_ORDER, index=TYPE_ORDER.index(current),
                                    format_func=lambda k: f"{BOOK_TYPES[k]['icon']} {BOOK_TYPES[k]['label']}")
            st.caption("Changes the prompts, chapter grouping and main view. Existing chapters are kept.")
            if st.button("Apply type", use_container_width=True, disabled=new_type == current):
                apply_type(project, new_type)
                save(project)
                rerun_notice(f"Changed to a {BOOK_TYPES[new_type]['label'].lower()} photobook.")
    with st.expander("Delete this photobook", expanded=False):
        confirm = st.checkbox("Permanently delete its saved photos and story text", key="delete_confirm")
        if st.button("Delete photobook", disabled=not confirm, type="secondary", use_container_width=True):
            delete_project(ROOT, st.session_state["active_project"])
            st.session_state.pop("active_project", None)
            rerun_notice("Photobook deleted from local storage.")
    st.divider()
    st.caption("2026 AI Hackathon · Team 2 · Prototype\n\nSingle-user local demo: no login or encryption at rest.")

if notice := st.session_state.pop("flash_notice", ""):
    st.success(notice)

# ------------------------- Choose a photobook type -------------------------
choosing = st.session_state.get("choosing_type") or (not project.get("book_type") and not project["photos"])
if choosing:
    st.markdown('<p class="ls-title">Life Story</p>'
                '<p class="ls-tagline">Your memories, gathered from everywhere and told as the journey they are.</p>',
                unsafe_allow_html=True)
    h1, h2, h3 = st.columns(3)
    for col, cls, icon, head, sub in (
            (h1, "ls-step1", "🔗", "Link your accounts", "OneDrive, Google Photos and uploads"),
            (h2, "ls-step2", "👁", "Each memory is understood", "When, where and what happened"),
            (h3, "ls-step3", "✨", "Ask for a story", "Relive a trip, a year or a milestone")):
        col.markdown(f'<div class="ls-card"><span class="ls-icon {cls}">{icon}</span><b>{head}</b>'
                     f'<div class="ls-sub" style="margin-left:42px">{sub}</div></div>', unsafe_allow_html=True)
    st.write("")
    st.subheader("What would you like to make?")
    st.caption("Your choice shapes the questions, how chapters are grouped and how the story is shown. "
               "You can change it later.")
    for row in range(0, len(TYPE_ORDER), 4):
        for col, key in zip(st.columns(4), TYPE_ORDER[row:row + 4]):
            t = BOOK_TYPES[key]
            with col.container(border=True):
                st.markdown(f'<div class="ls-type-icon">{t["icon"]}</div>', unsafe_allow_html=True)
                st.markdown(f"**{t['label']}**")
                st.write(t["blurb"])
                st.caption(f"Good for: {t['good_for']}")
                if st.button("Start this book", key=f"start_{key}", use_container_width=True,
                             type="primary"):
                    target = project if (not project.get("book_type") and not project["photos"]) else new_project()
                    target["title"], target["subtitle"] = "", ""
                    apply_type(target, key)
                    save_project(ROOT, target)
                    st.session_state["active_project"] = target["id"]
                    st.session_state.pop("choosing_type", None)
                    rerun_notice(f"Started a new {t['label'].lower()} photobook. Bring in your photos to begin.")
    if st.session_state.get("choosing_type") and project.get("book_type"):
        if st.button("Cancel"):
            st.session_state.pop("choosing_type", None)
            st.rerun()
    st.stop()

# A photobook from before types existed: treat it as a life story.
if not project.get("book_type"):
    apply_type(project, "life", set_defaults=False)
    save(project)
btype = get_type(project)

# ------------------------------- Header -------------------------------
st.markdown(f'<div class="ls-kicker">{btype["icon"]} {btype["label"]}</div>'
            f'<p class="ls-book-title">{html.escape(project.get("title") or btype["title"])}</p>'
            f'<p class="ls-tagline">{html.escape(project.get("subtitle") or btype["blurb"])}</p>',
            unsafe_allow_html=True)
photos_all = project["photos"]
m1, m2, m3, m4 = st.columns(4)
m1.metric("Memories", len(photos_all))
m2.metric("In your own words", sum(bool(p.get("memory", "").strip()) for p in photos_all))
m3.metric("Places", len({p["place"].strip() for p in photos_all if p.get("place", "").strip()}))
m4.metric("Story chapters", len(project.get("chapters", [])))

# ------------------------------ Step-by-step ------------------------------
STEPS = ["Link & bring in", "Understand memories", "Ask for a story", "Story views", "Book"]
with_notes = sum(bool(p.get("memory", "").strip() or p.get("caption", "").strip()) for p in photos_all)
has_story = bool(project.get("chapters"))
STEP_DONE = [bool(photos_all), bool(photos_all) and with_notes == len(photos_all), has_story, has_story,
             bool(st.session_state.get("rendered_pdf"))]
STEP_HELP = [
    "Add the photos for this photobook. When they're in, go to the next step.",
    "Check when and where each photo was taken and add what you remember. Notes are optional, but "
    "they're what the story is built from.",
    f"Say what story you'd like, then write a draft (no AI) or write it with AI. Chapters for a "
    f"{btype['label'].lower()} are grouped by {GROUPING_TEXT[btype['grouping']]}.",
    "See your story as a timeline, map, photo strip or chapters to read. Go back to step 3 to edit it.",
    "Make the printable PDF photobook and download it.",
]
if st.session_state.get("step_for") != project["id"]:
    # Opening a photobook: start where there is something to do.
    st.session_state["step_for"] = project["id"]
    st.session_state["step"] = 4 if has_story else 2 if photos_all else 1
step = st.session_state.get("step", 1)


def go(n: int):
    st.session_state["step"] = n
    st.rerun()


st.progress(sum(STEP_DONE) / len(STEPS))
for i, (col, name) in enumerate(zip(st.columns(len(STEPS)), STEPS), 1):
    mark = "✓ " if STEP_DONE[i - 1] and i != step else ""
    if col.button(f"{mark}{i} · {name}", key=f"stepnav_{i}", use_container_width=True,
                  type="primary" if i == step else "secondary"):
        go(i)
st.info(f"**Step {step} of {len(STEPS)} · {STEPS[step - 1]}**: {STEP_HELP[step - 1]}")

# -------------------------- Link & bring in --------------------------
if step == 1:
    st.markdown('<div class="ls-kicker">Sources</div>', unsafe_allow_html=True)
    st.subheader("Bring your memories in")
    sources = [("⬆️", "Uploads", "Photos from this computer", True),
               ("☁️", "OneDrive", "Microsoft Graph", False),
               ("🖼️", "Google Photos", "Google Photos Picker", False),
               ("📷", "Instagram", "Instagram data download", False),
               ("📅", "Mail & calendar", "Microsoft Graph", False)]
    for col, (icon, name, via, live) in zip(st.columns(len(sources)), sources):
        badge = '<span class="ls-badge ls-live">Available</span>' if live else \
                '<span class="ls-badge ls-planned">Planned</span>'
        col.markdown(f'<div class="ls-source"><div style="font-size:1.4rem">{icon}</div>'
                     f'<div class="ls-name">{name}</div><div class="ls-via">{via}</div>{badge}</div>',
                     unsafe_allow_html=True)
    st.caption("This prototype supports uploads. Account connectors are part of the full Life Story design.")
    if project["book_type"] == "travel":
        st.caption("📍 Tip: phone photos usually carry their location, which puts them straight on the map.")
    elif project["book_type"] == "business":
        st.caption("🏢 Tip: check you have permission to use client, site and staff photos before adding them.")
    elif project["book_type"] == "family":
        st.caption("🖨️ Tip: scanned prints work well. Add an approximate date such as 'circa 1965' in the next step.")
    st.write("")
    uploaded = st.file_uploader("Upload photographs", type=["jpg", "jpeg", "png", "webp", "heic"],
                                accept_multiple_files=True,
                                help="Up to 30 images, maximum 20 MB and 45 megapixels each.")
    if not HEIC_ENABLED:
        st.caption("HEIC/HEIF needs the optional `pillow-heif` package. JPEG, PNG and WebP work without it.")
    if st.button("Bring in selected photos", type="primary", disabled=not bool(uploaded)):
        added, skipped, errors = 0, 0, []
        for file in uploaded or []:
            try:
                if add_photo(ROOT, project, file.name, file.getvalue()):
                    added += 1
                else:
                    skipped += 1
            except (InvalidPhoto, OSError, ValueError) as exc:
                errors.append(f"{file.name}: {exc}")
        if added:
            st.session_state.pop("rendered_pdf", None)
        st.success(f"Brought in {added} photos; skipped {skipped} duplicates. "
                   "Bring in more, or click **Next** below when you're ready.")
        for error in errors:
            st.error(error)
    if photos_all:
        st.markdown("#### Your memories")
        previews = st.columns(4)
        for idx, photo in enumerate(chronological_photos(project)):
            with previews[idx % 4]:
                st.image(str(photo_path(ROOT, project["id"], photo)), use_container_width=True)
                st.caption(photo.get("caption") or photo["filename"])

# ------------------------ Understand memories ------------------------
if step == 2:
    st.markdown('<div class="ls-kicker">Enrich</div>', unsafe_allow_html=True)
    st.subheader("Each memory is understood")
    e1, e2, e3 = st.columns(3)
    e1.markdown('<div class="ls-card"><b>📍 When & where</b><div class="ls-sub">From the photo\'s camera data, '
                'or a place AI suggests from clear clues. You confirm it.</div></div>', unsafe_allow_html=True)
    e2.markdown('<div class="ls-card"><b>👁 Photo insights</b><div class="ls-sub">AI describes only what is visible. '
                'It never identifies people.</div></div>', unsafe_allow_html=True)
    e3.markdown('<div class="ls-card"><b>💬 Your words</b><div class="ls-sub">Names, places and what it meant. '
                'These are what the story is built from.</div></div>', unsafe_allow_html=True)
    st.write("")
    if not photos_all:
        st.info("No photos yet. Go back to step **1 · Link & bring in**, or load a demo from the sidebar.")
    else:
        unlocated = [p for p in photos_all if needs_location(p)]
        a1, a2 = st.columns(2)
        if a1.button("✨ Describe all photos with AI", use_container_width=True,
                     help="Sends one reduced-size, EXIF-stripped photo at a time; GPS is never sent.") \
                and require_ai("Describe all photos with AI"):
            progress = st.progress(0)
            errors = []
            client = get_client(api_key)
            for idx, p in enumerate(photos_all):
                try:
                    result = analyse_photo(client, model, photo_path(ROOT, project["id"], p))
                    p["observation"] = result.get("observation", "")
                    p["question"] = result.get("question", "")
                    p["analyzed"] = True
                    save(project)
                except Exception as exc:
                    errors.append(f"{p['filename']}: {exc}")
                progress.progress((idx + 1) / len(photos_all))
            if errors:
                st.warning("Some descriptions did not complete: " + " | ".join(errors[:4]))
            else:
                rerun_notice("AI descriptions are ready. Please check each one.")
        if a2.button(f"📍 Suggest places with AI ({len(unlocated)} without a location)",
                     disabled=not unlocated, use_container_width=True,
                     help="For photos with no camera location and no recognised place. "
                          "Suggestions are only saved when you accept them.") \
                and require_ai("Suggest places with AI"):
            progress = st.progress(0)
            errors, found = [], 0
            client = get_client(api_key)
            for idx, p in enumerate(unlocated):
                try:
                    p["place_suggestion"] = suggest_place(client, model, photo_path(ROOT, project["id"], p))
                    found += bool(p["place_suggestion"]["place"])
                    save(project)
                except Exception as exc:
                    errors.append(f"{p['filename']}: {exc}")
                progress.progress((idx + 1) / len(unlocated))
            if errors:
                st.warning("Some suggestions did not complete: " + " | ".join(errors[:4]))
            else:
                rerun_notice(f"AI suggested a place for {found} of {len(unlocated)} photos. "
                             "Open each photo below to accept or dismiss.")
        st.caption("AI steps are optional: you can type everything yourself."
                   + ("" if api_key else " You'll be asked for an API key the first time you use one."))
        for p in chronological_photos(project):
            friendly = p.get("caption", "").strip() or p["filename"]
            done = "✅" if p.get("memory", "").strip() else "📷"
            flag = " · 📍 place suggested" if p.get("place_suggestion", {}).get("place") else ""
            with st.expander(f"{done} {friendly}{flag}", expanded=False):
                left, right = st.columns([1, 1.25], gap="large")
                with left:
                    st.image(str(photo_path(ROOT, project["id"], p)), use_container_width=True)
                    m = p["metadata"]
                    gps = m.get("gps")
                    known = lookup_place(p.get("place", ""))
                    if gps:
                        on_map = f"Camera location {gps['latitude']}, {gps['longitude']} (stays on this computer)"
                    elif known:
                        on_map = f"{known['name']}" + (f", {known['country']}" if known["country"] != known["name"] else "") + \
                                 " (from the place entered)"
                    else:
                        on_map = "Not on the map yet"
                    st.markdown("**When & where**")
                    st.caption(f"Camera date: {m.get('capture_date') or 'Not available'} (unverified)  \n"
                               f"Map: {on_map}  \n"
                               f"Camera: {m.get('camera') or 'Not available'}")
                    if p.get("question"):
                        st.info("💬 " + p["question"])
                    b_desc, b_place = st.columns(2)
                    if b_desc.button("✨ Describe", key="analyse_" + p["id"], use_container_width=True) \
                            and require_ai("Describe"):
                        described = False
                        try:
                            with st.spinner("Looking at visible details..."):
                                result = analyse_photo(get_client(api_key), model,
                                                       photo_path(ROOT, project["id"], p))
                            p["observation"] = result.get("observation", "")
                            p["question"] = result.get("question", "")
                            p["analyzed"] = True
                            save(project)
                            described = True
                        except Exception as exc:
                            st.error(f"Image description failed: {exc}")
                        if described:
                            rerun_notice("Description ready. Please check it and add your memory.")
                    if not gps and b_place.button("📍 Suggest place", key="place_" + p["id"],
                                                  use_container_width=True) and require_ai("Suggest place"):
                        suggested = False
                        try:
                            with st.spinner("Looking for landmarks, signs and other clues..."):
                                p["place_suggestion"] = suggest_place(get_client(api_key), model,
                                                                      photo_path(ROOT, project["id"], p))
                            save(project)
                            suggested = True
                        except Exception as exc:
                            st.error(f"Place suggestion failed: {exc}")
                        if suggested:
                            st.rerun()
                    sug = p.get("place_suggestion")
                    if sug:
                        if sug.get("place"):
                            st.info(f"📍 Possibly **{sug['place']}** ({sug.get('confidence', 'low')} confidence)  \n"
                                    f"{sug.get('evidence', '')}")
                        else:
                            st.info("📍 AI found no clear clues to where this was taken. "
                                    + (sug.get("evidence") or "") + " Add the place yourself if you know it.")
                        ok_col, no_col = st.columns(2)
                        if sug.get("place") and ok_col.button("Use this place", key="accept_" + p["id"],
                                                              type="primary", use_container_width=True):
                            p["place"] = sug["place"]
                            p["place_source"] = "AI suggestion, confirmed by you"
                            p.pop("place_suggestion", None)
                            save(project)
                            rerun_notice(f"Place set to {sug['place']}.")
                        if no_col.button("Dismiss", key="dismiss_" + p["id"], use_container_width=True):
                            p.pop("place_suggestion", None)
                            save(project)
                            st.rerun()
                    with st.popover("🗑️ Remove photo"):
                        st.write("Remove this photo from the photobook? Its memory notes go too, and it is "
                                 "taken out of any chapters. This can't be undone.")
                        if st.button("Yes, remove it", key="remove_" + p["id"], type="primary"):
                            location = photo_path(ROOT, project["id"], p)
                            project["photos"] = [item for item in project["photos"] if item["id"] != p["id"]]
                            for chapter in project["chapters"]:
                                chapter["photo_ids"] = [pid for pid in chapter["photo_ids"] if pid != p["id"]]
                            save(project)
                            location.unlink(missing_ok=True)
                            rerun_notice("Photo removed from this photobook.")
                with right:
                    with st.form("edit_photo_" + p["id"]):
                        caption = st.text_input("What happened", value=p.get("caption", ""))
                        date = st.text_input("When (YYYY-MM-DD, a year, or 'circa 1990')",
                                             value=p.get("event_date", ""))
                        place = st.text_input("Where (a city or country puts it on the map)", value=p.get("place", ""))
                        people = st.text_input(btype.get("people_label", "Who was there"), value=p.get("people", ""))
                        memory = st.text_area(btype["memory_label"], value=p.get("memory", ""), height=115)
                        observation = st.text_area("Photo insights (AI draft, editable)",
                                                   value=p.get("observation", ""), height=90)
                        if st.form_submit_button("Save memory", type="primary"):
                            if place.strip() != p.get("place", "").strip():
                                p.pop("place_suggestion", None)
                                p.pop("place_source", None)
                            p.update({"caption": caption, "event_date": date, "place": place,
                                      "people": people, "memory": memory,
                                      "observation": observation})
                            save(project)
                            rerun_notice("Memory saved. Ask for a new story to include the changes.")

# -------------------------- Ask for a story --------------------------
if step == 3:
    st.markdown('<div class="ls-kicker">Reason</div>', unsafe_allow_html=True)
    st.subheader(f"Ask for your {btype['label'].lower()}")
    st.caption(f"Chapters for a {btype['label'].lower()} are grouped by **{GROUPING_TEXT[btype['grouping']]}**.")
    if not photos_all:
        st.info("Bring in some photos first.")
    saved_filter = project.get("story_filter", {})
    with st.form("story_request_form"):
        request = st.text_input("What story would you like?", value=project.get("story_request", ""),
                                placeholder=btype["request_hint"])
        st.caption("Ideas: " + " · ".join(f"*{x}*" for x in btype["examples"]))
        years = sorted({y for p in photos_all if (y := photo_year(p))})
        year_range = None
        if len(years) >= 2:
            default = tuple(saved_filter.get("years") or (years[0], years[-1]))
            default = (max(years[0], default[0]), min(years[-1], default[1]))
            year_range = st.slider("Which years?", years[0], years[-1], default)
        places_known = sorted({p["place"].strip() for p in photos_all if p.get("place", "").strip()})
        places = st.multiselect("Which places? (leave empty for all)", places_known,
                                default=[x for x in saved_filter.get("places", []) if x in places_known])
        include_undated = st.checkbox("Include photos without a date",
                                      value=saved_filter.get("include_undated", True))
        voice_options = ["Warm and reflective", "Joyful and celebratory", "Simple and factual", "Gentle and poetic",
                         "Clear and professional"]
        current_voice = project.get("voice", btype["voice"])
        voice = st.selectbox("Writing style", voice_options,
                             index=voice_options.index(current_voice) if current_voice in voice_options else 0)
        with st.expander("Book details", expanded=False):
            title = st.text_input("Title", value=project.get("title", ""))
            subtitle = st.text_input("Subtitle", value=project.get("subtitle", ""))
            dedication = st.text_input("Dedication (optional)", value=project.get("dedication", ""))
            intro = st.text_area("Opening note (optional)", value=project.get("intro", ""), height=86)
            instructions = st.text_area("Extra directions for the writer", value=project.get("instructions", ""),
                                        placeholder="e.g. Write in first person. Keep the language simple for grandchildren.")
        if st.form_submit_button("Save request"):
            project.update({"story_request": request, "voice": voice, "title": title, "subtitle": subtitle,
                            "dedication": dedication, "intro": intro, "instructions": instructions,
                            "story_filter": {"years": list(year_range) if year_range else None,
                                             "places": places, "include_undated": include_undated}})
            save(project)
            rerun_notice("Story request saved.")

    flt = project.get("story_filter", {})
    matching = select_photos(project, tuple(flt["years"]) if flt.get("years") else None,
                             flt.get("places") or None, flt.get("include_undated", True))
    st.markdown(f"**{len(matching)} of {len(photos_all)} memories** match this request.")
    if matching:
        st.image([str(photo_path(ROOT, project["id"], p)) for p in matching[:8]], width=110,
                 caption=[(p.get("caption") or p["filename"])[:22] for p in matching[:8]])
    story_project = dict(project, photos=matching)
    b1, b2 = st.columns(2)
    with b1:
        st.markdown("**Quick draft** (no AI)")
        st.caption(f"Arranges your own notes into chapters by {GROUPING_TEXT[btype['grouping']]}. Nothing is invented.")
        if st.button("Write a draft", use_container_width=True, type="primary", disabled=not matching):
            project["chapters"] = local_chapters(project, matching)
            save(project)
            st.session_state["step"] = 4
            rerun_notice("Draft ready. Here it is. Go back to step 3 to refine it.")
    with b2:
        st.markdown("**Story writer** (AI)")
        consent = st.checkbox("Send the notes for these memories to OpenAI to write the story.",
                              key="story_consent")
        share_exif = st.checkbox("Include camera dates (never GPS)", value=False)
        if st.button("✨ Write with AI", use_container_width=True,
                     disabled=not (matching and consent),
                     help="Tick the box above first. Replaces the current chapters.") \
                and require_ai("Write with AI"):
            try:
                with st.spinner("Writing your story from your memories..."):
                    project["chapters"] = generate_ai_story(get_client(api_key), model, story_project,
                                                            share_metadata=share_exif,
                                                            book_label=btype["label"],
                                                            guidance=btype["guidance"])
                save(project)
                st.session_state["step"] = 4
                rerun_notice("Your story is ready. Check the details before sharing.")
            except Exception as exc:
                st.error(f"Story writing failed: {exc}")
    st.caption("A new story replaces the current chapters. Your saved memories are not changed.")

    st.divider()
    st.markdown("#### Refine the story")
    chapters = project.get("chapters", [])
    if not chapters:
        st.caption("No chapters yet.")
    photo_options = [p["id"] for p in chronological_photos(project)]
    filename_map = {p["id"]: p.get("caption") or p["filename"] for p in photos_all}
    for idx, chapter in enumerate(chapters):
        with st.expander(f"Chapter {idx + 1}: {chapter.get('title', 'Untitled')}", expanded=False):
            with st.form(f"edit_chapter_{idx}"):
                new_title = st.text_input("Chapter heading", value=chapter.get("title", ""))
                new_text = st.text_area("Story text (fully editable)", value=chapter.get("text", ""), height=220)
                new_photos = st.multiselect("Photos in this chapter", photo_options,
                                            default=[x for x in chapter.get("photo_ids", []) if x in filename_map],
                                            format_func=lambda x: filename_map.get(x, x[:8]))
                if st.form_submit_button("Save chapter", type="primary"):
                    chapter.update({"title": new_title, "text": new_text, "photo_ids": new_photos})
                    save(project)
                    rerun_notice("Chapter saved.")
            first, second, third = st.columns(3)
            if first.button("↑ Move up", key=f"up_{idx}", disabled=idx == 0):
                chapters[idx-1], chapters[idx] = chapters[idx], chapters[idx-1]
                save(project); st.rerun()
            if second.button("↓ Move down", key=f"down_{idx}", disabled=idx == len(chapters)-1):
                chapters[idx+1], chapters[idx] = chapters[idx], chapters[idx+1]
                save(project); st.rerun()
            if third.button("Remove chapter", key=f"drop_{idx}"):
                chapters.pop(idx); save(project); st.rerun()
    if st.button("＋ Add a blank chapter"):
        project["chapters"].append({"title": "New chapter", "text": "", "photo_ids": []})
        save(project)
        st.rerun()

# ---------------------------- Story views ----------------------------
by_id = {p["id"]: p for p in photos_all}


def view_timeline(ordered: list[dict]):
    groups = project.get("chapters") or [{"title": "All memories", "photo_ids": [p["id"] for p in ordered]}]
    for ch in groups:
        items = [by_id[i] for i in ch.get("photo_ids", []) if i in by_id]
        if not items:
            continue
        st.markdown(f"##### {ch.get('title', 'Untitled')}")
        for p in items:
            c1, c2 = st.columns([1, 3], gap="medium")
            c1.image(str(photo_path(ROOT, project["id"], p)), use_container_width=True)
            when = p.get("event_date") or p["metadata"].get("capture_date") or "Date unknown"
            where = p.get("place") or "Place not recorded"
            c2.markdown(f"**{when}** · {where}")
            if p.get("caption"):
                c2.markdown(p["caption"])
            if p.get("memory"):
                c2.caption(p["memory"])
        st.write("")


def view_travels(ordered: list[dict]):
    stops, unmapped = build_trips(ordered)
    if not stops:
        st.info("None of these memories has a location yet. Add a place (e.g. 'Kyoto' or 'Paris, France') "
                "or use **📍 Suggest places with AI** in **2 · Understand memories**.")
        return
    import pydeck as pdk
    countries = sorted({s["country"] for s in stops if s["country"]})
    years = sorted({s["start"][:4] for s in stops if s["start"]})
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Destinations", len(stops))
    k2.metric("Countries", len(countries))
    k3.metric("Memories on the map", sum(len(s["photo_ids"]) for s in stops))
    k4.metric("Years", f"{years[0]}–{years[-1]}" if len(years) > 1 else (years[0] if years else "–"))

    chosen = st.session_state.get("travel_stop", 1)
    if not 1 <= chosen <= len(stops):
        chosen = 1
    points = [{"label": s["label"], "when": s["when"] or "Date unknown",
               "count": len(s["photo_ids"]), "num": str(s["number"]),
               "lat": s["lat"], "lon": s["lon"],
               "color": [234, 75, 221] if s["number"] == chosen else [91, 71, 199]} for s in stops]
    legs = [{"from": [a["lon"], a["lat"]], "to": [b["lon"], b["lat"]]} for a, b in zip(stops, stops[1:])]
    lat_span = max(s["lat"] for s in stops) - min(s["lat"] for s in stops)
    lon_span = max(s["lon"] for s in stops) - min(s["lon"] for s in stops)
    span = max(lat_span, lon_span / 2)
    zoom = 0.7 if span > 50 else 1.5 if span > 20 else 3 if span > 6 else 5 if span > 1 else 8
    view = pdk.ViewState(latitude=(max(s["lat"] for s in stops) + min(s["lat"] for s in stops)) / 2,
                         longitude=(max(s["lon"] for s in stops) + min(s["lon"] for s in stops)) / 2,
                         zoom=zoom, pitch=0)
    deck = pdk.Deck(
        map_style=None, initial_view_state=view,
        layers=[
            pdk.Layer("ArcLayer", legs, get_source_position="from", get_target_position="to",
                      get_source_color=[91, 71, 199, 210], get_target_color=[162, 138, 201, 210],
                      get_width=3, great_circle=True),
            pdk.Layer("ScatterplotLayer", points, get_position="[lon, lat]", get_fill_color="color",
                      get_radius=40000, radius_min_pixels=11, radius_max_pixels=18, stroked=True,
                      get_line_color=[255, 255, 255], line_width_min_pixels=2, pickable=True),
            pdk.Layer("TextLayer", points, get_position="[lon, lat]", get_text="num", get_size=13,
                      get_color=[255, 255, 255], get_text_anchor="'middle'",
                      get_alignment_baseline="'center'"),
        ],
        tooltip={"html": "<b>{label}</b><br/>{when}<br/>{count} memories",
                 "style": {"backgroundColor": "#1F2D4A", "color": "white"}},
    )
    st.pydeck_chart(deck, use_container_width=True)
    st.caption("Destinations are numbered in the order you visited them. Positions come from each "
               "photo's camera location or the place you entered, and stay on this computer.")

    st.markdown("##### Your journey")
    per_row = 4
    for row in range(0, len(stops), per_row):
        cols = st.columns(per_row)
        for col, s in zip(cols, stops[row:row + per_row]):
            with col.container(border=True):
                st.markdown(f"**{s['number']} · {s['label']}**")
                st.caption(f"{s['when'] or 'Date unknown'} · {len(s['photo_ids'])} "
                           f"memor{'y' if len(s['photo_ids']) == 1 else 'ies'}")
                if st.button("Viewing" if s["number"] == chosen else "View",
                             key=f"stop_{s['number']}", use_container_width=True,
                             type="primary" if s["number"] == chosen else "secondary"):
                    st.session_state["travel_stop"] = s["number"]
                    st.rerun()

    stop = stops[chosen - 1]
    st.markdown(f"#### {stop['label']}")
    st.caption(f"{stop['when'] or 'Date unknown'} · located from {stop['source']}")
    for pid in stop["photo_ids"]:
        p = by_id[pid]
        c1, c2 = st.columns([1, 2], gap="medium")
        c1.image(str(photo_path(ROOT, project["id"], p)), use_container_width=True)
        c2.markdown(f"**{p.get('caption') or p['filename']}**")
        c2.caption(f"{p.get('event_date') or p['metadata'].get('capture_date') or ''} · "
                   f"{p.get('place') or ''}")
        if p.get("memory"):
            c2.write(p["memory"])

    if unmapped:
        with st.expander(f"{len(unmapped)} memor{'y' if len(unmapped) == 1 else 'ies'} not on the map"):
            st.caption("Add a city or country, or use **📍 Suggest places with AI**, in **2 · Understand memories**.")
            for p in unmapped:
                st.write(f"• {p.get('caption') or p['filename']} · {p.get('place') or 'no place entered'}")

    st.divider()
    st.caption("Turn this journey into your story: one chapter per destination, written only "
               "from your own notes. This replaces the current chapters.")
    if st.button("Make chapters from these trips"):
        project["chapters"] = chapters_from_trips(stops, photos_all)
        save(project)
        rerun_notice("Created one chapter per destination. Refine them in step 3 · Ask for a story.")


def view_strip(ordered: list[dict]):
    st.image([str(photo_path(ROOT, project["id"], p)) for p in ordered], width=220,
             caption=[f"{p.get('caption') or p['filename']} · "
                      f"{p.get('event_date') or p['metadata'].get('capture_date') or ''}" for p in ordered])


def view_read(ordered: list[dict]):
    if project.get("dedication"):
        st.markdown(f"*{project['dedication']}*")
    if project.get("intro"):
        st.markdown(f"*{project['intro']}*")
    if not project.get("chapters"):
        st.caption("Ask for a story in step **3 · Ask for a story** to read it here.")
    for idx, ch in enumerate(project.get("chapters", []), 1):
        st.markdown(f'<div class="ls-kicker">Chapter {idx:02d}</div>', unsafe_allow_html=True)
        st.markdown(f"### {ch.get('title', 'Untitled')}")
        st.write(ch.get("text", ""))
        pics = [by_id[i] for i in ch.get("photo_ids", []) if i in by_id]
        if pics:
            st.image([str(photo_path(ROOT, project["id"], p)) for p in pics], width=320)
        st.divider()


VIEWS = {"travels": ("🌏 Travels", view_travels), "timeline": ("🕒 Timeline", view_timeline),
         "read": ("📖 Read", view_read), "strip": ("🎞️ Photo strip", view_strip)}

if step == 4:
    st.markdown('<div class="ls-kicker">Experience</div>', unsafe_allow_html=True)
    st.subheader(project.get("title") or "Your story")
    if project.get("story_request"):
        st.caption(f"“{project['story_request']}”")
    ordered = [by_id[i] for i in story_photo_ids(project) if i in by_id]
    if not ordered:
        st.info("Bring in photos and ask for a story to see it here.")
    else:
        if not project.get("chapters"):
            st.caption("No story yet, so all memories are shown by date.")
        # The main view for this type comes first. Travel stories lead with the map;
        # other types keep it last, for any photos that do have places.
        order = [btype["primary_view"]] + [k for k in ("timeline", "read", "strip", "travels")
                                           if k != btype["primary_view"]]
        for tab, key in zip(st.tabs([VIEWS[k][0] for k in order]), order):
            with tab:
                VIEWS[key][1](ordered)

# -------------------------------- Book --------------------------------
if step == 5:
    st.markdown('<div class="ls-kicker">Share</div>', unsafe_allow_html=True)
    st.subheader("Your photobook")
    if not photos_all or not project.get("chapters"):
        st.info("Bring in photos and ask for a story to make a book.")
    else:
        used = {pid for ch in project["chapters"] for pid in ch.get("photo_ids", [])}
        st.write(f"**{project.get('title') or btype['title']}**: {len(project['chapters'])} chapters, "
                 f"{len(used)} photos · cover label “{project.get('cover_kicker', btype['kicker'])}”")
        draft_watermark = st.checkbox("Label pages as a personal draft", value=True)
        unassigned = [p for p in photos_all if p["id"] not in used]
        if unassigned:
            st.caption(f"{len(unassigned)} photo(s) in this photobook are not part of this story and won't be in the book.")
        if st.button("Prepare PDF book", type="primary"):
            try:
                with st.spinner("Building your illustrated book..."):
                    st.session_state["rendered_pdf"] = generate_pdf(project, ROOT, mark_draft=draft_watermark)
                st.success("PDF ready. Review it before sharing.")
            except Exception as exc:
                st.error(f"PDF export failed: {exc}")
        if pdf_bytes := st.session_state.get("rendered_pdf"):
            st.download_button("⬇ Download photobook PDF", data=pdf_bytes,
                               file_name=f"{project['book_type']}-story.pdf", mime="application/pdf", type="primary")
            st.caption(f"{len(pdf_bytes) / 1024:.0f} KB • A4 portrait")
        st.markdown("#### Chapters")
        for idx, chapter in enumerate(project["chapters"], 1):
            st.write(f"**{idx:02d} · {chapter.get('title', 'Untitled')}** · {len(chapter.get('photo_ids', []))} photos")
            text = chapter.get("text", "")
            st.caption((text[:190] + "...") if len(text) > 190 else text)

# --------------------------- Back / Next ---------------------------
st.write("")
st.divider()
NEXT_BLOCK = {1: (not photos_all, "Add at least one photo to continue."),
              3: (not has_story, "Write a draft or write with AI to continue.")}
NEXT_HINT = {2: (f"{len(photos_all) - with_notes} photo(s) have no notes yet. You can still continue."
                 if photos_all and with_notes < len(photos_all) else "")}
back_col, hint_col, next_col = st.columns([1, 2, 1.3])
if step > 1 and back_col.button(f"← {STEPS[step - 2]}", use_container_width=True):
    go(step - 1)
blocked, why = NEXT_BLOCK.get(step, (False, ""))
hint_col.caption(why if blocked else NEXT_HINT.get(step, ""))
if step < len(STEPS):
    if next_col.button(f"Next: {STEPS[step]} →", type="primary", use_container_width=True, disabled=blocked):
        go(step + 1)
else:
    next_col.caption("🎉 That's the whole journey. Use the steps above to go back and change anything.")

st.divider()
st.caption("Privacy: photos and story text are stored on this computer under the data/ folder. Only the AI buttons "
           "send reduced images or text to OpenAI, and GPS is never sent. Check all AI-written text before sharing.")
