# Life Story — working prototype

*Your memories, gathered from everywhere and told as the journey they are.*

2026 AI Hackathon · Team 2. A local Streamlit prototype of the Life Story concept: it turns uploaded photographs into **a human-edited story you can view as a timeline, map, photo strip or illustrated PDF book**. It supports EXIF extraction, optional AI image descriptions, grounded story writing, chapter editing, and export.

### Choose your photobook up front

**＋ New photobook** opens a chooser. The type shapes the questions you're asked, how chapters are grouped, which story view opens first, the default writing voice, the AI writer's instructions and the PDF cover label. You can change it later from the sidebar.

| Type | Chapters grouped by | Opens on | Good for |
|---|---|---|---|
| 📖 Life story | Life stage | Timeline | A parent's or grandparent's story |
| 🌏 Travel story | Destination | Travels map | Holidays, gap years, every trip |
| 🎉 Milestone celebration | Life stage, ending in the celebration | Read | 18th/21st, wedding, anniversary, retirement |
| 📅 Year in review | Month | Timeline | A family's year, a baby's first year |
| 🕯️ In memory of | Life stage, gentle voice | Read | A memorial or tribute |
| 🌳 Family history | Decade | Timeline | Old scanned photos, reunions |
| 🏢 Business record | Month / phase, professional voice | Timeline | Project or site progress, event recaps, company history |

Types are defined in `storybook/book_types.py`; adding one is a single dictionary entry.

