# Job Scraper

Multi board job scraper - _Indeed_, _Dice_, _Glassdoor_ + _SQLite_ aggregation and HTML report suite supported by a FastAPI server:<br>
>- __NOTE:__ Architecture has been changed: 
>- _Historical_ - Oldder attempts and limitations I had to deal with in the past around _Cloudflare_ bypass as well as the reasons beind this repo now live in [LEGACY_CODE/README.md](LEGACY_CODE/README.md) if you need them:

---

## What it does today:

| Layer | Role |
|-------|------|
| **Scrape** | SeleniumBase UC Mode → one JSON file per query in `artifacts/json/` |
| **Store** | `modules/job_store.py` deduplicates into `artifacts/jobs.db` (jobs, sightings, clusters, applications) |
| **Reports** | Static HTML shells in `artifacts/html/` + live data using FastAPI on port **8765** |

**Job Boards**:

| Board | Auth | Notes |
|-------|------|-------|
| Indeed | Cookies required | Cookie-first strategy; `indeed_cookies.pkl` from `modules/get_cookies.py` |
| Dice | None | Two-phase search + optional detail fetch |
| Glassdoor | None | Scroll + in-page JS extraction |

---

## Quick start on _host_:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## First run (recommended)

Use the **attach menu** — it opens real Chrome, handles Cloudflare / Glassdoor checks, and runs the scraper for you. Prefer this over `python3 src/main.py` when you are new to the repo or scraping Indeed/Glassdoor.

```bash
bash maintance/run_scraper_attach.sh
```

| Menu | Board | Debug port |
|------|-------|------------|
| 1 | Indeed | 9222 |
| 2 | Glassdoor | 9223 |
| 3 | Dice | 9224 |
| 4 | All three (sequential) | — |

Single board (same flow, skip menu):

```bash
bash maintance/run_indeed_attach.sh
bash maintance/run_glassdoor_attach.sh
bash maintance/run_dice_attach.sh
```

**Indeed authentication (attach flow):**

1. **Start:** real **Google Chrome** opens (not Selenium). Default on first run: log in there and pass Cloudflare once.
2. **End:** optionally save `indeed_cookies.pkl` from that Chrome session for faster repeat runs.

| When | What to pick |
|------|----------------|
| First run / Cloudflare trouble | Log in in warm Chrome (default) |
| Regular scraping | Load saved `indeed_cookies.pkl` if you have one |

Avoid `get_cookies.py --auto` before attach — it uses Selenium on the auth page and often loops Cloudflare. Export after attach instead:

```bash
python3 modules/get_cookies.py --from-warm 9222   # while warm Chrome still open
```

**Reports (at end of attach):** you are asked whether to start the report server and open **http://127.0.0.1:8765/** in your browser. Say yes for Jobs search, Apply/Skip, and live dashboard data.

**All job titles from** `config/job_titles.ini`: run attach, then at prompts choose indices or type `all`.

**Reports without the attach prompt:**

```bash
bash scripts/start_report_server.sh          # http://127.0.0.1:8765/
python3 modules/generate_job_reports.py --import-json
```

## 1 · Scrape (advanced — direct CLI)

For automation/scripts. **Indeed and Glassdoor** usually need attach (above) — headless/auto CLI often hits Cloudflare or “Humans only”.

```bash
python3 src/main.py --auto --board dice --query "devops engineer" --location remote --max 50
python3 src/main.py --auto --board indeed --queries "DevOps,SDET" --remote --max 25
```

## 2 · Import + build reports

```bash
python3 modules/generate_job_reports.py --import-json
```

Rebuild specific pages:

```bash
python3 modules/generate_job_reports.py --variants index,dashboard,table,search,companies,cards,screenshots,compare
```

## 3 · Serve (browser + API)

```bash
bash scripts/start_report_server.sh
```

Or directly:

```bash
python3 modules/generate_job_reports.py --serve
```

Open **http://127.0.0.1:8765/** — Jobs and Search tabs needs a server. Dashboard/Cards work as static shells with lazy API loads:

Rebuild then serve:

```bash
python3 modules/generate_job_reports.py --serve --regenerate
```

---
## Report Pages:

| Page | Data source |
|------|-------------|
| **Dashboard** | Per-scrape JSON tables lazy-loaded via `/api/scrapes/{filename}/jobs` |
| **Jobs / Search** | Server-side `/api/jobs` (pagination, board filter, text search) |
| **Cards** | Apply / Skip / Interviewing → `applications` table (needs server) |
| **Companies, Compare, Screenshots** | Built at generate time from DB + JSON |

