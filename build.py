#!/usr/bin/env python3
"""AI Daily Watch: static site builder.

  python3 build.py           build public/ from data/ (what Netlify and CI use)
  python3 build.py --sync    first copy new digests + sources from the private pipeline (../) into data/, sanitised

Only public fields are copied: no monitor IDs, event IDs, run logs, API keys or state.
Standard library only. Output is deterministic: the same data gives byte-identical files.
"""
import argparse, hashlib, html, json, os, re, shutil, sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from email.utils import format_datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "public")
PIPE = os.path.dirname(HERE)
SITE_URL = os.environ.get("AIW_SITE_URL", "https://ai-daily-watch.netlify.app").rstrip("/")
REPO_URL = os.environ.get("AIW_REPO_URL", "https://github.com/anorthernman-developer/ai-daily-watch")
UK = ZoneInfo("Europe/London")
TITLE = "AI Daily Watch"

TOPICS = OrderedDict([
    ("copilot-m365", ("Microsoft Copilot & Microsoft 365", "Copilot", "Microsoft 365 Copilot, Copilot Chat, Copilot Studio and agents, the consumer Copilot app, Copilot in Windows and Edge, and Copilot+ PCs.")),
    ("azure-foundry", ("Azure AI & Microsoft Foundry", "Azure & Foundry", "Microsoft Foundry, Azure OpenAI, Foundry Agent Service, Azure AI services and major Azure platform updates.")),
    ("windows-autopilot-intune", ("Windows, Autopilot & Intune", "Windows & Autopilot", "Windows 11 and Insider builds, Windows AI features, Windows Autopilot and Microsoft Intune.")),
    ("devtools-github-vscode", ("VS Code, GitHub & developer tools", "Code & GitHub", "Visual Studio Code, GitHub and GitHub Copilot, Visual Studio and Microsoft developer platforms.")),
    ("anthropic-claude", ("Anthropic & Claude", "Anthropic", "Claude models and apps, Claude Code, the Claude developer platform, partnerships, research and safety policy.")),
    ("openai", ("OpenAI", "OpenAI", "GPT models, ChatGPT, the OpenAI API, Codex, Sora, partnerships, leadership and policy.")),
    ("google-gemini", ("Google Gemini & DeepMind", "Gemini", "Gemini models and app, the Gemini API and AI Studio, Gemini in Workspace and Android, and DeepMind research.")),
    ("ai-trends", ("AI news, innovation & trends", "AI trends", "Major model releases, agents, enterprise adoption, funding and deals, regulation in the UK, EU and US, research and open models.")),
])
SOURCE_TYPES = OrderedDict([("blog", "Blogs"), ("news", "Newsrooms and news"), ("changelog", "Changelogs"), ("roadmap", "Roadmaps"),
    ("docs", "Docs and what's new"), ("official", "Official pages"), ("status", "Status"), ("newsletter", "Newsletters"),
    ("youtube", "YouTube channels"), ("x", "X accounts"), ("reddit", "Reddit communities"), ("forum", "Forums")])
ITEM_FIELDS = ["title", "summary", "source_url", "published_date", "company", "category", "citations"]


# ---------- sync (private pipeline -> public data/) ----------
def safe_url(u):
    return u if isinstance(u, str) and re.match(r"^https?://[^\s\"'<>]+$", u) else ""


def sanitise_digest(d):
    items = []
    for i in d.get("items", []):
        if i.get("monitor_key") not in TOPICS:
            continue
        it = {k: i.get(k) for k in ITEM_FIELDS}
        it["source_url"] = safe_url(it.get("source_url"))
        it["citations"] = [c for c in (it.get("citations") or []) if safe_url(c)]
        it["topic"] = i["monitor_key"]
        it["event_date"] = i.get("event_date")
        key = it["source_url"] or (it.get("title") or "") + (it.get("published_date") or "")
        it["id"] = hashlib.sha1(key.encode()).hexdigest()[:12]
        items.append(it)
    items.sort(key=lambda x: (list(TOPICS).index(x["topic"]), x.get("published_date") or "", x["id"]))
    return {"date": d["date"], "generated_at": d.get("generated_at"), "count": len(items), "items": items}


