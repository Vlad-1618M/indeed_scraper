# Docker & Build Logic

 ### Containerized job scraper setup tech-doc:
       - build flow:
       - entrypoint behavior:
       - compose architecture:
---

## Overview:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Host                                                                       │
│  ├── build/Dockerfile          →  Image build definition                    │
│  ├── build/entrypoint.sh       →  Runs before every container command       │
│  ├── build/build.sh            →  Convenience wrapper (build, auto, dice…)  │
│  ├── build/docker-compose.yml  →  Service definitions + default commands    │
│  └── build/docker-compose.override.example.yml  →  Cookie mounts (Indeed)   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Container (single image, multiple services)                                │
│  1. ENTRYPOINT starts Xvfb on :99                                           │
│  2. CMD runs (e.g. python src/main.py --auto --board dice ...)              │
│  3. SeleniumBase launches Chromium → scrapes job board                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Build Logic:

### Dockerfile Layer Order:

| Layer | Purpose | Caching |
|-------|---------|---------|
| `FROM python:3.13-slim-bookworm` | Base OS | — |
| `RUN apt-get install ...` | Chromium, Xvfb, browser deps, PyAutoGUI libs | Changes when package list changes |
| `COPY requirements.txt` | Python deps list | Rebuild from here if requirements change |
| `RUN pip install -r requirements.txt` | SeleniumBase, rich, etc. | Rebuild if requirements change |
| `COPY modules/ src/` | Application code | Rebuild if code changes |
| `COPY doc[s]/ ./docs/` | Documentation | Optional, fails gracefully if missing |
| `RUN mkdir -p artifacts/...` | Output dirs (json, logs, screenshots) | Static |
| `COPY build/entrypoint.sh` | Startup script | Rebuild if entrypoint changes |
| `ENTRYPOINT + CMD` | Default: show help | — |

**Why this order?**  
- Code changes often: 
- System and Python deps change rarely: 
- Putting `COPY requirements.txt` and `pip install` before `COPY modules/` avoids reinstalling dependencies on every code change:

### Build Choices:

- **Chromium over Chrome** — Better ARM64 (Apple Silicon) support and easier install in Debian.
- **Xvfb** — Chromium needs an X11 display. Xvfb provides a virtual one so the browser runs in headless containers.
- **`shm_size: 2gb`** — Chromium can hit shared-memory limits; 2GB avoids crashes in containers.
- **Multi-arch** — Same Dockerfile used on ARM64 and AMD64.

---

## Entrypoint Logic:

```
Container start
       │
       ▼
┌──────────────────┐
│ /entrypoint.sh   │
│ 1. Xvfb :99 &    │  ← Background virtual display
│ 2. export DISPLAY│  ← Chromium uses this
│ 3. sleep 2       │  ← Wait for Xvfb
│ 4. xdpyinfo check│  ← Verify display works
│ 5. trap cleanup  │  ← Kill Xvfb on exit
└──────────────────┘
       │
       ▼
┌──────────────────┐
│ exec "$@"        │  ← Run CMD (e.g. python src/main.py …)
└──────────────────┘
```

### Why Xvfb in Entrypoint (not CMD)?

- **Single responsibility** — Entrypoint only sets up the environment; CMD runs the app.
- **Consistent display** — Every container run gets Xvfb, no matter which service.
- **Cleanup** — `trap` ensures Xvfb is stopped when the container exits.
- **Failure handling** — If Xvfb fails, the entrypoint exits before the scraper runs.

---

## Compose Logic

### Service Model

| Service | Board | Auth | Use Case |
|---------|-------|------|----------|
| `scraper-auto` | Indeed | Cookies | Automated Indeed scrape |
| `scraper-interactive` | User choice | Depends | Board selection via prompts |
| `scraper-dice` | Dice | None | Automated Dice scrape |
| `scraper-glassdoor` | Glassdoor | None | Automated Glassdoor scrape |
| `scraper-scheduled` | All three | Indeed needs cookies | Cron / scheduled multi-board |
| `scraper-proxy` | Indeed | Cookies + proxy | Indeed with residential proxy |

