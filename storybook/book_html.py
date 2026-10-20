"""Interactive web version of a photobook: one self-contained HTML file.

Photos are embedded (upright, resized), so the file works offline and can be shared like the
PDF. Only the optional map loads extra resources (Leaflet and map tiles) when it is opened.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from .core import chronological_photos, display_image
from .travel import CITIES, build_trips


def _approximate(stop: dict) -> tuple[float, float]:
    """Town/city-level position for sharing: snap to the known city, otherwise ~10 km."""
    if stop["name"] in CITIES:
        lat, lon, _ = CITIES[stop["name"]]
        return lat, lon
    return round(stop["lat"], 1), round(stop["lon"], 1)


def build_book_data(project: dict, root: Path, mark_draft: bool = True,
                    include_map: bool = True, precise_map: bool = False) -> dict:
    by_id = {p["id"]: p for p in project.get("photos", [])}
    order: list[str] = []
    for ch in project.get("chapters", []):
        for pid in ch.get("photo_ids", []):
            if pid in by_id and pid not in order:
                order.append(pid)
    index = {pid: i for i, pid in enumerate(order)}
    photos = []
    for pid in order:
        p = by_id[pid]
        src = "data:image/jpeg;base64," + base64.b64encode(
            display_image(root, project["id"], p, max_edge=1400)).decode("ascii")
        photos.append({
            "src": src,
            "caption": p.get("caption", ""),
            "date": p.get("event_date") or p.get("metadata", {}).get("capture_date") or "",
            "place": p.get("place", ""),
            "people": p.get("people", ""),
            "memory": p.get("memory", ""),
        })
    chapters = [{"title": ch.get("title", ""), "text": ch.get("text", ""),
                 "photos": [index[pid] for pid in ch.get("photo_ids", []) if pid in index]}
                for ch in project.get("chapters", [])]
    stops = []
    if include_map:
        trips, _ = build_trips([by_id[pid] for pid in order])
        for s in trips:
            lat, lon = (s["lat"], s["lon"]) if precise_map else _approximate(s)
            stops.append({"n": s["number"], "label": s["label"], "when": s["when"],
                          "lat": lat, "lon": lon, "photos": [index[pid] for pid in s["photo_ids"]]})
    dated = sorted(range(len(photos)), key=lambda i: (photos[i]["date"] == "", photos[i]["date"]))
    return {
        "title": project.get("title") or "Our Story",
        "subtitle": project.get("subtitle", ""),
        "kicker": project.get("cover_kicker") or "LIFE STORY",
        "dedication": project.get("dedication", ""),
        "intro": project.get("intro", ""),
        "draft": bool(mark_draft),
        "chapters": chapters,
        "photos": photos,
        "timeline": dated,
        "stops": stops,
        "travel": project.get("book_type") == "travel",
        "precise": bool(precise_map),
    }


def generate_html(project: dict, root: Path, mark_draft: bool = True,
                  include_map: bool = True, precise_map: bool = False) -> str:
    if not project.get("chapters"):
        raise ValueError("Please create or add a story chapter before exporting.")
    data = build_book_data(project, root, mark_draft, include_map, precise_map)
    # Safe to embed inside <script>: escape characters that could close the tag or break JS.
    payload = (json.dumps(data, ensure_ascii=False)
               .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
               .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    title = (data["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return TEMPLATE.replace("__TITLE__", title).replace("__DATA__", payload)


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#FBF8F4;--paper:#FFFFFF;--ink:#1F2D4A;--muted:#53617B;--accent:#5B47C7;--accent2:#A28AC9;
--line:#E6DFEF;--cream:#F5EFE8;--shadow:0 10px 30px rgba(31,45,74,.12)}
*{box-sizing:border-box}html,body{margin:0}
body{background:var(--bg);color:var(--ink);font:16px/1.65 system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
.serif{font-family:Georgia,"Times New Roman",serif;font-style:italic;font-weight:700}
header{position:sticky;top:0;z-index:5;background:rgba(251,248,244,.94);backdrop-filter:blur(6px);
border-bottom:1px solid var(--line)}
.bar{max-width:1100px;margin:0 auto;padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.bar .name{flex:1;min-width:180px}
.kicker{letter-spacing:.18em;font-size:.7rem;color:var(--accent);font-weight:700;text-transform:uppercase}
.bar .t{font-size:1.15rem;line-height:1.2}
.tabs{display:flex;gap:6px;flex-wrap:wrap}
.tabs button,.btn{border:1px solid var(--line);background:var(--paper);color:var(--ink);border-radius:999px;
padding:6px 14px;font:inherit;font-size:.9rem;cursor:pointer}
.tabs button[aria-selected=true],.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.btn:disabled{opacity:.4;cursor:default}
main{max-width:1100px;margin:0 auto;padding:20px 16px 60px}
.view{display:none}.view.on{display:block}
/* Book view */
.page{background:var(--paper);border-radius:18px;box-shadow:var(--shadow);min-height:520px;overflow:hidden;
display:grid;grid-template-columns:1.1fr 1fr;animation:turn .35s ease}
@keyframes turn{from{opacity:0;transform:translateX(18px)}to{opacity:1;transform:none}}
.page .pics{background:var(--cream);padding:18px;display:grid;gap:10px;align-content:center}
.page .pics.n1{grid-template-columns:1fr}.page .pics.n2{grid-template-columns:1fr 1fr}
.page .pics.n3,.page .pics.many{grid-template-columns:1fr 1fr}
.page .pics.n3 figure:first-child,.page .pics.many figure:first-child{grid-column:1/-1}
.page .words{padding:34px 36px;display:flex;flex-direction:column;justify-content:center}
.page h2{font-size:2rem;line-height:1.15;margin:.2em 0 .6em}
.page p{margin:0 0 1em;white-space:pre-line}
figure{margin:0;cursor:zoom-in;position:relative}
figure img{width:100%;height:100%;max-height:420px;object-fit:cover;border-radius:10px;display:block;background:#eee}
.pics.n1 figure img{max-height:470px;object-fit:contain;background:transparent}
figcaption{font-size:.8rem;color:var(--muted);margin-top:4px}
.cover{grid-template-columns:1fr;text-align:center;place-items:center;padding:40px 24px;background:var(--cream)}
.cover h1{font-size:clamp(2.2rem,6vw,3.6rem);line-height:1.05;margin:.3em 0 .2em}
.cover .sub{color:var(--muted);font-family:Georgia,serif;font-style:italic;font-size:1.2rem}
.cover img{max-width:min(560px,90%);max-height:340px;object-fit:cover;border-radius:12px;margin:24px auto 10px;
box-shadow:var(--shadow);cursor:zoom-in}
.cover .ded{font-family:Georgia,serif;font-style:italic;margin-top:12px}
.nav{display:flex;align-items:center;gap:10px;justify-content:space-between;margin-top:16px}
.nav .btn{white-space:nowrap}
.nav select{border:1px solid var(--line);border-radius:999px;padding:6px 12px;font:inherit;background:var(--paper);
color:var(--ink);flex:0 1 auto;min-width:0;max-width:60%}
.dots{display:flex;gap:6px;justify-content:center;margin-top:12px;flex-wrap:wrap}
.dots span{width:8px;height:8px;border-radius:50%;background:var(--line);cursor:pointer}
.dots span.on{background:var(--accent)}
/* Scroll view */
.chapter{background:var(--paper);border-radius:16px;box-shadow:var(--shadow);padding:28px 30px;margin:0 0 22px}
.chapter h2{font-size:1.8rem;margin:.1em 0 .5em}.chapter p{white-space:pre-line}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;margin-top:14px}
.grid figure img{height:170px}
/* Timeline */
.tl{position:relative;margin-left:12px;border-left:3px solid var(--accent2);padding-left:22px}
.tl .item{position:relative;display:grid;grid-template-columns:160px 1fr;gap:16px;background:var(--paper);
border-radius:14px;box-shadow:var(--shadow);padding:12px;margin-bottom:16px}
.tl .item:before{content:"";position:absolute;left:-32px;top:22px;width:14px;height:14px;border-radius:50%;
background:var(--accent);border:3px solid var(--bg)}
.tl .item img{width:160px;height:120px;object-fit:cover;border-radius:8px;cursor:zoom-in}
.tl .when{font-weight:700}.tl .where{color:var(--muted);font-size:.9rem}
/* Map */
#map{height:520px;border-radius:16px;box-shadow:var(--shadow);background:#eaf3f6}
.stops{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin-top:14px}
.stop{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:10px 12px;cursor:pointer}
.stop b{display:block}.stop small{color:var(--muted)}
.pin{background:var(--accent);color:#fff;border:2px solid #fff;border-radius:50%;width:28px;height:28px;
display:flex;align-items:center;justify-content:center;font:700 13px system-ui;box-shadow:0 2px 6px rgba(0,0,0,.3)}
.note{color:var(--muted);font-size:.85rem}
/* Lightbox */
.lb{position:fixed;inset:0;background:rgba(20,24,40,.92);display:none;z-index:20;align-items:center;
justify-content:center;padding:20px}
.lb.on{display:flex}
.lb .box{max-width:min(1100px,96vw);width:100%;display:grid;grid-template-columns:1fr 300px;gap:18px;color:#fff}
.lb img{width:100%;max-height:84vh;object-fit:contain;border-radius:8px}
.lb .info{align-self:center}.lb .info .when{color:#cfc6ef}.lb .info p{white-space:pre-line}
.lb .x,.lb .prev,.lb .next{position:fixed;background:rgba(255,255,255,.12);color:#fff;border:0;border-radius:50%;
width:44px;height:44px;font-size:22px;cursor:pointer}
.lb .x{top:16px;right:16px}.lb .prev{left:12px;top:50%}.lb .next{right:12px;top:50%}
footer{max-width:1100px;margin:0 auto;padding:0 16px 30px;color:var(--muted);font-size:.8rem;
display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
@media (max-width:760px){.page{grid-template-columns:1fr}.page .words{padding:22px}
.lb .box{grid-template-columns:1fr}.tl .item{grid-template-columns:1fr}.tl .item img{width:100%;height:180px}}
@media print{header,.nav,.dots,footer .keys{display:none}.view{display:block!important}#v-book,#v-map,#v-timeline{display:none!important}
.chapter{box-shadow:none;break-inside:avoid}}
</style>
</head>
<body>
<header><div class="bar">
  <div class="name"><div class="kicker" id="k"></div><div class="t serif" id="t"></div></div>
  <nav class="tabs" role="tablist" id="tabs"></nav>
</div></header>
<main>
  <section class="view" id="v-book"><div id="page"></div>
    <div class="nav"><button class="btn" id="prev">‹ Previous</button><select id="jump" aria-label="Go to page"></select>
    <button class="btn primary" id="next">Next ›</button></div><div class="dots" id="dots"></div></section>
  <section class="view" id="v-scroll"></section>
  <section class="view" id="v-timeline"><div class="tl" id="tl"></div></section>
  <section class="view" id="v-map"><div id="map"></div><p class="note" id="mapnote"></p><div class="stops" id="stops"></div></section>
</main>
<footer><span id="draft"></span><span class="keys">Use ← → to turn pages · click a photo to enlarge · made with Life Story</span></footer>
<div class="lb" id="lb" role="dialog" aria-modal="true"><button class="x" aria-label="Close">×</button>
<button class="prev" aria-label="Previous photo">‹</button><button class="next" aria-label="Next photo">›</button>
<div class="box"><img id="lbimg" alt=""><div class="info" id="lbinfo"></div></div></div>
<script>
const B = __DATA__;
const $ = s => document.querySelector(s);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls;
  if (text != null) e.textContent = text; return e; };
const paras = (parent, text) => String(text || "").split(/\n{2,}/).filter(x => x.trim())
  .forEach(t => parent.appendChild(el("p", null, t)));
function fig(i, cap) { const f = el("figure"); const im = el("img"); im.src = B.photos[i].src;
  im.alt = B.photos[i].caption || "Photo"; im.loading = "lazy"; f.appendChild(im);
  if (cap && B.photos[i].caption) f.appendChild(el("figcaption", null, B.photos[i].caption));
  f.onclick = () => openLb(i); return f; }

$("#k").textContent = B.kicker; $("#t").textContent = B.title; document.title = B.title;
$("#draft").textContent = B.draft ? "Personal draft: please review before sharing" : "";

/* ---------- Book view (cover, opening, chapters, end) ---------- */
const pages = [{kind: "cover"}];
if (B.intro || B.dedication) pages.push({kind: "intro"});
B.chapters.forEach((c, i) => pages.push({kind: "chapter", i}));
pages.push({kind: "end"});
let cur = 0;
pages.forEach((p, i) => { const o = el("option", null,
  p.kind === "cover" ? "Cover" : p.kind === "intro" ? "Before we begin" : p.kind === "end" ? "The end"
  : `${String(p.i + 1).padStart(2, "0")} · ${B.chapters[p.i].title}`); o.value = i; $("#jump").appendChild(o);
  const d = el("span"); d.title = o.textContent; d.onclick = () => show(i); $("#dots").appendChild(d); });
function show(i) {
  cur = Math.max(0, Math.min(pages.length - 1, i)); const p = pages[cur], box = $("#page"); box.innerHTML = "";
  const page = el("article", "page"); box.appendChild(page);
  if (p.kind === "cover") {
    page.classList.add("cover"); const w = el("div");
    w.appendChild(el("div", "kicker", B.kicker)); w.appendChild(el("h1", "serif", B.title));
    if (B.subtitle) w.appendChild(el("div", "sub", B.subtitle));
    if (B.photos.length) { const im = el("img"); im.src = B.photos[0].src; im.alt = "Cover photo";
      im.onclick = () => openLb(0); w.appendChild(im); }
    if (B.dedication) w.appendChild(el("div", "ded", B.dedication));
    page.appendChild(w);
  } else if (p.kind === "intro") {
    page.classList.add("cover"); const w = el("div"); w.appendChild(el("div", "kicker", "Before we begin"));
    if (B.dedication) w.appendChild(el("div", "ded", B.dedication));
    if (B.intro) { const t = el("div"); t.style.maxWidth = "620px"; t.style.marginTop = "18px"; paras(t, B.intro); w.appendChild(t); }
    page.appendChild(w);
  } else if (p.kind === "end") {
    page.classList.add("cover"); const w = el("div"); w.appendChild(el("div", "kicker", "The end"));
    w.appendChild(el("h1", "serif", B.title));
    w.appendChild(el("div", "sub", `${B.chapters.length} chapters · ${B.photos.length} photos`));
    const again = el("button", "btn primary", "Back to the beginning"); again.style.marginTop = "20px";
    again.onclick = () => show(0); w.appendChild(again); page.appendChild(w);
  } else {
    const c = B.chapters[p.i], n = c.photos.length;
    const pics = el("div", "pics " + (n <= 3 ? "n" + n : "many"));
    c.photos.slice(0, 5).forEach(ix => pics.appendChild(fig(ix, n <= 2)));
    if (n > 5) pics.appendChild(el("div", "note", `+ ${n - 5} more: see the scroll view`));
    const words = el("div", "words");
    words.appendChild(el("div", "kicker", "Chapter " + String(p.i + 1).padStart(2, "0")));
    words.appendChild(el("h2", "serif", c.title)); paras(words, c.text);
    if (n) page.appendChild(pics); else page.style.gridTemplateColumns = "1fr";
    page.appendChild(words);
  }
  $("#prev").disabled = cur === 0; $("#next").disabled = cur === pages.length - 1; $("#jump").value = cur;
  [...$("#dots").children].forEach((d, j) => d.classList.toggle("on", j === cur));
  try { history.replaceState(null, "", "#page-" + cur); } catch (e) { /* e.g. inside a preview frame */ }
}
$("#prev").onclick = () => show(cur - 1); $("#next").onclick = () => show(cur + 1);
$("#jump").onchange = e => show(+e.target.value);
let tx = null; $("#page").addEventListener("touchstart", e => tx = e.touches[0].clientX, {passive: true});
$("#page").addEventListener("touchend", e => { if (tx == null) return; const dx = e.changedTouches[0].clientX - tx;
  if (Math.abs(dx) > 50) show(cur + (dx < 0 ? 1 : -1)); tx = null; });

/* ---------- Scroll view ---------- */
B.chapters.forEach((c, i) => { const s = el("article", "chapter");
  s.appendChild(el("div", "kicker", "Chapter " + String(i + 1).padStart(2, "0")));
  s.appendChild(el("h2", "serif", c.title)); paras(s, c.text);
  if (c.photos.length) { const g = el("div", "grid"); c.photos.forEach(ix => g.appendChild(fig(ix, true))); s.appendChild(g); }
  $("#v-scroll").appendChild(s); });

/* ---------- Timeline ---------- */
B.timeline.forEach(ix => { const p = B.photos[ix], it = el("div", "item"); const im = el("img");
  im.src = p.src; im.alt = p.caption || "Photo"; im.loading = "lazy"; im.onclick = () => openLb(ix); it.appendChild(im);
  const t = el("div"); t.appendChild(el("div", "when", p.date || "Date unknown"));
  if (p.place) t.appendChild(el("div", "where", p.place));
  if (p.caption) t.appendChild(el("div", null, p.caption));
  if (p.memory) t.appendChild(el("div", "note", p.memory));
  it.appendChild(t); $("#tl").appendChild(it); });

/* ---------- Map (loads Leaflet only when opened) ---------- */
let mapReady = false;
function buildMap() {
  if (mapReady) return; mapReady = true;
  B.stops.forEach(s => { const c = el("div", "stop"); c.appendChild(el("b", null, `${s.n} · ${s.label}`));
    c.appendChild(el("small", null, `${s.when || "Date unknown"} · ${s.photos.length} photo${s.photos.length === 1 ? "" : "s"}`));
    c.onclick = () => openLb(s.photos[0]); $("#stops").appendChild(c); });
  $("#mapnote").textContent = (B.precise ? "Exact photo locations are shown." : "Positions are shown at town or city level.")
    + " Click a place to see its photos.";
  const css = document.createElement("link"); css.rel = "stylesheet";
  css.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"; document.head.appendChild(css);
  const js = document.createElement("script"); js.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
  js.onerror = () => { $("#map").style.display = "none";
    $("#mapnote").textContent = "The map needs an internet connection. The places are listed below."; };
  js.onload = () => {
    const map = L.map("map", {worldCopyJump: true});
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
      {attribution: "&copy; OpenStreetMap contributors &copy; CARTO", maxZoom: 18}).addTo(map);
    const pts = B.stops.map(s => [s.lat, s.lon]);
    if (pts.length > 1) L.polyline(pts, {color: "#5B47C7", weight: 3, opacity: .7, dashArray: "6 8"}).addTo(map);
    B.stops.forEach(s => {
      const icon = L.divIcon({className: "", html: `<div class="pin">${s.n}</div>`, iconSize: [28, 28], iconAnchor: [14, 14]});
      const pop = el("div"); pop.appendChild(el("b", null, s.label)); pop.appendChild(el("div", null, s.when || ""));
      const im = el("img"); im.src = B.photos[s.photos[0]].src; im.style.cssText = "width:180px;border-radius:6px;margin-top:6px;cursor:zoom-in";
      im.onclick = () => openLb(s.photos[0]); pop.appendChild(im);
      L.marker([s.lat, s.lon], {icon}).addTo(map).bindPopup(pop);
    });
    pts.length > 1 ? map.fitBounds(pts, {padding: [40, 40]}) : map.setView(pts[0], 6);
  };
  document.head.appendChild(js);
}

/* ---------- Tabs ---------- */
const views = [["book", "Book"], ["scroll", "Scroll"], ["timeline", "Timeline"]];
if (B.stops.length) views.splice(B.travel ? 1 : 3, 0, ["map", "Map"]);
function tab(name) {
  views.forEach(([v]) => { $("#v-" + v).classList.toggle("on", v === name);
    $("#tab-" + v).setAttribute("aria-selected", v === name); });
  if (name === "map") buildMap();
  if (name === "book") show(cur);
}
views.forEach(([v, label]) => { const b = el("button", null, label); b.id = "tab-" + v; b.setAttribute("role", "tab");
  b.onclick = () => tab(v); $("#tabs").appendChild(b); });

/* ---------- Photo viewer ---------- */
let lbi = 0;
function openLb(i) { lbi = (i + B.photos.length) % B.photos.length; const p = B.photos[lbi];
  $("#lbimg").src = p.src; $("#lbimg").alt = p.caption || "Photo"; const info = $("#lbinfo"); info.innerHTML = "";
  if (p.caption) info.appendChild(el("h3", "serif", p.caption));
  const meta = [p.date, p.place].filter(Boolean).join(" · "); if (meta) info.appendChild(el("div", "when", meta));
  if (p.people) info.appendChild(el("div", "when", p.people));
  if (p.memory) { const d = el("div"); paras(d, p.memory); info.appendChild(d); }
  info.appendChild(el("div", "note", `${lbi + 1} of ${B.photos.length}`)); $("#lb").classList.add("on"); }
const closeLb = () => $("#lb").classList.remove("on");
$("#lb .x").onclick = closeLb; $("#lb .prev").onclick = () => openLb(lbi - 1); $("#lb .next").onclick = () => openLb(lbi + 1);
$("#lb").onclick = e => { if (e.target.id === "lb") closeLb(); };
document.addEventListener("keydown", e => {
  if ($("#lb").classList.contains("on")) { if (e.key === "Escape") closeLb();
    if (e.key === "ArrowLeft") openLb(lbi - 1); if (e.key === "ArrowRight") openLb(lbi + 1); return; }
  if ($("#v-book").classList.contains("on")) { if (e.key === "ArrowLeft") show(cur - 1); if (e.key === "ArrowRight") show(cur + 1); }
});

const m = location.hash.match(/^#page-(\d+)$/); if (m) cur = +m[1];
tab("book");
</script>
</body>
</html>
"""