def sync():
    os.makedirs(os.path.join(DATA, "digests"), exist_ok=True)
    src = os.path.join(PIPE, "digests")
    n = 0
    for f in sorted(os.listdir(src)):
        if not re.match(r"^\d{4}-\d{2}-\d{2}\.json$", f):
            continue
        pub = sanitise_digest(json.load(open(os.path.join(src, f))))
        dst = os.path.join(DATA, "digests", f)
        if os.path.exists(dst):  # same items as already published: keep the old timestamp so re-runs make no commit
            old = json.load(open(dst))
            if old.get("items") == pub["items"]:
                pub["generated_at"] = old.get("generated_at")
        text = json.dumps(pub, indent=1, ensure_ascii=False) + "\n"
        if not os.path.exists(dst) or open(dst).read() != text:
            open(dst, "w").write(text); n += 1
    s = json.load(open(os.path.join(PIPE, "sources.json")))
    pub = {"verified": (s.get("generated") or "")[:10], "count": 0, "sources": []}
    for x in s.get("sources", []):
        if safe_url(x.get("url")):
            pub["sources"].append({k: x.get(k) for k in ("name", "type", "url", "topic")})
    pub["count"] = len(pub["sources"])
    text = json.dumps(pub, indent=1, ensure_ascii=False) + "\n"
    dst = os.path.join(DATA, "sources.json")
    if not os.path.exists(dst) or open(dst).read() != text:
        open(dst, "w").write(text); n += 1
    print(f"sync: {n} data file(s) changed")


# ---------- helpers ----------
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def fmt_day(iso):
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%-d %b %Y")
    except Exception:
        return iso or ""


def fmt_uk(ts):
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UK)
        return dt.strftime("%-d %b %Y, %H:%M ") + dt.tzname()
    except Exception:
        return ""


def ridge():
    h = [18, 24, 30, 26, 34, 40, 46, 52, 48, 56, 62, 58, 66, 70, 64, 54, 50, 58, 44, 40, 36, 42, 32, 28, 34, 26, 22, 18, 14, 10]
    bars = "".join(f'<rect x="{i*9.6 + (i//5)*1.6:.1f}" y="{70-v}" width="7" height="{v}"/>' for i, v in enumerate(h))
    return f'<svg class="ridge" viewBox="0 0 300 70" role="img" aria-label="reimagining.work ridge" fill="currentColor">{bars}</svg>'