_Index Page:_
![index](/docs/png_repo_screenshots/Latest/Scraper_Index_Page.png)
_Dashboard Page:_
![Dboard](/docs/png_repo_screenshots/Latest/Scraper_Dashboard_Page.png)
_Dashboard iside look Page:_
![Dboard](/docs/png_repo_screenshots/Latest/Scraper_Dboard_page.png)
_Jobs Page:_
![jobs](/docs/png_repo_screenshots/Latest/Scraper_Jobs_Page.png)
_Search Page:_
![Search](/docs/png_repo_screenshots/Latest/Scraper_Search_page.png)
_ScreenShots Page:_
![ScreenShots](/docs/png_repo_screenshots/Latest/Scraper_ScreenShots_page_1.png)
_ScreenShots Page:_
![ScreenShots](/docs/png_repo_screenshots/Latest/Scraper_ScreenShots_page_2.png)
_Companies Page:_
![Companies](/docs/png_repo_screenshots/Latest/Scraper_Comp_Page.png)
_Data Records Compare Page:_
![SQLite vs JSON data look](/docs/png_repo_screenshots/Latest/Scraper_Data_Compare_page.png)
_Job Board Cards Page:_
![Board Cards](/docs/png_repo_screenshots/Latest/Scraper_Cards_page.png)
**API highlights**

- `GET /api/jobs?q=&board=&page=&limit=`
- `GET /api/scrapes/{filename}/jobs`
- `POST /api/applications/...` (Apply / Skip)
- `/screenshots/*` — page captures from `artifacts/screenshots/`

---

## Project layout

```
src/main.py                      <-- Scraper entry (auto / interactive)
modules/scraper_*.py             <-- Per-board scrapers
modules/job_store.py             <-- SQLite import + search helpers
modules/job_report_html.py       <-- HTML generators + embedded UI
modules/job_report_api.py        <-- FastAPI routes
modules/generate_job_reports.py  <-- Import / build / --serve CLI
maintance/run_*_attach.sh        <-- Chrome attach entry (start here)
maintance/lib/attach_common.sh   <-- shared attach orchestration (required)
artifacts/json/                  <-- Scrape output
artifacts/jobs.db                <-- Aggregated database
artifacts/html/                  <-- Generated reports
artifacts/screenshots/           <-- Page captures
build/                           <-- Docker (see below)
config/job_titles.ini            <-- Default queries for auto mode
```

---

# Docker:

Containerized scraping shares `artifacts/` with the host. **Indeed is host-only** (Cloudflare needs real Chrome / manual clicks). Docker is best for **Dice scrape + reports + serve**.

**Full guide:** [docs/Scraper_Docker_Setup.md](docs/Scraper_Docker_Setup.md)

```bash
./build/build.sh build
./build/build.sh all dice              # Dice + reports + serve → http://localhost:8765
./build/build.sh auto                  # shows Indeed host redirect if you try Docker
```

**Indeed on host** (then `./build/build.sh reports && ./build/build.sh serve`):

```bash
bash maintance/run_indeed_attach.sh
python3 src/main.py --auto --board indeed --queries "DevOps,SDET" --remote --max 25
```

---

# Environment:

Copy `.env.example` → `.env`. Key variables:

| Variable | Purpose |
|----------|---------|
| `TZ` | Timezone for logs and timestamps |
| `PROXY_*` | Optional residential proxy (Indeed) |
| `REPORT_HOST` | Bind address (`127.0.0.1` host, `0.0.0.0` in Docker) |
| `REPORT_PORT` | Host port for report server (default `8765`) |

---

## Maintenance

```bash
bash maintance/chrome_cache_cleanup.sh -d    # trim Chrome profile cache
python3 modules/generate_job_reports.py --prototypes   # UI theme experiments ( TBD )
```

---

---

## CI / tests

Merge CI runs on every PR (Python 3.13). **Two steps** — install deps with `pip`, run tests with `pytest`:

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -q \
  --cov=modules.job_store \
  --cov=modules.job_report_api \
  --cov-fail-under=60
```

Or one command:

```bash
bash scripts/run_tests.sh
```

`--cov` is a **pytest** flag (via `pytest-cov` + `coverage` in `requirements-dev.txt`), not a `pip` option.

| Job | When | What |
|-----|------|------|
| `python` | Always | pytest + 60% coverage on `job_store` + `job_report_api` |
| `config` | Always | `bash -n build/build.sh`, `docker compose config` |
| `docker-build` | PR touches `build/`, `modules/`, `src/`, `requirements*` | Image build + import smoke |

No live scrapes in CI — board scraping is manual/host attach only.

---

# Docs:

- [Docker setup](docs/Scraper_Docker_Setup.md) — Xvfb, compose services, report server, debugging
- [Build logic](docs/build_logic.md) — Dockerfile layers and entrypoint flow
- [LEGACY_CODE](LEGACY_CODE/) — original Indeed Cloudflare bypass approach
