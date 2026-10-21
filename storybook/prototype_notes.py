"""What in this prototype is the real experience, and what is only here for the prototype.

The app shows these as small coloured markers and notes (sidebar toggle: "Show what changes in the
full app"). Keeping them in one place means the UI, the sidebar guide and the presentation all say
the same thing. The "full" text describes the target Azure design in the architecture deck
(Hackathon_Docs/Life_Story.pptx and demo page 10), not something that is built yet.
"""
from __future__ import annotations

BANNER = ("Prototype: built to prove the experience, not the platform. Features, technology and "
          "wording will change as it moves to the target Azure design.")

# kind -> (icon, label, what it means, short legend text)
KINDS = {
    "proto": ("🧪", "Prototype only", "Only here so the prototype can run or be demoed. Removed in the full app.",
              "removed in the full app"),
    "change": ("🔁", "Changes in full app", "Works here, but as a simplified stand-in. Built differently in the full app.",
               "works here, built differently later"),
    "planned": ("🗓️", "Planned", "Not in the prototype yet. Part of the full design.",
                "not built yet"),
}

# key -> kind, title, what the prototype does here, what the full app does
NOTES = {
    # ---- Prototype only: removed in the full app ----
    "demo": dict(kind="proto", title="Fictional demos",
                 here="Load made-up photos and memories so the app can be shown without personal data.",
                 full="People start from their own linked accounts and uploads."),
    "ai_settings": dict(kind="proto", title="Pasting an OpenAI key and model name",
                        here="AI calls go to the public OpenAI API with a key you paste, kept for this "
                             "session only. The model name can be typed in.",
                        full="No key to paste: the app calls Azure OpenAI using managed identities and "
                             "Key Vault. The model is a setting the team manages and can swap as models improve."),
    "recheck": dict(kind="proto", title="Re-check camera data",
                    here="A maintenance button for photos added before an update to the app.",
                    full="Dates and places are read automatically as each memory comes in."),
    "quick_draft": dict(kind="proto", title="Write a draft (no AI)",
                        here="A fallback so the demo works without an AI key. It only arranges your own notes.",
                        full="Not decided yet. It may stay as a 'my notes only' option."),

    # ---- Changes in full app: a working stand-in ----
    "uploads": dict(kind="change", title="Uploads",
                    here="Up to 30 photos per book, 20 MB and 45 megapixels each, saved on this computer.",
                    full="Web upload straight to private cloud storage (Azure Blob Storage). Large libraries "
                         "are brought in in the background, with no 30-photo limit."),
    "storage": dict(kind="change", title="Where memories are kept",
                    here="Photos and story text are files in the data/ folder on this computer: one person, "
                         "no sign-in, not encrypted.",
                    full="A private, encrypted library for each person in Azure (Blob Storage, Cosmos DB and "
                         "AI Search), behind sign-in (Microsoft Entra External ID)."),
    "when_where": dict(kind="change", title="When & where",
                       here="Camera date and GPS, with typed places matched to a built-in list of about "
                            "170 cities and countries.",
                       full="Azure Maps finds any place, down to towns and landmarks."),
    "insights": dict(kind="change", title="Photo insights and place suggestions",
                     here="OpenAI API (gpt-4.1-mini). Prompt rules keep it to visible details, no face ID, "
                          "and places at city level.",
                     full="An Azure OpenAI vision model, with Azure AI Content Safety checks on every request."),
    "story_select": dict(kind="change", title="Choosing the memories for a story",
                         here="Your request guides the writer, but the year and place filters choose the photos. "
                              "Demo tip: pick the places you want before writing.",
                         full="The story agent reads the request (e.g. \"our trips to Japan\") and works out the "
                              "dates, places and memories itself."),
    "writer": dict(kind="change", title="Story writer",
                   here="OpenAI API (gpt-4.1-mini), with a consent tick each time and prompt rules only.",
                   full="Azure OpenAI via the story agent, with content safety checks and consent "
                        "given once per source."),
    "views": dict(kind="change", title="Story views",
                  here="Drawn by Streamlit. The Travels map uses pydeck and the built-in place list.",
                  full="The Life Story web app (Azure Static Web Apps) with Azure Maps, including animated "
                       "routes and playback."),
    "pdf": dict(kind="change", title="Printable PDF",
                here="A4 at screen resolution, with no bleed: fine for printing at home.",
                full="Print-ready files at full resolution, for ordering printed books."),
    "share": dict(kind="change", title="Share link",
                  here="There's no sign-in, so anyone with the link can view it, and it only works while this "
                       "app is running where others can reach it. Best left out of a live demo.",
                  full="Sharing tied to sign-in: you choose who can see each story and can stop sharing at any time."),
    "delete": dict(kind="change", title="Deleting a photobook",
                   here="Removes its files from this computer.",
                   full="Removes it from cloud storage and the memory index, under a clear retention policy."),

    # ---- Planned: not in the prototype ----
    "accounts": dict(kind="planned", title="Linking accounts",
                     here="Uploads only.",
                     full="OneDrive is linked once and new photos sync in. Google Photos uses Google's picker "
                          "to choose photos, Instagram uses your data download, and mail & calendar add dates "
                          "and events."),
    "more_media": dict(kind="planned", title="Voice notes, video and meaning search",
                       here="Photos only.",
                       full="Voice notes turned into text (Azure AI Speech), video highlights (Video Indexer), "
                            "and searching the whole library by meaning (Azure AI Search)."),
    "versions": dict(kind="planned", title="Version history and approval",
                     here="Saving a chapter replaces the earlier text.",
                     full="Each chapter keeps its earlier versions, and nothing is shared until you approve it."),
    "safety": dict(kind="planned", title="Content safety and monitoring",
                   here="Prompt rules only. There is no content filter or monitoring.",
                   full="Azure AI Content Safety checks what goes into and comes out of the AI, and "
                        "Application Insights monitors the service."),
}

# Shown in the sidebar guide: what the prototype is here to prove, which carries over as it is.
EXPERIENCE = [
    "Choosing a photobook type, and the five-step journey",
    "Adding your own words to each memory",
    "AI suggests, you confirm: descriptions and places are only saved when you accept or edit them",
    "Writing only from your photos and your words; filenames withheld, locations off unless you opt in",
    "Editing, reordering and removing chapters",
    "Seeing the story as a map, timeline, read view and photo strip",
    "A printable book and an interactive web book",
]

# Planned sources on the Link & bring in cards: how each will work in the full app.
SOURCE_PLANS = {
    "OneDrive": "Full app: link once and new photos sync in (Microsoft Graph).",
    "Google Photos": "Full app: choose photos with Google's Photos Picker each time.",
    "Instagram": "Full app: upload your Instagram data download.",
    "Mail & calendar": "Full app: dates and events from Microsoft Graph help place memories.",
}


def notes_by_kind() -> dict[str, list[tuple[str, dict]]]:
    """Notes grouped by kind, in KINDS order."""
    grouped = {kind: [] for kind in KINDS}
    for key, note in NOTES.items():
        grouped[note["kind"]].append((key, note))
    return grouped