CSS = """
:root{--ink:#121416;--paper:#F4F4F1;--stone:#DEDDD7;--panel:#EAEAE5;--line:#CFCEC7;--granite:#5C6166;--muted:#50555A;--glacier:#1F5C8B;
--d:'Bricolage Grotesque',ui-sans-serif,system-ui,sans-serif;--s:'Source Serif 4',Georgia,serif;--m:'IBM Plex Mono',ui-monospace,monospace;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--ink:#ECECE7;--paper:#101214;--stone:#22262A;--panel:#181B1E;--line:#2C3034;--granite:#A3A8AD;--muted:#A3A8AD;--glacier:#6FA6D6}}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:400 18px/1.6 var(--s);-webkit-font-smoothing:antialiased}
a{color:var(--glacier);text-underline-offset:.18em}
a:focus-visible,button:focus-visible,summary:focus-visible{outline:3px solid var(--glacier);outline-offset:3px}
.skip{position:absolute;left:-999px;top:8px;background:var(--ink);color:var(--paper);padding:8px 12px;font-family:var(--d)}
.skip:focus{left:16px;z-index:9}
.wrap{max-width:1120px;margin:0 auto;padding:0 20px}
header.site{border-bottom:2px solid var(--ink)}
.wrap.bar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px 24px;min-height:64px;padding-top:12px;padding-bottom:12px}
.brand{display:flex;align-items:center;gap:12px;color:var(--ink);text-decoration:none}
.ridge{width:96px;height:auto;display:block;color:var(--ink)}
.brand b{font:800 22px/1 var(--d);letter-spacing:-.03em}
.brand small{display:block;font:400 13px/1.2 var(--d);letter-spacing:-.02em;color:var(--granite)}
.brand small strong{font-weight:800}
nav.top ul{display:flex;flex-wrap:wrap;gap:4px 18px;margin:0;padding:0;list-style:none}
nav.top a{font:600 15px/1 var(--d);color:var(--ink);text-decoration:none;padding:8px 0;display:inline-block;border-bottom:2px solid transparent}
nav.top a:hover{border-color:var(--ink)}
nav.top a[aria-current=page]{border-color:var(--glacier);color:var(--glacier)}
main.wrap{padding-top:40px;padding-bottom:72px}
.eyebrow{font:500 12px/1.4 var(--m);text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:0 0 8px}
h1,h2,h3{font-family:var(--d);text-wrap:balance;letter-spacing:-.025em;margin:0}
h1{font-weight:800;font-size:clamp(34px,5vw,52px);line-height:1.05;margin-bottom:16px}
h2{font-weight:800;font-size:26px;line-height:1.15;margin:0 0 4px}
h3{font-weight:600;font-size:20px;line-height:1.25}
.lede{max-width:65ch;font-size:19px;color:var(--ink);margin:0 0 8px}
p,li{max-width:65ch}
.muted{color:var(--muted)}
section.blk{border-top:2px solid var(--ink);padding-top:16px;margin-top:48px}
section.blk>header{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:4px 16px;margin-bottom:12px}
.label{font:800 14px/1 var(--d);letter-spacing:.14em;text-transform:uppercase;color:var(--glacier)}
.stamp{font:400 13px/1.5 var(--m);color:var(--muted);font-variant-numeric:tabular-nums}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:24px 32px}
/* link list (docs pattern) */
ul.links{list-style:none;margin:0;padding:0;border-top:2px solid var(--ink)}
ul.links li{max-width:none;border-bottom:1px solid var(--line)}
ul.links a{display:grid;grid-template-columns:1fr auto;gap:2px 12px;padding:12px 4px;text-decoration:none;color:var(--ink)}
ul.links a:hover{background:var(--panel)}
ul.links .t{font:600 16px/1.35 var(--d)}
ul.links .k{grid-column:1;font:400 12px/1.4 var(--m);text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
ul.links .go{grid-row:1/3;grid-column:2;align-self:center;font:400 16px/1 var(--m);color:var(--glacier)}
/* items */
ol.items{list-style:none;margin:0;padding:0}
ol.items>li{max-width:none;border-top:1px solid var(--line);padding:16px 0 18px}
ol.items>li:first-child{border-top:0}
.item h3{font-size:21px;margin:4px 0 6px}
.item h3 a{color:var(--ink);text-decoration-thickness:1px}
.item h3 a:hover{color:var(--glacier)}
.item p{margin:0 0 6px}
.meta{font:400 13px/1.5 var(--m);color:var(--muted);font-variant-numeric:tabular-nums}
.meta a{color:var(--glacier)}
.chip{display:inline-block;font:500 12px/1 var(--m);text-transform:uppercase;letter-spacing:.06em;background:var(--panel);color:var(--ink);padding:5px 7px;margin-right:6px;text-decoration:none}
a.chip:hover{background:var(--stone)}
.empty{border:1.5px dashed var(--muted);padding:12px 16px;color:var(--muted);margin:8px 0}
table{width:100%;border-collapse:collapse;border-top:2px solid var(--ink);font-size:16px}
th{font:500 12px/1.4 var(--m);text-transform:uppercase;letter-spacing:.08em;color:var(--muted);text-align:left;padding:10px 8px 8px 0;border-bottom:1px solid var(--line)}
td{padding:9px 8px 9px 0;border-bottom:1px solid var(--line);vertical-align:top}
td.n,th.n{text-align:right;font-family:var(--m);font-variant-numeric:tabular-nums;padding-right:0}
td.u{font:400 13px/1.5 var(--m);word-break:break-all}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:0;border-top:2px solid var(--ink);margin-top:24px}
.stats div{padding:12px 16px 12px 0;border-bottom:1px solid var(--line)}
.stats b{display:block;font:500 32px/1.1 var(--m);font-variant-numeric:tabular-nums}
.stats span{font:400 12px/1.4 var(--m);text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.callout{border-top:2px solid var(--ink);background:var(--stone);padding:16px 20px;margin:24px 0}
.toc{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 0;padding:0;list-style:none}
.toc li{max-width:none}
footer.site{border-top:2px solid var(--ink);padding:24px 0 48px;font-size:15px;color:var(--muted)}
footer.site p{margin:4px 0}
code{font:400 14px/1.4 var(--m);background:var(--panel);padding:2px 5px}
pre{font:400 14px/1.5 var(--m);background:var(--panel);padding:12px 16px;overflow:auto;max-width:100%}
@media (max-width:640px){body{font-size:17px}main.wrap{padding-top:28px}.ridge{width:96px}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
@media print{nav.top,.skip{display:none}body{background:#fff;color:#000}a{color:#1F5C8B}}
"""

FONTS = "https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,600;12..96,800&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=IBM+Plex+Mono:wght@400;500&display=swap"
NAV = [("/", "Home"), ("/today/", "Today"), ("/archive/", "Archive"), ("/topics/", "Topics"), ("/sources/", "Sources"), ("/feeds/", "Feeds & API"), ("/about/", "About")]


