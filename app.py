"""Run with: streamlit run app.py"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from storybook.ai import DEFAULT_MODEL, analyse_photo, generate_ai_story, generate_local_story
from storybook.book_pdf import generate_pdf
from storybook.core import (InvalidPhoto, add_photo, chronological_photos, delete_project,
                            list_projects, load_project, new_project, photo_path,
                            register_heif, save_project)
from storybook.demo import make_demo_project

st.set_page_config(page_title="Life Storybook Studio", page_icon="📖", layout="wide")
ROOT = Path(os.environ.get("LIFESTORY_DATA_DIR", Path(__file__).parent / "data")).expanduser().resolve()
ROOT.mkdir(parents=True, exist_ok=True)
HEIC_ENABLED = register_heif()

st.markdown("""<style>
.block-container {max-width: 1200px; padding-top: 1.8rem}
h1, h2, h3 {color: #173140}
[data-testid="stMetric"] {background: #f3f7f5; padding: 15px; border-radius: 10px}
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


# -------------------- Sidebar / project selection --------------------
with st.sidebar:
    st.title("📖 Storybook Studio")
    st.caption("A human-guided photo memoir prototype")
    projects = list_projects(ROOT)
    if not projects:
        p = new_project()
        save_project(ROOT, p)
        projects = list_projects(ROOT)
    project_ids = [p["id"] for p in projects]
    if st.session_state.get("active_project") not in project_ids:
        st.session_state["active_project"] = project_ids[0]
    label_by_id = {p["id"]: p["title"] for p in projects}
    pick = st.selectbox("Your projects", project_ids,
                        index=project_ids.index(st.session_state["active_project"]),
                        format_func=lambda key: label_by_id.get(key, "Untitled"))
    if pick != st.session_state["active_project"]:
        st.session_state["active_project"] = pick
        st.session_state.pop("rendered_pdf", None)
        st.rerun()
    if st.button("＋ New blank project", use_container_width=True):
        p = new_project()
        save_project(ROOT, p)
        st.session_state["active_project"] = p["id"]
        rerun_notice("Created a new project.")
    if st.button("✨ Load fictional demo", use_container_width=True,
                 help="Creates a separate project with four synthetic illustrations and sample memories."):
        sample = make_demo_project(ROOT)
        st.session_state["active_project"] = sample["id"]
        rerun_notice("Loaded a fictional example. All artwork and memories are synthetic.")
    st.divider()
    st.subheader("Optional AI")
    api_key = st.text_input("OpenAI API key", type="password", key="openai_key",
                            placeholder="sk-... (or set OPENAI_API_KEY)",
                            help="Held in this Streamlit session; never written to project files.") or os.getenv("OPENAI_API_KEY", "")
    model = st.text_input("Model", value=DEFAULT_MODEL, help="Choose an image-capable OpenAI Responses API model.")
    st.caption("AI calls happen only when you explicitly click Analyse or Generate with AI. API usage may incur charges.")
    st.divider()
    st.caption("Designed for local single-user demos. There is no login or encryption-at-rest. Do not publish it to a shared server without authentication and secure storage.")
    with st.expander("Delete this project", expanded=False):
        confirm = st.checkbox("Permanently delete all its saved photos and story text", key="delete_confirm")
        if st.button("Delete project", disabled=not confirm, type="secondary", use_container_width=True):
            delete_project(ROOT, st.session_state["active_project"])
            st.session_state.pop("active_project", None)
            rerun_notice("Project deleted from local storage.")

project = load_project(ROOT, st.session_state["active_project"])
if notice := st.session_state.pop("flash_notice", ""):
    st.success(notice)

st.title("Life Storybook Studio")
st.write("Turn personal photos into a **reviewable, editable, illustrated life story** — and export it as a book.")
col_a, col_b, col_c = st.columns(3)
col_a.metric("Photos", len(project["photos"]))
col_b.metric("With personal memories", sum(bool(p.get("memory", "").strip()) for p in project["photos"]))
col_c.metric("Chapters", len(project.get("chapters", [])))

t_upload, t_review, t_write, t_export = st.tabs([
    "1 · Upload", "2 · Review & correct", "3 · Write your story", "4 · Export book"
])

# ------------------------------ Upload ------------------------------
with t_upload:
    st.subheader("Add your photographs")
    st.write("Original files remain in this project's local folder. Camera EXIF is read where available; missing timestamps are not guessed.")
    uploaded = st.file_uploader("Choose photographs", type=["jpg", "jpeg", "png", "webp", "heic"],
                                accept_multiple_files=True,
                                help="Up to 30 images, maximum 20 MB and 45 megapixels each.")
    if not HEIC_ENABLED:
        st.caption("HEIC/HEIF requires the optional `pillow-heif` package. JPEG, PNG and WebP work without it.")
    if st.button("Add selected photographs", type="primary", disabled=not bool(uploaded)):
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
        st.success(f"Added {added} photographs; skipped {skipped} duplicates.")
        for error in errors:
            st.error(error)
    if project["photos"]:
        st.markdown("#### Current collection")
        previews = st.columns(4)
        for idx, photo in enumerate(chronological_photos(project)):
            with previews[idx % 4]:
                st.image(str(photo_path(ROOT, project["id"], photo)), use_container_width=True)
                st.caption(photo.get("caption") or photo["filename"])

# ------------------------ Photo review ------------------------------
with t_review:
    st.subheader("Make every memory accurate")
    st.write("AI can describe visible details, but **you** provide the names, locations and meaning. Original EXIF is displayed separately from corrections.")
    if not project["photos"]:
        st.info("Upload your first photograph or choose the fictional demo project.")
    else:
        st.caption("To use AI observations, add an API key in the sidebar. Each click sends an EXIF-stripped, resized image to OpenAI; GPS coordinates are never sent.")
        if st.button("Analyse all photographs with AI", disabled=not bool(api_key),
                     help="Sends one reduced-size photo at a time; each analysis incurs API usage."):
            progress = st.progress(0)
            errors = []
            client = get_client(api_key)
            for idx, p in enumerate(project["photos"]):
                try:
                    result = analyse_photo(client, model, photo_path(ROOT, project["id"], p))
                    p["observation"] = result.get("observation", "")
                    p["question"] = result.get("question", "")
                    p["analyzed"] = True
                    save(project)
                except Exception as exc:
                    errors.append(f"{p['filename']}: {exc}")
                progress.progress((idx + 1) / len(project["photos"]))
            if errors:
                st.warning("Some analyses did not complete: " + " | ".join(errors[:4]))
            else:
                rerun_notice("AI observations are ready. Please review every description.")
        for p in chronological_photos(project):
            friendly = p.get("caption", "").strip() or p["filename"]
            with st.expander(f"📷 {friendly}", expanded=False):
                left, right = st.columns([1, 1.25], gap="large")
                with left:
                    st.image(str(photo_path(ROOT, project["id"], p)), use_container_width=True)
                    m = p["metadata"]
                    st.caption(f"Image: {m.get('dimensions', ['?', '?'])[0]} × {m.get('dimensions', ['?', '?'])[1]} pixels")
                    st.caption(f"Camera date: {m.get('capture_date') or 'Not available'} (unverified)")
                    st.caption(f"Camera: {m.get('camera') or 'Not available'}")
                    gps = m.get("gps")
                    st.caption("GPS in original: " +
                               (f"{gps['latitude']}, {gps['longitude']} (local only)" if gps else "Not available"))
                    if p.get("question"):
                        st.info("AI follow-up question: " + p["question"])
                    if st.button("Analyse this photo with AI", key="analyse_" + p["id"],
                                 disabled=not bool(api_key)):
                        try:
                            with st.spinner("Examining visible details..."):
                                result = analyse_photo(get_client(api_key), model,
                                                       photo_path(ROOT, project["id"], p))
                            p["observation"] = result.get("observation", "")
                            p["question"] = result.get("question", "")
                            p["analyzed"] = True
                            save(project)
                            rerun_notice("Observation generated. Please verify it and add your memory.")
                        except Exception as exc:
                            st.error(f"Image analysis failed: {exc}")
                with right:
                    with st.form("edit_photo_" + p["id"]):
                        caption = st.text_input("Caption / event", value=p.get("caption", ""))
                        date = st.text_input("Corrected date (YYYY-MM-DD, year, or 'circa 1990')",
                                             value=p.get("event_date", ""))
                        place = st.text_input("Place (you confirm this)", value=p.get("place", ""))
                        people = st.text_input("People / relationships (you confirm this)",
                                               value=p.get("people", ""))
                        memory = st.text_area("What do you remember?", value=p.get("memory", ""), height=115)
                        observation = st.text_area("Visible description (AI draft, editable)",
                                                   value=p.get("observation", ""), height=90)
                        if st.form_submit_button("Save details", type="primary"):
                            p.update({"caption": caption, "event_date": date, "place": place,
                                      "people": people, "memory": memory,
                                      "observation": observation})
                            save(project)
                            rerun_notice("Updated photo context. Regenerate your story to apply the changes.")
                    confirm_remove = st.checkbox("Confirm removal", key="confirm_remove_" + p["id"])
                    if st.button("Remove this photo", key="remove_" + p["id"],
                                 disabled=not confirm_remove):
                        location = photo_path(ROOT, project["id"], p)
                        project["photos"] = [item for item in project["photos"] if item["id"] != p["id"]]
                        for chapter in project["chapters"]:
                            chapter["photo_ids"] = [pid for pid in chapter["photo_ids"] if pid != p["id"]]
                        save(project)
                        location.unlink(missing_ok=True)
                        rerun_notice("Photograph removed from this project.")

# -------------------------- Story drafting --------------------------
with t_write:
    st.subheader("Compose your life story")
    with st.form("book_preferences"):
        title = st.text_input("Book title", value=project.get("title", ""))
        subtitle = st.text_input("Subtitle", value=project.get("subtitle", ""))
        dedication = st.text_input("Dedication (optional)", value=project.get("dedication", ""))
        intro = st.text_area("Opening note (optional)", value=project.get("intro", ""), height=86)
        voice_options = ["Warm and reflective", "Joyful and celebratory", "Simple and factual", "Gentle and poetic"]
        current_voice = project.get("voice", voice_options[0])
        voice = st.selectbox("Writing style", voice_options,
                             index=voice_options.index(current_voice) if current_voice in voice_options else 0)
        instructions = st.text_area("Additional directions to the writer", value=project.get("instructions", ""),
                                    placeholder="e.g. Write in first person. Keep the language accessible to grandchildren.")
        if st.form_submit_button("Save book settings"):
            project.update({"title": title, "subtitle": subtitle, "dedication": dedication,
                            "intro": intro, "voice": voice, "instructions": instructions})
            save(project)
            rerun_notice("Saved your book settings.")
    st.divider()
    st.markdown("#### Generate a chapter draft")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("Create local draft (no API key)", use_container_width=True, type="primary",
                     disabled=not bool(project["photos"])):
            project["chapters"] = generate_local_story(project)
            save(project)
            rerun_notice("Created a local draft. Edit it or generate an AI version.")
    with b2:
        consent = st.checkbox("I agree to send the photo notes and selected metadata to OpenAI for story generation.",
                              key="story_consent")
        share_exif = st.checkbox("Include camera timestamps (never GPS)", value=False)
        if st.button("Generate with AI", use_container_width=True,
                     disabled=not (project["photos"] and api_key and consent),
                     help="Replaces current chapter drafts. Edit or copy their text first if needed."):
            try:
                with st.spinner("Drafting chapters from confirmed memories..."):
                    project["chapters"] = generate_ai_story(get_client(api_key), model, project,
                                                              share_metadata=share_exif)
                save(project)
                rerun_notice("AI story draft created. Review details before exporting.")
            except Exception as exc:
                st.error(f"Story generation failed: {exc}")
    st.caption("Generating a new draft replaces the previous chapter text. Your photo annotations remain saved.")
    st.divider()
    st.markdown("#### Edit the manuscript")
    chapters = project.get("chapters", [])
    photo_options = [p["id"] for p in chronological_photos(project)]
    filename_map = {p["id"]: p.get("caption") or p["filename"] for p in project["photos"]}
    for idx, chapter in enumerate(chapters):
        with st.expander(f"Chapter {idx + 1}: {chapter.get('title', 'Untitled')}", expanded=False):
            with st.form(f"edit_chapter_{idx}"):
                new_title = st.text_input("Chapter heading", value=chapter.get("title", ""))
                new_text = st.text_area("Narrative (fully editable)", value=chapter.get("text", ""), height=220)
                new_photos = st.multiselect("Photos on these pages", photo_options,
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

# ----------------------------- Export ------------------------------
with t_export:
    st.subheader("Your photo storybook")
    if not project["photos"] or not project.get("chapters"):
        st.info("Upload photos and create at least one chapter to enable book export.")
    else:
        st.write(f"**{project.get('title', 'Our Life in Pictures')}** — {len(project['chapters'])} chapters, {len(project['photos'])} original photographs")
        draft_watermark = st.checkbox("Label pages as a personal draft", value=True)
        photo_references = [pid for ch in project["chapters"] for pid in ch.get("photo_ids", [])]
        unassigned = [p for p in project["photos"] if p["id"] not in photo_references]
        if unassigned:
            st.warning(f"{len(unassigned)} photo(s) are not assigned to a chapter and will not be in the exported book. Add them in the chapter editor.")
        if st.button("Prepare PDF book", type="primary"):
            try:
                with st.spinner("Building your illustrated book..."):
                    st.session_state["rendered_pdf"] = generate_pdf(project, ROOT, mark_draft=draft_watermark)
                st.success("PDF prepared. Review it before sharing.")
            except Exception as exc:
                st.error(f"PDF export failed: {exc}")
        if pdf_bytes := st.session_state.get("rendered_pdf"):
            st.download_button("⬇ Download storybook PDF", data=pdf_bytes,
                               file_name="my-life-storybook.pdf", mime="application/pdf", type="primary")
            st.caption(f"{len(pdf_bytes) / 1024:.0f} KB • A4 portrait • includes original photos as embedded image previews")
        st.markdown("#### Chapter overview")
        for idx, chapter in enumerate(project["chapters"], 1):
            st.write(f"**{idx:02d} · {chapter.get('title', 'Untitled')}** · {len(chapter.get('photo_ids', []))} photos")
            text = chapter.get("text", "")
            st.caption((text[:190] + "...") if len(text) > 190 else text)

st.divider()
st.caption("Privacy: photographs and story text are stored locally under the data/ folder. Only explicit AI actions send reduced images or text to OpenAI. Delete your project to erase its local project folder. Verify all AI-generated statements.")