### Volume Strategy

```
Host                          Container
────                          ─────────
artifacts/         ───────────►   /app/artifacts     (JSON, logs, screenshots)
.env               ───────────►   /app/.env:ro       (proxy, TZ - optional)
indeed_cookies.pkl     ───────►   /app/indeed_cookies.pkl:ro  (override only)
```

- **artifacts** — Shared across services; persisted on the host.
- **.env** — Environment variables; read-only in the container.
- **indeed_cookies.pkl** — Only for Indeed; added via `docker-compose.override.yml` (copied from `docker-compose.override.example.yml`).

### Why Override for Cookies?

- **Default flow works without cookies** — Dice and Glassdoor run without any extra setup.
- **No failing mounts** — If `indeed_cookies.pkl` is missing, Docker does not fail; main.py reports the cookie requirement.
- **Explicit opt-in** — Users enabling Indeed copy the override file once they have cookies.

---

## Build Script Logic:

### Flow:

```
./build.sh <cmd> [args]
       │
       ├── build      → docker-compose -f build/docker-compose.yml build
       ├── auto       → Check indeed_cookies.pkl → run scraper-auto
       ├── dice       → run scraper-dice (no check)
       ├── glassdoor  → run scraper-glassdoor (no check)
       ├── interactive→ run scraper-interactive
       ├── scheduled  → run scraper-scheduled
       ├── proxy      → Check PROXY_SERVER → run scraper-proxy
       ├── shell      → run scraper-auto /bin/bash
       ├── logs       → docker-compose logs -f
       └── clean      → docker-compose down --rmi all --volumes
```

### Paths

- `SCRIPT_DIR` — `build/` directory.
- `PROJECT_ROOT` — Parent of `build/` (repo root).
- `COMPOSE_FILE` — `build/docker-compose.yml` (from project root).

All commands run from `PROJECT_ROOT` so paths like `../artifacts` resolve correctly.

---

## Startup Sequence (Example)

```
$ ./build.sh dice "Python Developer" Remote 25

1. build.sh resolves PROJECT_ROOT, COMPOSE_FILE
2. check_docker()
3. cmd_dice("Python Developer", "Remote", 25)
4. docker-compose -f build/docker-compose.yml run --rm scraper-dice \
     python src/main.py --auto --board dice \
     --query "Python Developer" --location "Remote" --remote --days 7 --max 25
5. Compose builds image if needed, creates container
6. ENTRYPOINT ["/entrypoint.sh"] runs first
7. Xvfb starts, DISPLAY=:99, trap set
8. exec python src/main.py ...
9. main.py loads DiceScraper, runs search_jobs()
10. SeleniumBase opens Chromium, navigates to Dice
11. Jobs saved to artifacts/json/ (mounted from host)
12. Container exits, trap runs, Xvfb killed
```

---

## Quick Refs:

| File | Role |
|------|------|
| `build/Dockerfile` | Image definition, layer order, env vars |
| `build/entrypoint.sh` | Xvfb setup, DISPLAY, cleanup |
| `build/docker-compose.yml` | Scraper services, `report-server`, volumes, ports |
| `build/docker-compose.override.example.yml` | Cookie volume template |
| `build/build.sh` | CLI wrapper: build, scrape, `reports`, `serve` |

---

## Report server in Docker

The `report-server` compose service runs the same command as the host:

```bash
python3 modules/generate_job_reports.py --serve --host 0.0.0.0 --port 8765
```

- **No Xvfb** — uvicorn only; entrypoint still starts Xvfb but it is unused (harmless).
- **Port mapping** — `REPORT_PORT:8765` exposes the API to the host browser.
- **Shared artifacts** — `../artifacts:/app/artifacts` keeps DB/HTML/JSON in sync with host scrapes.
- **One-shot rebuild** — `docker-compose run --rm --no-deps report-server python3 modules/generate_job_reports.py --import-json`

---