def page(path, title, body, section, desc, updated):
    nav = "".join(f'<li><a href="{h}"{" aria-current=page" if h == section else ""}>{t}</a></li>' for h, t in NAV)
    full = f"{title} · {TITLE}" if title != TITLE else f"{TITLE} · Microsoft, Copilot and AI news, daily"
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(full)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{SITE_URL}{path}">
<meta property="og:title" content="{E(full)}"><meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{SITE_URL}{path}"><meta property="og:type" content="website">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="alternate" type="application/rss+xml" title="{TITLE}: all topics" href="/feed.xml">
<link rel="alternate" type="application/feed+json" title="{TITLE}: all topics (JSON Feed)" href="/feed.json">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="/assets/site.css">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site"><div class="wrap bar">
<a class="brand" href="/" aria-label="{TITLE} home">{ridge()}<span><b>{TITLE}</b><small>by <strong>reimagining</strong>.work</small></span></a>
<nav class="top" aria-label="Main"><ul>{nav}</ul></nav>
</div></header>
<main id="main" class="wrap">
{body}
</main>
<footer class="site"><div class="wrap">
<p><strong>reimagining</strong>.work · Redesign the work. Then add the AI.</p>
<p class="stamp">Last update {E(updated)} · <a href="/feed.xml">RSS</a> · <a href="/feed.json">JSON Feed</a> · <a href="/api/">API</a> · <a href="{REPO_URL}">Source on GitHub</a></p>
<p>Summaries are machine-written from public sources. Check the linked source before you act on an item.</p>
</div></footer>
</body>
</html>
"""


def write(rel, text):
    p = os.path.join(OUT, rel.lstrip("/"))
    if rel.endswith("/"):
        p = os.path.join(p, "index.html")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


def item_html(i, show_topic=True, show_day=False):
    url = i.get("source_url")
    t = E(i.get("title") or "(untitled)")
    head = f'<a href="{E(url)}" rel="noopener">{t}</a>' if url else t
    chips = ""
    if show_topic:
        chips += f'<a class="chip" href="/topics/{i["topic"]}/">{E(TOPICS[i["topic"]][1])}</a>'
    if i.get("company") and not (show_topic and i["company"].lower() == TOPICS[i["topic"]][1].lower()):
        chips += f'<span class="chip">{E(i["company"])}</span>'
    meta = [x for x in [E(i.get("category") or ""), "Published " + E(fmt_day(i["published_date"])) if i.get("published_date") else ""] if x]
    if show_day and i.get("_day"):
        meta.append(f'<a href="/briefings/{i["_day"]}/">Briefing {E(fmt_day(i["_day"]))}</a>')
    dom = re.sub(r"^https?://(www\.)?", "", url or "").split("/")[0]
    if dom:
        meta.append(E(dom))
    extra = [c for c in i.get("citations") or [] if c != url][:3]
    also = ""
    if extra:
        also = '<p class="meta">Also: ' + ", ".join(f'<a href="{E(c)}" rel="noopener">{E(re.sub(r"^https?://(www\\.)?", "", c).split("/")[0])}</a>' for c in extra) + "</p>"
    return f'<li class="item" id="i-{i["id"]}"><div>{chips}</div><h3>{head}</h3><p>{E(i.get("summary") or "")}</p><p class="meta">{" · ".join(meta)}</p>{also}</li>'


def items_list(items, **kw):
    if not items:
        return '<p class="empty">No items yet. Unknown, not quiet: the monitor may not have reported.</p>'
    return '<ol class="items">' + "".join(item_html(i, **kw) for i in items) + "</ol>"


def links(rows):
    return '<ul class="links">' + "".join(f'<li><a href="{E(h)}"><span class="t">{E(t)}</span><span class="k">{E(k)}</span><span class="go" aria-hidden="true">↗</span></a></li>' for t, k, h in rows) + "</ul>"


def counts_table(counter, head, link=None):
    rows = "".join(f'<tr><td>{(f"<a href={chr(34)}{link(k)}{chr(34)}>{E(lbl)}</a>") if link else E(lbl)}</td><td class="n">{n}</td></tr>' for k, lbl, n in counter)
    return f'<table><thead><tr><th scope="col">{head}</th><th scope="col" class="n">Items</th></tr></thead><tbody>{rows}</tbody></table>'


# ---------- feeds ----------
def rss(items, title, desc, path, updated_dt):
    out = [f'<?xml version="1.0" encoding="utf-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>',
           f"<title>{E(title)}</title><link>{SITE_URL}/</link><description>{E(desc)}</description><language>en-gb</language>",
           f'<atom:link href="{SITE_URL}{path}" rel="self" type="application/rss+xml"/>',
           f"<lastBuildDate>{format_datetime(updated_dt)}</lastBuildDate>"]
    for i in items:
        try:
            pd = datetime.strptime((i.get("published_date") or i["_day"])[:10], "%Y-%m-%d").replace(hour=7, tzinfo=timezone.utc)
        except Exception:
            pd = updated_dt
        link = i.get("source_url") or f'{SITE_URL}/briefings/{i["_day"]}/'
        out.append(f'<item><title>{E(i.get("title"))}</title><link>{E(link)}</link><guid isPermaLink="false">aidw-{i["id"]}</guid>'
                   f'<pubDate>{format_datetime(pd)}</pubDate><category>{E(TOPICS[i["topic"]][0])}</category>'
                   f'<description>{E((i.get("company") or "") + ": " + (i.get("summary") or ""))}</description></item>')
    out.append("</channel></rss>\n")
    return "".join(out)


def jsonfeed(items, title, path):
    return json.dumps({"version": "https://jsonfeed.org/version/1.1", "title": title, "home_page_url": SITE_URL + "/", "feed_url": SITE_URL + path,
        "language": "en-GB", "items": [{"id": "aidw-" + i["id"], "url": i.get("source_url") or f'{SITE_URL}/briefings/{i["_day"]}/', "title": i.get("title"),
        "content_text": i.get("summary"), "date_published": (i.get("published_date") or i["_day"]) + "T07:00:00Z",
        "tags": [TOPICS[i["topic"]][0], i.get("company") or "", i.get("category") or ""]} for i in items]}, indent=1, ensure_ascii=False) + "\n"


def public_item(i):
    return {k: i.get(k) for k in ["id", "title", "summary", "source_url", "published_date", "company", "category", "topic", "citations"]} | {"briefing": i["_day"]}


# ---------- build ----------
def build():
    ddir = os.path.join(DATA, "digests")
    digests = []
    for f in sorted(os.listdir(ddir), reverse=True):
        if re.match(r"^\d{4}-\d{2}-\d{2}\.json$", f):
            digests.append(json.load(open(os.path.join(ddir, f))))
    if not digests:
        sys.exit("no digests in data/digests; run with --sync")
    sources = json.load(open(os.path.join(DATA, "sources.json")))
    allitems, seen = [], set()
    for d in digests:  # newest first, de-duplicated by id
        for i in d["items"]:
            if i["id"] in seen:
                continue
            seen.add(i["id"]); allitems.append(dict(i, _day=d["date"]))
    allitems.sort(key=lambda i: (i["_day"], i.get("published_date") or ""), reverse=True)
    latest = digests[0]
    upd_iso = max((d.get("generated_at") or d["date"] + "T07:00:00+00:00") for d in digests)
    upd_dt = datetime.fromisoformat(upd_iso.replace("Z", "+00:00"))
    updated = fmt_uk(upd_iso) or fmt_day(latest["date"])
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    os.makedirs(os.path.join(OUT, "assets"))
    open(os.path.join(OUT, "assets", "site.css"), "w").write(CSS.strip() + "\n")
    open(os.path.join(OUT, "favicon.svg"), "w").write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" fill="#121416"/><g fill="#F4F4F1"><rect x="5" y="18" width="4" height="9"/><rect x="11" y="10" width="4" height="17"/><rect x="17" y="5" width="4" height="22"/><rect x="23" y="14" width="4" height="13"/></g></svg>\n')
    P = lambda path, title, body, sec, desc: write(path, page(path, title, body, sec, desc, updated))
    by_topic = {k: [i for i in allitems if i["topic"] == k] for k in TOPICS}
    comp = Counter(i.get("company") or "Unknown" for i in allitems)

    # Home: docs-style hub (reference layout) + latest items and counts
    lt = Counter(i["topic"] for i in latest["items"])
    hub = [("Today's briefing", f'{fmt_day(latest["date"])} · {latest["count"]} items', "/today/"),
           ("Archive of daily briefings", f"{len(digests)} day(s)", "/archive/"),
           ("All items, combined feed", "RSS", "/feed.xml"),
           ("All items, combined feed", "JSON Feed", "/feed.json"),
           ("API docs", "API", "/api/"),
           ("Official sources", f'{sources["count"]} channels', "/sources/")]
    topic_blocks = "".join(f'<section class="blk" aria-labelledby="t-{k}"><header><h2 id="t-{k}">{E(v[0])}</h2><span class="stamp">{len(by_topic[k])} item(s) · {lt.get(k,0)} today</span></header>'
        + links([(f"{v[0]}: latest", "Page", f"/topics/{k}/"), ("RSS feed", "RSS", f"/feeds/{k}.xml"), ("JSON", "API", f"/api/topics/{k}.json")]) + "</section>" for k, v in TOPICS.items())
    body = f"""<p class="eyebrow">Daily · updated about 07:00 UK time</p>
