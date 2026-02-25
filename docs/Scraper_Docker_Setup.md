
# Containerized Job Scraper Setup (Indeed, Dice, Glassdoor)

See [README.md](/README.md) for design notes and per-board details.

## Table of Contents:

1. [**Prerequisites**](#prerequisites)
2. [**Environment Configuration**](#environment-configuration)
4. [**Understanding Xvfb & Entrypoint**](#understanding-xvfb--entrypoint)
5. [**Build the Image**](#build-the-image)
6. [**Docker Compose Commands**](#docker-compose-commands)
7. [**Helper Script**](#helper-script)
8. [**Debugging Help**](#debugging-help)
9. [**Output Artifacts**](#output-artifacts)

---

## Prerequisites

| Software | Min Version | Check Command |
|----------|-------------|---------------|
| Docker | 20.10+ | `docker --version` |
| Docker Compose | 2.0+ | `docker-compose --version` |

---
## Environment Configuration:

### Cookie Override for Indeed:

Indeed requires cookies. Create them on your host (needs a display for login):

```bash
python modules/get_cookies.py
```

Then enable the cookie mount for Docker:

```bash
cp build/docker-compose.override.example.yml docker-compose.override.yml
```

Without this override, `scraper-auto` and `scraper-interactive` will fail with "NO COOKIES FOUND". Use `scraper-dice` or `scraper-glassdoor` for cookie-free runs.

### Step 1: Create `.env` file

```bash
cp .env.example .env
```

### Step 2: Edit `.env` file

```dotenv
# .env

# ___ Timezone:
TZ=America/New_York

# ___ Proxy Configuration | <-- RECOMMENDED for Cloudflare bypass:
PROXY_SERVER=http://us.smartproxy.com:10000
PROXY_USER=your_proxy_username
PROXY_PASS=your_proxy_password

# ___ Indeed Credentials | <-- Optional:
INDEED_EMAIL=
INDEED_PASSWORD=
```

**Why proxy?**  
Residential proxies help bypass Cloudflare's bot detection. Recommended providers:
- [IPRoyal](https://docs.iproyal.com/):
- [Smartproxy](https://help.decodo.com/docs/introduction):
- [Bright Data](https://docs.brightdata.com/introduction):

---

## Understanding Xvfb & Entrypoint:

### What is [Xvfb](https://www.x.org/archive/X11R7.7/doc/man/man1/Xvfb.1.xhtml) ?

**Xvfb** = X Virtual Framebuffer -> Creates a virtual display (fake screen) for GUI applications:

### Why do we need it?

**Problem:**  
- Chromium/Chrome requires an [X11 display server](https://www.x.org/releases/current/doc/libX11/libX11/libX11.html) to run:
- Even in "headless" mode, [SeleniumBase UC Mode](https://github.com/seleniumbase/SeleniumBase/blob/master/help_docs/uc_mode.md) needs a real display to avoid bot detection:
- Docker containers have no display by default:

**Solution:**  
- Xvfb provides a virtual display that Chromium thinks is real:
- This allows GUI browsers to run in headless Docker containers:

### How [entrypoint.sh](/build/entrypoint.sh) works

The entrypoint script runs **before** the scraper starts:

```bash
#!/bin/bash
# =============================================================================
#       *** Indeed Scraper - Docker Entrypoint ***
# =============================================================================
set -e

echo "[*] Starting Xvfb virtual display..."

# ___ Start Xvfb in background on display :99:
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

# ___ Export DISPLAY so apps know where to render | <-- CRITICAL:
export DISPLAY=:99

# ___ Wait for Xvfb to initialize:
sleep 2

# ___ Verify Xvfb started successfully:
if xdpyinfo -display :99 > /dev/null 2>&1; then
    echo "[+] Virtual display ready on :99"
else
    echo "[!] ERROR: Xvfb failed to start"
    kill $XVFB_PID 2>/dev/null || true
    exit 1
fi

# ___ Cleanup function | <-- kills Xvfb when container stops:
cleanup() {
    echo "[*] Shutting down Xvfb..."
    kill $XVFB_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ___ Run the actual command | <-- your scraper:
exec "$@"
```

**Logic:**
- `Xvfb :99` -> Starts virtual display on port :99:
- `-screen 0 1920x1080x24` -> Resolution and color depth:
- `export DISPLAY=:99` -> Tells Chromium where to render (THIS IS CRITICAL):
- `&` -> Runs Xvfb in background:
- `trap cleanup` -> Ensures Xvfb is killed when container exits:
- `exec "$@"` -> Runs python scraper cli commands:

**Without this:**  
Chromium crashes with errors like:

```bash
selenium.common.exceptions.WebDriverException: Message: unknown error: Chrome failed to start
ERROR:browser_main_loop.cc(1344)] Unable to open X display
```

### Why not use `xvfb-run` wrapperor why it did not work in this case ?

**Problem with `xvfb-run`:**
- Can hang indefinitely waiting for display:
- Inconsistent behavior in containers:
- Poor error reporting:

**Current approach for this particular use case:**
- Explicit control over Xvfb lifecycle:
- Clear error messages:
- Reliable cleanup:

---

## Build the Image:

### Option 1: [Docker Compose](/build/docker-compose.yml)

```bash
# ___ From project root:
docker-compose -f build/docker-compose.yml build
```

### Option 2: [Helper Script](/build/build.sh)

```bash
cd build/
./build/build.sh build
```
![build/build.sh build](/docs/png_repo_screenshots/build.sh_build.png)
**Build time:** ~5-10 minutes on first run (downloads Chromium + dependencies)

---

## Docker-Compose Commands Refs/Help:

### Build

>- Build image
```bash
docker-compose -f build/docker-compose.yml build
```
---
### Automated Scraper:
---
>- Default search | <-- DevOps Engineer, Remote, last 7 days, max 25:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-auto
```
---
>- Custom search:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-auto \
    python src/main.py --auto --board indeed \
    --query "Python Developer" --location "Remote" --max 50
```
---
>- With screenshots:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-auto \
    python src/main.py --auto --board indeed \
    --query "DevOps Engineer" --location "Remote" --remote \
    --max 25 --screenshots
```
---
>- With salary filter + days old + screenshots:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-auto \
    python src/main.py --auto --board indeed \
    --query "Sr Software Engineer" --location "Remote" --remote --min-salary 150000 --max-salary 250000 --days 7 --max 50 --screenshots
```
![auto_scraper](/docs/png_repo_screenshots/auto_scraper.png)
---
>- Salary + screenshots:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-auto \
    python src/main.py --auto --board indeed \
    --query "Sr.Python Developer" --location "Remote" --remote \
    --min-salary 150000 --max-salary 250000 \
    --days 7 --max 50 --screenshots
```
---
>- Remote only + recent posts:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-auto \
    python src/main.py --auto --board indeed \
    --query "Platform Engineer" --location "Remote" --remote \
    --days 3 --max 25
```
---
### Interactive Mode:
>- TTY mode with prompts:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-interactive
```

### Scheduled Scrapes:
>- Multiple searches in sequence | <-- good for cron:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-scheduled
```

### Glassdoor Scraper (no cookies):
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-glassdoor
```

### Dice Scraper (no cookies):
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-dice
```

### With Proxy:
>- Requires PROXY variables in .env:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-proxy
```

### Shell Access:
>- Open bash shell for debugging:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-auto /bin/bash
```

### Cleanup:
>- Remove all containers + images:
```bash
docker-compose -f build/docker-compose.yml down --rmi all --volumes
```

---

## Helper Script:

```
build/build.sh
```

### How To: 

```bash
./build.sh <command> [args]
```

### Commands

| Command | Description |
|---------|-------------|
| _build_ | Build Docker image |
| _auto [query] [location] [max]_ | Indeed automated (needs cookies) |
| _dice [query] [location] [max]_ | Dice automated (no cookies) |
| _glassdoor [query] [location] [max]_ | Glassdoor automated (no cookies) |
| _interactive_ | Interactive mode (board selection) |
| _scheduled_ | Multi-board scheduled scrape |
| _proxy_ | Indeed with proxy (needs .env) |
| _shell_ | Open bash shell in container |
| _logs_ | View container logs |
| _clean_ | Remove containers + images |
| _help_ | Show help |

### Examples:
>- Build image:
```bash
./build.sh build
```
>- Default search:
```bash
./build.sh auto
```
>- Custom search:
```bash
./build.sh auto "Python Developer" "Remote" 50
```
>- Interactive mode:
```bash
./build.sh interactive
```
>- Debug shell:
```bash
./build.sh shell
```
>- View logs:
```bash
./build.sh logs
```
>- Cleanup:
```bash
./build.sh clean
```
---

## Debugging Help:

### Shell Access
>- Open bash shell in container:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-auto /bin/bash
```

### Test Xvfb Manually:
>- Enter container without entrypoint | <-- bypasses entrypoint.sh:
```bash
docker-compose -f build/docker-compose.yml run --rm --entrypoint="" scraper-auto /bin/bash
```
>- Inside container + Start Xvfb manually:
```bash
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99
sleep 2
```

>- Test display is available:
```bash
xdpyinfo -display :99
```
>- Run scraper:
```bash
python src/main.py --auto --board indeed --query "DevOps Engineer" --location "Remote" --max 5
```

### Xvfb Installation Check: 
>- Verify xvfb-run exists:
```bash
docker-compose -f build/docker-compose.yml run --rm --entrypoint="" scraper-auto which xvfb-run
# Output: /usr/bin/xvfb-run
```

>- Test xvfb-run wrapper:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-auto /bin/bash -c "xvfb-run --auto-servernum echo 'xvfb works'"
# Output: xvfb works
```

### View Container Logs:
>- Tail logs in real-time:
```bash
docker-compose -f build/docker-compose.yml logs -f scraper-auto
```
>- ... or use helper:
```bash
./build.sh logs
```

### Check DISPLAY Variable:

>- Verify DISPLAY is set correctly:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-auto /bin/bash -c 'echo $DISPLAY'
# Output: :99
```

### Save Debug Screenshot:

>- Run with screenshots enabled:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-auto python src/main.py --auto --board indeed --query "test" --location "Remote" --max 5 --screenshots

# output check
ls -la artifacts/screenshots/
```

### Common Issues:

#### Issue: Chrome crashes with `WebDriverException`:

* Error:

```bash
selenium.common.exceptions.WebDriverException: Message: unknown error: Chrome failed to start
```

> **Cause:** Shared memory too small:<br>
> **Solution:** Already configured in `docker-compose.yml`:

>- Shared memory for Chromium:
```yaml
shm_size: '2gb'
```
___If still fails, check Docker host has sufficient RAM (4GB+ available)___

#### Issue: Xvfb hangs or container won't start:

>**Cause:** `xvfb-run` wrapper issues:<br>
>**Solution:** We use direct Xvfb invocation in `entrypoint.sh` (not `xvfb-run`)

>- Verify entrypoint is correct:
>   - Check entrypoint.sh starts Xvfb directly:
```bash
cat build/entrypoint.sh | grep "Xvfb :99"
# Should show: Xvfb :99 -screen 0 1920x1080x24 ...
```

#### Issue: `DISPLAY` not set / Chrome can't find display:

*Error:
```bash
ERROR:browser_main_loop.cc(1344)] Unable to open X display
```

>**Cause:** `export DISPLAY=:99` missing in entrypoint:<br>
>- **Check:**
>   - Verify entrypoint exports DISPLAY:

```bash
cat build/entrypoint.sh | grep "export DISPLAY"
# Should show: export DISPLAY=:99
```

**Test manually:**

```bash
docker-compose -f build/docker-compose.yml run --rm --entrypoint="" scraper-auto /bin/bash

# Inside container:
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99      # <-- THIS LINE IS CRITICAL:
sleep 2
xdpyinfo -display :99   # <-- Should show display info:
```

#### Issue: Cloudflare still blocking:

>**Cause:** IP reputation low, no proxy:<br>
>- **Solution:**
>   - Add residential proxy to `.env`
>   - Use `scraper-proxy` service:

```bash
docker-compose -f build/docker-compose.yml run --rm scraper-proxy
```

>   - Reduce scrape frequency:

---
* #### Issue: Build fails with `playwright install` error:

>**Cause:** Playwright browser download failed (network issue):<br>
>- **Solution:** Rebuild with `--no-cache`:
```bash
docker-compose -f build/docker-compose.yml build --no-cache
```

>- Or edit [Dockerfile](/build/Dockerfile) line 93 to remove ___true___:

```dockerfile
# Before:
RUN playwright install chromium --with-deps || true

# After | <-- will fail build if playwright fails:
RUN playwright install chromium --with-deps
```

---
## Output Artifacts:

All artifacts are saved to `artifacts/` (mounted as volume):
![Artifacts](/docs/png_repo_screenshots/Artifacts.png)

**Access from host:**

```bash
# ___ View JSON output:
ls -la artifacts/json/
cat artifacts/json/*.json | jq .

# ___ View logs:
tail -f artifacts/logs/scraper_*.log

# ___ View screenshots:
open artifacts/screenshots/pages/*.png
```
![view](/docs/png_repo_screenshots/View_Artifacts.png)
---

## Cron Job Examples

### Daily Scrape:
>- Add to crontab | <-- crontab -e:
```bash
0 9 * * * cd /path/to/indeed_scraper && docker-compose -f build/docker-compose.yml run --rm scraper-auto >> /var/log/indeed-scraper.log 2>&1
```

### Multiple Searches Every 6 Hours:
>- Run scheduled service:
```bash
0 */6 * * * cd /path/to/indeed_scraper && docker-compose -f build/docker-compose.yml run --rm scraper-scheduled
```

### Weekly High-Salary Search

>- Every Monday at 8am:
```bash
0 8 * * 1 cd /path/to/indeed_scraper && docker-compose -f build/docker-compose.yml run --rm scraper-auto python src/main.py --auto --board indeed --query "Senior DevOps" --min-salary 180000 --max-salary 250000 --remote --days 7
```

---

# Advanced Configuration:

### Resource Limits:

Edit `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      memory: 4G       # ___ Max RAM
    reservations:
      memory: 2G       # ___ Min reserved RAM
```

### Timezone:

```bash
# ___ In .env:
TZ=America/Los_Angeles

# ___ Or override at runtime:
docker-compose -f build/docker-compose.yml run --rm -e TZ=Europe/London scraper-auto
```

### Custom Display Number:
>- Override DISPLAY variable:
```bash
docker-compose -f build/docker-compose.yml run --rm -e DISPLAY=:100 scraper-auto
```
* __NOTE:__  - If changing display number, also update Xvfb startup in [entrypoint.sh](/build/entrypoint.sh)

---

## Quick Reference:

### Build & Run:

>- Build:
```bash
docker-compose -f build/docker-compose.yml build
```
* __NOTE:__
* on the `docker-compose -f build/docker-compose.yml build` rerans __if__ error below shows up:<br>

```bash
[+] Building 0.0s (0/1)
 => [internal] load local bake definitions                                                                                                                                           0.0s
failed to execute bake: read |0: file already closed 
```
* Check your root path and remove `.env` dir created by previous build, then recall command:

![rerun](/docs/png_repo_screenshots/docker-compose_rerun.png)

>- Run default:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-auto
```
>- Run custom:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-auto python src/main.py --auto --board indeed --query "Your Query" --location "Remote" --max 50
```

### Debug:

>- Shell:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-auto /bin/bash
```
>- Check Xvfb:
```bash
docker-compose -f build/docker-compose.yml run --rm scraper-auto /bin/bash -c 'xdpyinfo -display :99'
```
>- Test scraper:
```bash
docker-compose -f build/docker-compose.yml run --rm --entrypoint="" scraper-auto /bin/bash
```

### Cleanup:
>- Remove containers:
```bash
docker-compose -f build/docker-compose.yml down
```
>- Remove everything:
```bash
docker-compose -f build/docker-compose.yml down --rmi all --volumes
```
![cleanup](/docs/png_repo_screenshots/cleanup_images.png)
---

## Summary:

**Key files:**
- [build/Dockerfile](/build/Dockerfile) -> Container image definition
- [build/docker-compose.yml](/build/docker-compose.yml) -> Service orchestration  
- [build/entrypoint.sh](/build/entrypoint.sh) -> Xvfb startup + DISPLAY export
- [build/build.sh](/build/build.sh) -> Helper commands
- __.env__ -> Environment variables created from [.env.example](/.env.example):

**Xvfb flow:**
>1. Container starts -> entrypoint.sh runs
>2. Xvfb starts on display :99
>3. DISPLAY=:99 exported
>4. Verification with xdpyinfo
>5. Cleanup trap set
>6. Your scraper command runs
>7. On exit -> Xvfb killed

**For quick start:**
```bash
docker-compose -f build/docker-compose.yml build
docker-compose -f build/docker-compose.yml run --rm scraper-auto
```

**For debugging:**
```bash
./build/build.sh shell 
```
![debug](/docs/png_repo_screenshots/shell_in_container.png)
---