The app walks you through five numbered steps (a step bar at the top, a short note on what to do, and **← Back / Next →** buttons that tell you when you're ready to move on). They follow the two journeys in the architecture deck (`Hackathon_Docs/Life_Story.pptx`):

| Step | Deck layer | What works in the prototype |
|---|---|---|
| 1 · Link & bring in | Sources / Connect | Uploads. OneDrive, Google Photos, Instagram and Mail & calendar are shown as *planned* |
| 2 · Understand memories | Enrich | When & where from EXIF, AI photo insights (optional), your own words |
| 3 · Ask for a story | Reason | A story request, filtered by years and places, written as a local draft or by AI |
| 4 · Story views | Experience | **Travels** world map, timeline, photo strip, read view |
| 5 · Book | Share | A4 PDF **and** an interactive web book (one .html file) |

## What's prototype and what changes

The app marks, in the UI, which parts are the intended experience and which are only here for the prototype. A sidebar toggle, **Show what changes in the full app** (on by default), controls the markers; turn it off for a clean walkthrough.

| Marker | Meaning | Examples |
|---|---|---|
| 🧪 **Prototype only** | Only here so the prototype can run or be demoed. Removed in the full app. | Fictional demos, pasting an OpenAI key/model, Re-check camera data, Write a draft (no AI) |
| 🔁 **Changes in full app** | Works here as a simplified stand-in; built differently in the full app. | Local storage, uploads and the 30-photo limit, built-in place list, OpenAI API, year/place filters instead of the story agent, Streamlit/pydeck views, A4 PDF, share link |
| 🗓️ **Planned** | Not in the prototype yet. | Linking accounts, voice notes/video/meaning search, version history and approval, content safety |
| *(unmarked)* | The experience as intended. | Photobook types, the five steps, your own words, AI suggests/you confirm, chapter editing, story views |

A banner at the top of each page carries the standard caveat, each marked feature has a short note (**Here** / **Full app**), and the sidebar **Prototype guide** lists everything in one place. All the wording lives in `storybook/prototype_notes.py`, so it can be changed in one place to match the presentation.

## Start it

Requires **Python 3.10+**. In a terminal:

```bash
cd life_storybook_prototype
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Streamlit will open the app in a local browser, usually at `http://localhost:8501`.

**Fastest first run:** click **📖 Life** under *Or try a fictional demo* in the left sidebar. It creates a collection of *synthetic illustrations and fictional memories* (no personal photos or API key required). Two of the demo scenes carry location data, so the **Map** view has points. Go to **3 · Ask for a story** → **Write a draft**, then explore **4 · Story views** and build a PDF in **5 · Book**.

For the **Travels** world map, click **🌏 Travel** under *Or try a fictional demo*: a fictional trip through Tokyo, Kyoto, Singapore, Sydney and Paris. Open **4 · Story views → 🌏 Travels**.

To use your own photos, choose **＋ New photobook** → pick a type → **Link & bring in** → **Understand memories** → **Ask for a story** → **Story views** / **Book**.

## Optional live AI

1. Get an API key from your OpenAI account, subject to your organisation's data policies and billing.
2. Click any AI button and the app will ask for it (kept for the session only), or enter it under **AI settings** in the sidebar, or set `OPENAI_API_KEY` in the launch environment.
3. Use **✨ Describe** or **✨ Describe all photos with AI** to add *visible-only* observations. Note: no identification/face recognition is performed.
4. Correct the captions, date, people, places and memories yourself.
5. In **Ask for a story**, tick consent and choose **Write with AI**. Your story request is passed to the writer. Optionally include camera dates and/or **camera locations**: either the *nearest town or city* (recommended, e.g. "near Kyoto, Japan") or *exact coordinates* (with a warning). The writer is told to use locations only to name the general place and never to print coordinates or addresses. Both are off by default.
6. Review/edit generated chapters and export the book.

The model is configurable in the sidebar, defaulting to `gpt-4.1-mini`. The implementation uses the OpenAI **Responses API** with base64-encoded, resized, EXIF-stripped images and structured JSON replies. A compatible API model/account is required; use **Write a draft** if a key is not available. The local draft is *not AI-generated prose*: it assembles user-provided notes and photo observations into editable chapters, intentionally without inventing biographical details.

**Costs:** each AI photo analysis and story-generation call can incur API charges. Nothing is sent to OpenAI merely by uploading a file or clicking PDF export.

## Features

| Area | Works in local mode | Optional OpenAI mode |
|---|---|---|
| Multiple upload / duplicate avoidance | Yes | Not required |
| EXIF capture date / camera / GPS extraction | Yes | Not required |
| Human edits for names, relationships, places and memories | Yes | Not required |
| Image description from visual content | Manual edit | Yes, on explicit click |
| Story request filtered by years and places | Yes | Yes (request also guides the writer) |
| Chapter/story generation | Deterministic grounded draft | AI narrative from the saved context |
| Travels world map (destinations, route, trip cards, chapters from trips) | Yes | Yes |
| Timeline, photo strip and read views | Yes | Yes |
| Chapter titles, text, photo assignments and order | Yes | Yes |
| A4 illustrated book PDF / download | Yes | Yes |
| Project persistence between browser sessions | Local JSON + images | Same |

## Travels map

The Travels view places each photo using its **camera location** (EXIF GPS), or, if there is none, the **place you typed** (which can come from an accepted AI suggestion, below), matched against a built-in list of about 170 well-known cities and countries (`storybook/travel.py`). No online geocoding service is called, and coordinates never leave your computer. Photos taken close together in time and place (within 60 km) are grouped into one destination, numbered in the order visited and joined by route lines. Places that can't be matched are listed as *not on the map*. Add a city or country to place them, or extend the list in `travel.py`. The map is drawn with pydeck, which is installed with Streamlit.

## Interactive web book

Step 5 can also export the story as **one self-contained `.html` file** that opens in any browser and can be emailed or shared like the PDF. It includes:

- **Book**: page through a cover, opening note, one page per chapter and an ending. Use the buttons, the chapter menu, ← → keys or swipe on a phone.
- **Scroll**: the whole story on one page.
- **Timeline**: every photo in date order with its place and memory.
- **Map** (optional): a **built-in world map** with **every photo pinned as a clickable thumbnail**. Photos from the same place fan out around it, and clicking one opens it in the photo viewer. Places are joined by dashed route lines in visit order and listed as cards underneath; click a card to zoom to that place. Drag to pan, scroll or use + − to zoom, 🌍 for the whole world. Shown at **town/city level by default**; exact locations only if you tick that option. The map is an image inside the file (`storybook/assets/world_map.jpg`), so it **works offline and never sends locations to a map service**.
- **Photo viewer**: click any photo for a large view with its date, place, people and memory.

Photos and the map are embedded, so the whole book works offline. All user text is inserted as plain text, so it can't run as code. The app shows a live preview of the web book under the download buttons. Code: `storybook/book_html.py`.

## Share link

In step 5, **Create share link** gives a private link back to this app, e.g. `https://your-app/?story=qzis6atC…`. Opening it shows a **read-only** version of that story (the interactive book, scroll, timeline and map) with no sidebar or editing. The code in the link is long and random so it can't be guessed. **New link** replaces it, so the old one stops working, and **Turn off link** switches sharing off. Shared views always show places at town/city level.

- The link only works while the app is running somewhere others can reach. If it's running on your own computer (`localhost`), the app warns that the link only works there.
- If the app sits behind a proxy and detects the wrong address, set `LIFESTORY_PUBLIC_URL` (e.g. `https://life-story.example.com`).
- On Streamlit Community Cloud, saved stories (and so links) are lost when the app restarts. Fine for a demo; production would use the deck's Azure storage and sign-in.
- Anyone with the link can see the photos, places and memories in that story.

## AI place suggestions

For photos with no camera location, **📍 Suggest place** (per photo) or **📍 Suggest places with AI** (all at once) asks the model where the photo might have been taken, **only from clear visible evidence**: a well-known landmark, readable signs or tickets, or a distinctive landscape. It is told never to use people's faces or appearance, never to identify anyone, and to answer at city/country level at most. If the clues are weak it says so and suggests nothing. Each suggestion shows its evidence and confidence, and **nothing is saved to the photo or the map until you click "Use this place"**. The image sent is resized with EXIF/GPS removed.

## Data and privacy

- Storage defaults to `data/<project-id>/project.json` plus `images/` for the **original uploaded files**. Set `LIFESTORY_DATA_DIR` to store elsewhere. Data is not encrypted at rest.
- All files remain local unless **you explicitly invoke an OpenAI action**. Live photo calls upload resized JPEG versions with embedded EXIF removed. Photo uploads to the AI never include GPS. Camera dates and camera locations are excluded from story-writing requests unless you tick those options; locations default to the nearest town/city rather than exact coordinates.
- The story-generation call sends the text context you saved (caption, people, place, memories, edited observations, instructions), plus dates if explicitly permitted. Personal family notes may contain sensitive information; confirm you have appropriate consent and organisational approval before using live AI on personal images.
- **Delete this project** removes its folder and story data from this local installation; copies/downloads made elsewhere are not affected.
- **Security boundary:** THIS IS A SINGLE-USER, LOCAL PROTOTYPE. It has no authentication, user isolation, content scanning, encryption, or production audit controls. **Do not deploy it on a shared/public server** without adding access control, tenant-specific encrypted storage, deletion/retention policy, and abuse controls.
- EXIF camera clocks may be incorrect; visual AI observations and AI-written stories may be inaccurate. Review before publishing or sharing.
- Limit: **30 photographs per book**, **20 MB per file**, **45 MP per file**; HEIC is optional with `pip install pillow-heif`.

## Test it

Install test dependencies:

```bash
pip install pytest pypdf
pytest -q
```

The tests cover EXIF extraction, image validation, SHA-256 duplicate avoidance, API payload privacy, chapter grounding, project persistence, and demo-project-to-real-PDF export. They mock API calls and **do not incur charges**.

## Repo layout

```
app.py                    Streamlit user interface (Life Story theme)
storybook/core.py         File validation, EXIF, storage, chronology and story filtering
storybook/ai.py           Responses API image observation and story drafting
storybook/book_pdf.py     A4 PDF export using ReportLab
storybook/book_html.py    Interactive web book export (single HTML file)
storybook/book_types.py   Photobook types: prompts, grouping, main view, cover label
storybook/travel.py       Travels: built-in place list, trip grouping, chapters from trips
storybook/demo.py         Synthetic family and travel demo projects
storybook/prototype_notes.py  Prototype markers: what's prototype-only, what changes, what's planned
requirements.txt          Install requirements
.streamlit/config.toml    Theme and upload size
tests/test_workflow.py     Offline workflow tests
tests/test_prototype_notes.py  Checks every marker in the app has its wording
```

## Next iteration (after stakeholder feedback)

Authentication and team isolation, secure private cloud photo storage, chapter-level versioning, image sequencing/clustering, interviewer-style follow-up questions, Word/export themes, scanned-photo year estimation with clearly labelled uncertainty, and an approval workflow before publishing. Avoid automatically identifying individuals without their permission.