<h1>Microsoft and AI, every morning.</h1>
<p class="lede">One briefing a day on Microsoft Copilot, Microsoft 365, Azure and Foundry, Windows and Autopilot, VS Code and GitHub, plus Anthropic, OpenAI, Google Gemini and the wider AI field. Every item links to its source. Every topic has its own page, RSS feed and JSON.</p>
<div class="stats" role="list">
<div role="listitem"><b>{latest["count"]}</b><span>Items on {E(fmt_day(latest["date"]))}</span></div>
<div role="listitem"><b>{len(allitems)}</b><span>Items to date</span></div>
<div role="listitem"><b>{len(TOPICS)}</b><span>Topics watched</span></div>
<div role="listitem"><b>{sources["count"]}</b><span>Official sources</span></div>
</div>
<section class="blk" aria-labelledby="latest"><header><h2 id="latest">Latest stories</h2><span class="stamp">Briefing {E(fmt_day(latest["date"]))} · <a href="/today/">Read the full briefing</a></span></header>
{items_list(allitems[:12], show_day=True)}</section>
<section class="blk" aria-labelledby="counts"><header><h2 id="counts">Where the news came from</h2><span class="stamp">All briefings to date</span></header>
<div class="grid2"><div>{counts_table([(k, v[0], len(by_topic[k])) for k, v in TOPICS.items()], "Topic", lambda k: f"/topics/{k}/")}</div>
<div>{counts_table([(c, c, n) for c, n in sorted(comp.items(), key=lambda x: (-x[1], x[0]))], "Company")}</div></div></section>
<section class="blk" aria-labelledby="feeds"><header><h2 id="feeds">Briefings, feeds and API</h2></header>{links(hub)}</section>
{topic_blocks}"""
    P("/", TITLE, body, "/", "Daily briefing on Microsoft Copilot, Azure, Windows, GitHub, Anthropic, OpenAI, Gemini and AI trends, with RSS and JSON feeds.")

    # Briefings
    def briefing_body(d, canonical_note=""):
        its = [dict(i, _day=d["date"]) for i in d["items"]]
        t = Counter(i["topic"] for i in its)
        toc = '<ul class="toc">' + "".join(f'<li><a class="chip" href="#{k}">{E(v[1])} · {t.get(k,0)}</a></li>' for k, v in TOPICS.items()) + "</ul>"
        secs = "".join(f'<section class="blk" aria-labelledby="{k}"><header><h2 id="{k}">{E(v[0])}</h2><span class="stamp">{t.get(k,0)} item(s)</span></header>'
                       + (items_list([i for i in its if i["topic"] == k], show_topic=False) if t.get(k) else '<p class="empty">No new items reported for this topic today.</p>') + "</section>" for k, v in TOPICS.items())
        i = [x["date"] for x in digests].index(d["date"])
        prev = digests[i + 1]["date"] if i + 1 < len(digests) else None
        nxt = digests[i - 1]["date"] if i > 0 else None
        pn = " · ".join(x for x in [f'<a href="/briefings/{prev}/">Previous: {fmt_day(prev)}</a>' if prev else "", f'<a href="/briefings/{nxt}/">Next: {fmt_day(nxt)}</a>' if nxt else "", '<a href="/archive/">Archive</a>'] if x)
        return f"""<p class="eyebrow">Daily briefing{canonical_note}</p><h1>Briefing for {E(fmt_day(d["date"]))}</h1>
