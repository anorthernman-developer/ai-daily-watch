# AI Daily Watch

A daily briefing on Microsoft Copilot and Microsoft 365, Azure AI and Microsoft Foundry, Windows, Autopilot and Intune, VS Code and GitHub, Anthropic and Claude, OpenAI, Google Gemini and DeepMind, and the wider AI field.

Live site: https://anorthernman-developer.github.io/ai-daily-watch/

A **reimagining**.work project. Redesign the work. Then add the AI.

## What is here

| Path | What |
|---|---|
| `build.py` | Static site builder. Python 3.9+, standard library only. |
| `data/digests/YYYY-MM-DD.json` | One file per daily briefing (public fields only). |
| `data/sources.json` | The official channels the monitors prefer: blogs, newsrooms, changelogs, YouTube, X and Reddit. |
| `public/` | The generated site. GitHub Pages serves this folder as is, under `/ai-daily-watch/`. |
| `.github/workflows/pages.yml` | Deploys `public/` to GitHub Pages on every push to `main`. |
| `netlify.toml` | Left in place for the unused Netlify site; production is GitHub Pages. |

## Pages and feeds

Paths below are shown from the site root. On GitHub Pages they are served under `/ai-daily-watch/` (for example `/today/` is `https://anorthernman-developer.github.io/ai-daily-watch/today/`).

- `/` home: latest stories, counts by topic and company, links to every feed
- `/today/` latest briefing, `/briefings/YYYY-MM-DD/` each day, `/archive/` all days
- `/topics/` and `/topics/<topic>/` for the eight topics
- `/sources/` every official channel, grouped by type
- `/about/` how it is made
- `/feed.xml` (RSS), `/feed.json` (JSON Feed 1.1), `/feeds/<topic>.xml`
- `/api/` docs, `/api/index.json`, `/api/latest.json`, `/api/digests/<date>.json`, `/api/topics/<topic>.json`, `/api/sources.json`

Topic keys: `copilot-m365`, `azure-foundry`, `windows-autopilot-intune`, `devtools-github-vscode`, `anthropic-claude`, `openai`, `google-gemini`, `ai-trends`.

## How it updates

Each morning at about 07:00 UK time a private pipeline collects new events from eight Parallel Monitor API monitors, writes a dated digest, then runs `python3 build.py --sync`. The sync step copies only public fields into `data/`. The pipeline commits any change with the message `Daily update YYYY-MM-DD`, pushes, and GitHub Pages deploys `public/`. A day with no new items makes no commit.

Build locally:

```sh
python3 build.py            # rebuild public/ from data/
python3 -m http.server -d public 8000
```

## Caveats

Summaries are machine-written from public pages and can be wrong. The source link on each item is the evidence. A topic with no items means the monitor reported nothing new, not that nothing happened.
