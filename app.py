"""Life Story prototype. Run with: streamlit run app.py"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from storybook.ai import DEFAULT_MODEL, analyse_photo, generate_ai_story, generate_local_story
from storybook.book_pdf import generate_pdf
from storybook.core import (InvalidPhoto, add_photo, chronological_photos, delete_project,
                            list_projects, load_project, new_project, photo_path, photo_year,
                            register_heif, save_project, select_photos)
from storybook.demo import make_demo_project, make_travel_demo_project
from storybook.travel import build_trips, chapters_from_trips

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
.ls-tagline {font-family: Georgia, serif; font-style: italic; color: #53617B; font-size: 1.15rem;
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


def story_photo_ids(project: dict) -> list[str]:
    """Photos in story order: by chapter if a story exists, otherwise by date."""
    ids = [pid for ch in project.get("chapters", []) for pid in ch.get("photo_ids", [])]
    return ids or [p["id"] for p in chronological_photos(project)]


# -------------------- Sidebar / project selection --------------------
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
    label_by_id = {p["id"]: p["title"] for p in projects}
    pick = st.selectbox("Your story collections", project_ids,
                        index=project_ids.index(st.session_state["active_project"]),
                        format_func=lambda key: label_by_id.get(key, "Untitled"))
    if pick != st.session_state["active_project"]:
        st.session_state["active_project"] = pick
        st.session_state.pop("rendered_pdf", None)
        st.rerun()
    if st.button("＋ New collection", use_container_width=True):
        p = new_project()
        save_project(ROOT, p)
        st.session_state["active_project"] = p["id"]
        rerun_notice("Created a new collection.")
    if st.button("✨ Load fictional demo", use_container_width=True,
                 help="Creates a separate collection with four synthetic illustrations and sample memories."):
        sample = make_demo_project(ROOT)
        st.session_state["active_project"] = sample["id"]
        rerun_notice("Loaded a fictional example. All artwork and memories are synthetic.")
    if st.button("🌏 Load travel demo", use_container_width=True,
                 help="Creates a separate collection of fictional trips (Tokyo, Kyoto, Singapore, Sydney, Paris)."):
        sample = make_travel_demo_project(ROOT)
        st.session_state["active_project"] = sample["id"]
        st.session_state["travel_stop"] = 1
        rerun_notice("Loaded a fictional travel story. Open 4 · Story views → Travels.")
    st.divider()
    with st.expander("AI settings (optional)", expanded=False):
        api_key = st.text_input("OpenAI API key", type="password", key="openai_key",
                                placeholder="sk-... (or set OPENAI_API_KEY)",
                                help="Held in this session only; never written to project files.") or os.getenv("OPENAI_API_KEY", "")
        model = st.text_input("Model", value=DEFAULT_MODEL, help="An image-capable OpenAI Responses API model.")
        st.caption("AI runs only when you click an AI button. API usage may incur charges.")
    st.caption("🟢 AI connected" if api_key else "⚪ AI off: local mode")
    with st.expander("Delete this collection", expanded=False):
        confirm = st.checkbox("Permanently delete its saved photos and story text", key="delete_confirm")
        if st.button("Delete collection", disabled=not confirm, type="secondary", use_container_width=True):
            delete_project(ROOT, st.session_state["active_project"])
            st.session_state.pop("active_project", None)
            rerun_notice("Collection deleted from local storage.")
    st.divider()
    st.caption("2026 AI Hackathon · Team 2 · Prototype\n\nSingle-user local demo: no login or encryption at rest.")

project = load_project(ROOT, st.session_state["active_project"])
if notice := st.session_state.pop("flash_notice", ""):
    st.success(notice)

# ------------------------------- Hero -------------------------------
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
photos_all = project["photos"]
m1, m2, m3, m4 = st.columns(4)
m1.metric("Memories", len(photos_all))
m2.metric("In your own words", sum(bool(p.get("memory", "").strip()) for p in photos_all))
m3.metric("Places", len({p["place"].strip() for p in photos_all if p.get("place", "").strip()}))
m4.metric("Story chapters", len(project.get("chapters", [])))

t_link, t_understand, t_ask, t_views, t_book = st.tabs([
    "1 · Link & bring in", "2 · Understand memories", "3 · Ask for a story", "4 · Story views", "5 · Book"
])

# -------------------------- Link & bring in --------------------------
with t_link:
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
        st.success(f"Brought in {added} photos; skipped {skipped} duplicates.")
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
with t_understand:
    st.markdown('<div class="ls-kicker">Enrich</div>', unsafe_allow_html=True)
    st.subheader("Each memory is understood")
    e1, e2, e3 = st.columns(3)
    e1.markdown('<div class="ls-card"><b>📍 When & where</b><div class="ls-sub">Read from the photo\'s camera data. '
                'Camera clocks can be wrong, so you confirm it.</div></div>', unsafe_allow_html=True)
    e2.markdown('<div class="ls-card"><b>👁 Photo insights</b><div class="ls-sub">AI describes only what is visible. '
                'It never identifies people.</div></div>', unsafe_allow_html=True)
    e3.markdown('<div class="ls-card"><b>💬 Your words</b><div class="ls-sub">Names, places and what it meant. '
                'These are what the story is built from.</div></div>', unsafe_allow_html=True)
    st.write("")
    if not photos_all:
        st.info("Bring in your first photos in **1 · Link & bring in**, or load the fictional demo from the sidebar.")
    else:
        if st.button("✨ Describe all photos with AI", disabled=not bool(api_key),
                     help="Sends one reduced-size, EXIF-stripped photo at a time; GPS is never sent."):
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
        if not api_key:
            st.caption("Add an API key under **AI settings** in the sidebar to use AI descriptions.")
        for p in chronological_photos(project):
            friendly = p.get("caption", "").strip() or p["filename"]
            done = "✅" if p.get("memory", "").strip() else "📷"
            with st.expander(f"{done} {friendly}", expanded=False):
                left, right = st.columns([1, 1.25], gap="large")
                with left:
                    st.image(str(photo_path(ROOT, project["id"], p)), use_container_width=True)
                    m = p["metadata"]
                    gps = m.get("gps")
                    st.markdown("**When & where (from the camera)**")
                    st.caption(f"Date: {m.get('capture_date') or 'Not available'} (unverified)  \n"
                               f"Location: " + (f"{gps['latitude']}, {gps['longitude']} (stays on this computer)"
                                                if gps else "Not available") + "  \n"
                               f"Camera: {m.get('camera') or 'Not available'}  \n"
                               f"Size: {m.get('dimensions', ['?', '?'])[0]} × {m.get('dimensions', ['?', '?'])[1]} px")
                    if p.get("question"):
                        st.info("💬 " + p["question"])
                    if st.button("✨ Describe with AI", key="analyse_" + p["id"], disabled=not bool(api_key)):
                        try:
                            with st.spinner("Looking at visible details..."):
                                result = analyse_photo(get_client(api_key), model,
                                                       photo_path(ROOT, project["id"], p))
                            p["observation"] = result.get("observation", "")
                            p["question"] = result.get("question", "")
                            p["analyzed"] = True
                            save(project)
                            rerun_notice("Description ready. Please check it and add your memory.")
                        except Exception as exc:
                            st.error(f"Image description failed: {exc}")
                with right:
                    with st.form("edit_photo_" + p["id"]):
                        caption = st.text_input("What happened", value=p.get("caption", ""))
                        date = st.text_input("When (YYYY-MM-DD, a year, or 'circa 1990')",
                                             value=p.get("event_date", ""))
                        place = st.text_input("Where", value=p.get("place", ""))
                        people = st.text_input("Who was there", value=p.get("people", ""))
                        memory = st.text_area("What do you remember?", value=p.get("memory", ""), height=115)
                        observation = st.text_area("Photo insights (AI draft, editable)",
                                                   value=p.get("observation", ""), height=90)
                        if st.form_submit_button("Save memory", type="primary"):
                            p.update({"caption": caption, "event_date": date, "place": place,
                                      "people": people, "memory": memory,
                                      "observation": observation})
                            save(project)
                            rerun_notice("Memory saved. Ask for a new story to include the changes.")
                    confirm_remove = st.checkbox("Confirm removal", key="confirm_remove_" + p["id"])
                    if st.button("Remove this photo", key="remove_" + p["id"],
                                 disabled=not confirm_remove):
                        location = photo_path(ROOT, project["id"], p)
                        project["photos"] = [item for item in project["photos"] if item["id"] != p["id"]]
                        for chapter in project["chapters"]:
                            chapter["photo_ids"] = [pid for pid in chapter["photo_ids"] if pid != p["id"]]
                        save(project)
                        location.unlink(missing_ok=True)
                        rerun_notice("Photo removed from this collection.")

# -------------------------- Ask for a story --------------------------
with t_ask:
    st.markdown('<div class="ls-kicker">Reason</div>', unsafe_allow_html=True)
    st.subheader("Ask for a story")
    if not photos_all:
        st.info("Bring in some photos first.")
    saved_filter = project.get("story_filter", {})
    with st.form("story_request_form"):
        request = st.text_input("What story would you like?", value=project.get("story_request", ""),
                                placeholder="e.g. Tell the story of growing up, for my 18th birthday")
        st.caption("Try: *Relive our trips to the coast* · *My school years* · *A year in our family*")
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
        voice_options = ["Warm and reflective", "Joyful and celebratory", "Simple and factual", "Gentle and poetic"]
        current_voice = project.get("voice", voice_options[0])
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
        st.caption("Arranges your own notes into chapters. Nothing is invented.")
        if st.button("Write a draft", use_container_width=True, type="primary", disabled=not matching):
            project["chapters"] = generate_local_story(story_project)
            save(project)
            rerun_notice("Draft ready. See it in 4 · Story views or refine it below.")
    with b2:
        st.markdown("**Story writer** (AI)")
        consent = st.checkbox("Send the notes for these memories to OpenAI to write the story.",
                              key="story_consent")
        share_exif = st.checkbox("Include camera dates (never GPS)", value=False)
        if st.button("✨ Write with AI", use_container_width=True,
                     disabled=not (matching and api_key and consent),
                     help="Replaces the current chapters. Copy any text you want to keep first."):
            try:
                with st.spinner("Writing your story from your memories..."):
                    project["chapters"] = generate_ai_story(get_client(api_key), model, story_project,
                                                            share_metadata=share_exif)
                save(project)
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
with t_views:
    st.markdown('<div class="ls-kicker">Experience</div>', unsafe_allow_html=True)
    st.subheader(project.get("title") or "Your story")
    if project.get("story_request"):
        st.caption(f"“{project['story_request']}”")
    by_id = {p["id"]: p for p in photos_all}
    ordered = [by_id[i] for i in story_photo_ids(project) if i in by_id]
    if not ordered:
        st.info("Bring in photos and ask for a story to see it here.")
    else:
        if not project.get("chapters"):
            st.caption("No story yet, so all memories are shown by date.")
        v_travel, v_time, v_strip, v_read = st.tabs(["🌏 Travels", "🕒 Timeline", "🎞️ Photo strip", "📖 Read"])
        with v_time:
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
        with v_travel:
            stops, unmapped = build_trips(ordered)
            if not stops:
                st.info("None of these memories has a location yet. Add a place (e.g. 'Kyoto' or 'Paris, France') "
                        "in **2 · Understand memories**, or try **🌏 Load travel demo** in the sidebar.")
            else:
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
                        st.caption("Add a city or country in **2 · Understand memories** to place these on the map.")
                        for p in unmapped:
                            st.write(f"• {p.get('caption') or p['filename']} · {p.get('place') or 'no place entered'}")

                st.divider()
                st.caption("Turn this journey into your story: one chapter per destination, written only "
                           "from your own notes. This replaces the current chapters.")
                if st.button("Make chapters from these trips"):
                    project["chapters"] = chapters_from_trips(stops, photos_all)
                    save(project)
                    rerun_notice("Created one chapter per destination. Refine them in 3 · Ask for a story.")
        with v_strip:
            st.image([str(photo_path(ROOT, project["id"], p)) for p in ordered], width=220,
                     caption=[f"{p.get('caption') or p['filename']} · "
                              f"{p.get('event_date') or p['metadata'].get('capture_date') or ''}" for p in ordered])
        with v_read:
            if project.get("intro"):
                st.markdown(f"*{project['intro']}*")
            if not project.get("chapters"):
                st.caption("Ask for a story in **3 · Ask for a story** to read it here.")
            for idx, ch in enumerate(project.get("chapters", []), 1):
                st.markdown(f'<div class="ls-kicker">Chapter {idx:02d}</div>', unsafe_allow_html=True)
                st.markdown(f"### {ch.get('title', 'Untitled')}")
                st.write(ch.get("text", ""))
                pics = [by_id[i] for i in ch.get("photo_ids", []) if i in by_id]
                if pics:
                    st.image([str(photo_path(ROOT, project["id"], p)) for p in pics], width=320)
                st.divider()

# -------------------------------- Book --------------------------------
with t_book:
    st.markdown('<div class="ls-kicker">Share</div>', unsafe_allow_html=True)
    st.subheader("Your storybook")
    if not photos_all or not project.get("chapters"):
        st.info("Bring in photos and ask for a story to make a book.")
    else:
        used = {pid for ch in project["chapters"] for pid in ch.get("photo_ids", [])}
        st.write(f"**{project.get('title', 'Our Life in Pictures')}**: {len(project['chapters'])} chapters, "
                 f"{len(used)} photos")
        draft_watermark = st.checkbox("Label pages as a personal draft", value=True)
        unassigned = [p for p in photos_all if p["id"] not in used]
        if unassigned:
            st.caption(f"{len(unassigned)} photo(s) in this collection are not part of this story and won't be in the book.")
        if st.button("Prepare PDF book", type="primary"):
            try:
                with st.spinner("Building your illustrated book..."):
                    st.session_state["rendered_pdf"] = generate_pdf(project, ROOT, mark_draft=draft_watermark)
                st.success("PDF ready. Review it before sharing.")
            except Exception as exc:
                st.error(f"PDF export failed: {exc}")
        if pdf_bytes := st.session_state.get("rendered_pdf"):
            st.download_button("⬇ Download storybook PDF", data=pdf_bytes,
                               file_name="life-story.pdf", mime="application/pdf", type="primary")
            st.caption(f"{len(pdf_bytes) / 1024:.0f} KB • A4 portrait")
        st.markdown("#### Chapters")
        for idx, chapter in enumerate(project["chapters"], 1):
            st.write(f"**{idx:02d} · {chapter.get('title', 'Untitled')}** · {len(chapter.get('photo_ids', []))} photos")
            text = chapter.get("text", "")
            st.caption((text[:190] + "...") if len(text) > 190 else text)

st.divider()
st.caption("Privacy: photos and story text are stored on this computer under the data/ folder. Only the AI buttons "
           "send reduced images or text to OpenAI, and GPS is never sent. Check all AI-written text before sharing.")