<p class="lede">{d["count"]} new item(s) across {len(TOPICS)} topics. Generated {E(fmt_uk(d.get("generated_at") or ""))}.</p>{toc}{secs}
<p class="stamp" style="margin-top:32px">{pn} · <a href="/api/digests/{d["date"]}.json">This briefing as JSON</a></p>"""
    for d in digests:
        P(f'/briefings/{d["date"]}/', f'Briefing {fmt_day(d["date"])}', briefing_body(d), "/archive/", f'AI Daily Watch briefing for {fmt_day(d["date"])}: {d["count"]} items.')
    P("/today/", "Today", briefing_body(latest, " · latest"), "/today/", f'Latest AI Daily Watch briefing, {fmt_day(latest["date"])}.')

    rows = "".join(f'<tr><td><a href="/briefings/{d["date"]}/">{E(fmt_day(d["date"]))}</a></td><td class="n">{d["count"]}</td><td>{E(", ".join(TOPICS[k][1] for k in TOPICS if any(i["topic"] == k for i in d["items"])) or "None")}</td><td><a href="/api/digests/{d["date"]}.json">JSON</a></td></tr>' for d in digests)
    P("/archive/", "Archive", f'<p class="eyebrow">Archive</p><h1>Every daily briefing</h1><p class="lede">{len(digests)} briefing(s), newest first.</p><section class="blk"><table><thead><tr><th scope="col">Date</th><th scope="col" class="n">Items</th><th scope="col">Topics with news</th><th scope="col">Data</th></tr></thead><tbody>{rows}</tbody></table></section>', "/archive/", "Archive of AI Daily Watch briefings.")

    # Topics
    P("/topics/", "Topics", '<p class="eyebrow">Topics</p><h1>Eight topics, watched daily</h1><p class="lede">Each topic is one daily monitor. Pick one to see every item it has reported.</p>'
      + "".join(f'<section class="blk"><header><h2><a href="/topics/{k}/">{E(v[0])}</a></h2><span class="stamp">{len(by_topic[k])} item(s)</span></header><p>{E(v[2])}</p>{links([("Topic page", "Page", f"/topics/{k}/"), ("RSS feed", "RSS", f"/feeds/{k}.xml"), ("JSON", "API", f"/api/topics/{k}.json")])}</section>' for k, v in TOPICS.items()),
      "/topics/", "The eight AI Daily Watch topics.")
    for k, v in TOPICS.items():
        P(f"/topics/{k}/", v[0], f'<p class="eyebrow">Topic</p><h1>{E(v[0])}</h1><p class="lede">{E(v[2])}</p><p class="stamp">{len(by_topic[k])} item(s) to date · <a href="/feeds/{k}.xml">RSS</a> · <a href="/api/topics/{k}.json">JSON</a></p><section class="blk"><header><h2>All items</h2></header>{items_list(by_topic[k], show_topic=False, show_day=True)}</section>',
          "/topics/", f"AI Daily Watch: {v[0]}.")

    # Sources
    groups = OrderedDict((t, []) for t in SOURCE_TYPES)
    for s in sources["sources"]:
        groups.setdefault(s.get("type") or "other", []).append(s)
    toc = '<ul class="toc">' + "".join(f'<li><a class="chip" href="#src-{t}">{E(SOURCE_TYPES.get(t, t.title()))} · {len(g)}</a></li>' for t, g in groups.items() if g) + "</ul>"
    secs = "".join(f'<section class="blk" aria-labelledby="src-{t}"><header><h2 id="src-{t}">{E(SOURCE_TYPES.get(t, t.title()))}</h2><span class="stamp">{len(g)}</span></header><table><thead><tr><th scope="col">Name</th><th scope="col">Topic</th><th scope="col">Link</th></tr></thead><tbody>'
                   + "".join(f'<tr><td>{E(s["name"])}</td><td>{E(s.get("topic") or "")}</td><td class="u"><a href="{E(s["url"])}" rel="noopener">{E(re.sub(r"^https?://(www\.)?", "", s["url"]).rstrip("/"))}</a></td></tr>' for s in sorted(g, key=lambda s: ((s.get("topic") or ""), s["name"].lower())))
                   + "</tbody></table></section>" for t, g in groups.items() if g)
    P("/sources/", "Sources", f'<p class="eyebrow">Sources</p><h1>{sources["count"]} official channels</h1><p class="lede">The blogs, newsrooms, changelogs, roadmaps, YouTube channels, X accounts and Reddit communities the monitors prefer. Each link was checked on {E(fmt_day(sources.get("verified") or ""))}.</p>{toc}{secs}', "/sources/", "Official Microsoft, Anthropic, OpenAI and Google AI channels, blogs, YouTube, X and Reddit.")

    # Feeds & API
    feed_rows = [("Combined feed, latest 100 items", "RSS", "/feed.xml"), ("Combined feed, latest 100 items", "JSON Feed", "/feed.json")] + [(f"{v[0]}", "RSS", f"/feeds/{k}.xml") for k, v in TOPICS.items()]
    api_rows = [("API index", "JSON", "/api/index.json"), ("Latest items from every topic", "JSON", "/api/latest.json"), ("Latest briefing", "JSON", f'/api/digests/{latest["date"]}.json'), ("Sources", "JSON", "/api/sources.json")] + [(v[0], "JSON", f"/api/topics/{k}.json") for k, v in TOPICS.items()]
    P("/feeds/", "Feeds & API", f'<p class="eyebrow">Feeds &amp; API</p><h1>Take the news with you</h1><p class="lede">Every feed refreshes with the daily run. Read them in any RSS reader, or pull the JSON.</p><section class="blk"><header><h2>RSS and JSON feeds</h2></header>{links(feed_rows)}</section><section class="blk"><header><h2>JSON API</h2><a href="/api/">API docs</a></header>{links(api_rows)}</section>', "/feeds/", "RSS, JSON Feed and JSON API for AI Daily Watch.")
    example = json.dumps(public_item(allitems[0]), indent=1, ensure_ascii=False) if allitems else "{}"
    P("/api/", "API docs", f"""<p class="eyebrow">API</p><h1>Open JSON, no key</h1><p class="lede">Static JSON files, rebuilt each morning. No authentication, no rate limit beyond the host's. Cite the original source, not us.</p>
