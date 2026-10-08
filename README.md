# Life Storybook Studio — working proof of concept

A local Streamlit app that transforms uploaded photographs into **a human-edited, illustrated life storybook PDF**. It supports EXIF extraction, optional AI image descriptions, grounded narrative drafting, chapter editing, and export.

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

**Fastest first run:** click **Load fictional demo** in the left sidebar. It creates an editable book using *synthetic illustrations and fictional memories* (no personal photos or API key required). Go to **3 · Write your story** to modify chapters and **4 · Export book** to build/download a real PDF.

To use your own photos, choose **New blank project** → **Upload** → **Review & correct** → **Write your story** → **Export book**.

## Optional live AI

1. Get an API key from your OpenAI account, subject to your organisation's data policies and billing.
2. Enter it in the app sidebar, or set `OPENAI_API_KEY` in the launch environment.
3. Use **Analyse this photo with AI** or **Analyse all photographs with AI** to add *visible-only* observations. Note: no identification/face recognition is performed.
4. Correct the captions, date, people, places and memories yourself.
5. In **Write your story**, tick consent and choose **Generate with AI**. Optionally permit camera timestamps to be included (GPS is *never* sent).
6. Review/edit generated chapters and export the book.

The model is configurable in the sidebar, defaulting to `gpt-4.1-mini`. The implementation uses the OpenAI **Responses API** with base64-encoded, resized, EXIF-stripped images and structured JSON replies. A compatible API model/account is required; use **Create local draft** if a key is not available. The local draft is *not AI-generated prose*: it assembles user-provided notes and photo observations into editable chapters, intentionally without inventing biographical details.

**Costs:** each AI photo analysis and story-generation call can incur API charges. Nothing is sent to OpenAI merely by uploading a file or clicking PDF export.

## Features

| Area | Works in local mode | Optional OpenAI mode |
|---|---|---|
| Multiple upload / duplicate avoidance | Yes | Not required |
| EXIF capture date / camera / GPS extraction | Yes | Not required |
| Human edits for names, relationships, places and memories | Yes | Not required |
| Image description from visual content | Manual edit | Yes, on explicit click |
| Chapter/story generation | Deterministic grounded draft | AI narrative from the saved context |
| Chapter titles, text, photo assignments and order | Yes | Yes |
| A4 illustrated book PDF / download | Yes | Yes |
| Project persistence between browser sessions | Local JSON + images | Same |

## Data and privacy

- Storage defaults to `data/<project-id>/project.json` plus `images/` for the **original uploaded files**. Set `LIFESTORY_DATA_DIR` to store elsewhere. Data is not encrypted at rest.
- All files remain local unless **you explicitly invoke an OpenAI action**. Live photo calls upload resized JPEG versions with embedded EXIF removed. GPS coordinates are never included in requests. Raw EXIF dates are excluded from story-generation requests by default.
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
app.py                    Streamlit user interface
storybook/core.py         File validation, EXIF, storage and chronology
storybook/ai.py           Responses API image observation and story drafting
storybook/book_pdf.py     A4 PDF export using ReportLab
storybook/demo.py         Synthetic illustrated demo project
requirements.txt          Install requirements
.streamlit/config.toml    Theme and upload size
tests/test_workflow.py     Offline workflow tests
```

## Next iteration (after stakeholder feedback)

Authentication and team isolation, secure private cloud photo storage, chapter-level versioning, image sequencing/clustering, interviewer-style follow-up questions, Word/export themes, scanned-photo year estimation with clearly labelled uncertainty, and an approval workflow before publishing. Avoid automatically identifying individuals without their permission.