<section class="blk"><header><h2>Endpoints</h2></header><table><thead><tr><th scope="col">Path</th><th scope="col">What</th></tr></thead><tbody>
<tr><td class="u"><a href="/api/index.json">/api/index.json</a></td><td>Topics, briefing dates, counts and links</td></tr>
<tr><td class="u"><a href="/api/latest.json">/api/latest.json</a></td><td>Latest 100 items across all topics</td></tr>
<tr><td class="u">/api/digests/YYYY-MM-DD.json</td><td>One day's briefing</td></tr>
<tr><td class="u">/api/topics/&lt;topic&gt;.json</td><td>Every item for one topic</td></tr>
<tr><td class="u"><a href="/api/sources.json">/api/sources.json</a></td><td>The {sources["count"]} official sources</td></tr>
<tr><td class="u"><a href="/feed.json">/feed.json</a></td><td>JSON Feed 1.1, latest 100 items</td></tr></tbody></table></section>
<section class="blk"><header><h2>Topic keys</h2></header><table><tbody>{"".join(f'<tr><td class="u">{k}</td><td>{E(v[0])}</td></tr>' for k, v in TOPICS.items())}</tbody></table></section>
<section class="blk"><header><h2>Item shape</h2></header><pre>{E(example)}</pre></section>""", "/feeds/", "AI Daily Watch JSON API documentation.")

    for sub in ("feeds", "api/topics", "api/digests"):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    w = lambda rel, txt: open(os.path.join(OUT, rel), "w", encoding="utf-8").write(txt)
    w("feed.xml", rss(allitems[:100], f"{TITLE}: all topics", "Daily Microsoft, Copilot and AI news.", "/feed.xml", upd_dt))
    w("feed.json", jsonfeed(allitems[:100], f"{TITLE}: all topics", "/feed.json"))
    for k, v in TOPICS.items():
        w(f"feeds/{k}.xml", rss(by_topic[k][:100], f"{TITLE}: {v[0]}", v[2], f"/feeds/{k}.xml", upd_dt))
        w(f"api/topics/{k}.json", json.dumps({"topic": k, "name": v[0], "description": v[2], "count": len(by_topic[k]), "items": [public_item(i) for i in by_topic[k]]}, indent=1, ensure_ascii=False) + "\n")
    for d in digests:
        w(f'api/digests/{d["date"]}.json', json.dumps({"date": d["date"], "generated_at": d.get("generated_at"), "count": d["count"], "items": [public_item(dict(i, _day=d["date"])) for i in d["items"]]}, indent=1, ensure_ascii=False) + "\n")
    w("api/latest.json", json.dumps({"updated": upd_iso, "count": min(100, len(allitems)), "items": [public_item(i) for i in allitems[:100]]}, indent=1, ensure_ascii=False) + "\n")
    w("api/sources.json", json.dumps(sources, indent=1, ensure_ascii=False) + "\n")
    w("api/index.json", json.dumps({"name": TITLE, "site": SITE_URL, "updated": upd_iso, "latest_briefing": latest["date"], "items_total": len(allitems),
        "topics": [{"key": k, "name": v[0], "count": len(by_topic[k]), "json": f"{SITE_URL}/api/topics/{k}.json", "rss": f"{SITE_URL}/feeds/{k}.xml", "page": f"{SITE_URL}/topics/{k}/"} for k, v in TOPICS.items()],
        "briefings": [{"date": d["date"], "count": d["count"], "json": f'{SITE_URL}/api/digests/{d["date"]}.json', "page": f'{SITE_URL}/briefings/{d["date"]}/'} for d in digests]}, indent=1, ensure_ascii=False) + "\n")

    # About, 404, robots, sitemap
    P("/about/", "About", f"""<p class="eyebrow">About</p><h1>How the briefing is made</h1>
<p class="lede">We watch eight topics with a scheduled web monitor. Each morning we collect what it found, check it is new, and publish it here.</p>
<section class="blk"><header><h2>The method</h2></header><ol>
<li>Eight daily monitors on the Parallel Monitor API, one per topic. Each is told to prefer the official channels on the <a href="/sources/">Sources</a> page.</li>
<li>Each monitor reports new events with a headline, a two to three sentence summary, the company, a category and the source link.</li>
<li>At about 07:00 UK time a script collects the new events, removes duplicates and writes a dated briefing.</li>
<li>This site is rebuilt from those briefings, committed to <a href="{REPO_URL}">GitHub</a> and deployed to Netlify.</li></ol></section>
<section class="blk"><header><h2>What to trust</h2></header><div class="callout"><p class="label">Read the source</p><p>Summaries are written by a model from public pages. They can be wrong or out of date. The source link is the evidence. If an item has no source, treat it as Unknown.</p></div>
<p>A topic with no items means the monitor reported nothing new that day. It does not mean nothing happened.</p></section>
<section class="blk"><header><h2>Who runs it</h2></header><p>AI Daily Watch is a <strong>reimagining</strong>.work project by Craig Stanley. Redesign the work. Then add the AI.</p></section>""", "/about/", "How AI Daily Watch is made.")
    write("/404.html", page("/404.html", "Not found", '<h1>No page here</h1><p class="lede">That address does not exist. Try the <a href="/">home page</a> or the <a href="/archive/">archive</a>.</p>', "", "Page not found.", updated))
    urls = ["/", "/today/", "/archive/", "/topics/", "/sources/", "/feeds/", "/api/", "/about/"] + [f"/topics/{k}/" for k in TOPICS] + [f'/briefings/{d["date"]}/' for d in digests]
    w("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>{SITE_URL}{u}</loc></url>" for u in urls) + "</urlset>\n")
    w("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    print(f"build: {len(digests)} briefing(s), {len(allitems)} item(s), {sum(len(f) for _, _, f in os.walk(OUT))} files -> public/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sync", action="store_true", help="copy sanitised digests and sources from the private pipeline first")
    a = ap.parse_args()
    if a.sync:
        sync()
    build()
