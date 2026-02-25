# Scraper:

## Preamble: - Scraper's Origin Story:

Like many of us in early 2025, I discovered that my Staff Software Engineering role had been “selected” as part of an ongoing workforce reduction—simply put, a layoff. Despite the work and meaning behind it, I had to lay off my entire team myself, and soon enough I found myself scrolling through *Indeed* endlessly—for days, then months, and eventually nearly a full year.

During this time, I began to notice what I initially thought was intentionally filtered behavior on *Indeed*. Logged-in sessions produced different results than non-authenticated or incognito sessions for the exact same search query. That discrepancy got me a bit curious, so I wrote a scraper dedicated to indeed.com, which I hoped others might find useful.

That original project was a deep dive into bypassing [Cloudflare](https://support.indeed.com/hc/en-us/articles/33465379855501-Troubleshooting-Cloudflare-Errors)'s formidable anti-bot measures. However, the digital landscape is always changing. This document outlines the evolution of that scraper, the architectural pivot it required, and its expansion into a multi-board tool.

> ___Yes, I’m fully aware that job boards will continue to modify and improve their scraping, bot, and automation detection—and frankly, they should.<br> This project is intended as a learning exercise and a practical tool for those who understand the challenges.<br> And If you can, I encourage you to make it better for everyone: <br>Good luck ;0)___

## Side Note:
### I was able to find refs online for indeed's so called  ___"a strategic shift toward a closed, identity-first ecosystem"___
- https://aimgroup.com/2025/11/26/indeed-ends-anonymous-alerts-tightening-its-grip-on-job-seekers/
![alt text](/docs/png_repo_screenshots/updates/image.png)
- https://www.indeed.com/legal
![legal](/docs/png_repo_screenshots/updates/indeed_policy.png)

- ___Bottom line: Indeed treats these changes as security and product decisions, not developer-facing API updates:___

---

## From Cloudflare Bypass attempt to a Cookie-First Strategy:

The initial repository version  was dedicated to a single, complex problem: - 
___Scraping Indeed while navigating Cloudflare's aggressive bot detection.___ <br>
The primary obstacle was the neverending "Additional Verification Required" page, which uses a multi-layered approach including:<br> 
* IP reputation: <br>
Browser fingerprinting, <br>
... as well as behavioral analysis to block automated scripts:

___
## The Original Approach: ( ___Legacy___ )

The initial solution involved testing multiple browser automation backends to find one that could reliably mimic human interaction. The most successful of these was **SeleniumBase in UC (Undetected-Chromedriver) Mode**, primarily for its ability to use **PyAutoGUI** to perform a real mouse click on the Cloudflare challenge checkbox. This method was effective for a time, allowing the scraper to navigate through paginated results. Other tools like Playwright and Camoufox were tested but failed against Cloudflare's advanced fingerprinting.

For historical context and a deeper understanding of the original challenge, the original [README.md](/LEGACY_CODE/README.md) detailing this approach is preserved in the [LEGACY_CODE](/LEGACY_CODE/) directory.

----
## NOW lets talk about - Enhanced APIs and a New Architecture:

Recently, Indeed enhanced its internal APIs and security, rendering the purely bypass-oriented approach unreliable for multi-page scraping. Unauthenticated sessions are now aggressively throttled and challenged, making consistent data extraction difficult and perhaps not worth the time.

___This necessitated a fundamental indeed specific architectural shift.___ <br>
* Instead of trying to defeat Cloudflare from a cold start on every run, the scraper now adopts a **cookie-first strategy**. <br>
It leverages the authentication and trust of a real, logged-in user session. <br>
While SeleniumBase UC Mode is still used to reduce automation fingerprints, the primary guarantee of access now comes from reusing a valid browser session's cookies.<br>

And while I was at it, I also added **Dice** and **Glassdoor** scrapers, each with its own architecture.<br> 
I don't personally favor either board, but since they still allow unauthenticated searches, they serve as handy cross-data references:

---

## Architecture and Designs:

* This project now contains three distinct scrapers: <br>
    - All built upon the **SeleniumBase UC Mode** framework
    - but adapted to the specific security and structural nuances of each job board:

___For example:___ 

| Scraper | Source | Authentication | Key Architectural Feature |
|---|---|---|---|
| **Indeed** | [indeed.com](https://www.indeed.com) | **Cookies Required** | **Cookie-First Strategy**: Reuses an authenticated sessions to bypass multi-page protection: |
| **Dice** | [dice.com](https://www.dice.com/jobs) | None | **Two-Phase Model**: Stateless initial search followed by an optional job details: |
| **Glassdoor** | [glassdoor.com](https://www.glassdoor.com) | None | **Scroll-Based & JS Extraction**: Handles and extracts data with in-page JavaScript for resilience: |

___
* Indeed Scraper **Module:** - [scraper_indeed.py](/modules/scraper_indeed.py)
    - **Design:** - Use cookie-first strategy is central at this point: 
    - Scraper assumes an already-authenticated session, with cookie collection handled by [get_cookies.py](/modules/get_cookies.py) module: <br>
        This helps scraping logic itself cleaner and more reliable. <br> 
        Jobs are normalized into a consistent .json artifact for downstream processing: <br>
    - **Requirements:** 
        - Cookies are mandatory for multi-page scraping:
        - To get cookies: 
            - Option 1: - run [main.py](/src/main.py) once which calls [get_cookies.py](/modules/get_cookies.py) if none found:<br>
                - It'll log in and generate the ___indeed_cookies.pkl___ file which lasts approximately 30 days:
                    ```bash
                        python src/main.py
                    ```
            - Option 2: call [/modules/get_cookies.py](/modules/get_cookies.py) directly:<br>
                - same deal - Follow the prompt - It'll log in and generate the ___indeed_cookies.pkl___ file which lasts approximately 30 days:
                    ```bash
                        python modules/get_cookies.py
                    ```
            - ![cookies](/docs/png_repo_screenshots/updates/indeed_cookies_prereqs.png)
            - ![cookies](/docs/png_repo_screenshots/updates/cookies_age.png)
---
* Dice Scraper - **Module:** - [scraper_dice.py](/modules/scraper_dice.py)<br>
    - **Design:** - This scraper is stateless by design since Dice does not require a login for the level of detail or targeted context: 
        - THis one is a two phase model: 
            - Phase 1 -  quick lookup - gathers all job listings from the search results pages (handling lazy-loading and pagination): 
            - Phase 2 - ( _optional_ ) - visits each job link url to extract a full description and JD requiered skills if available:<br> 
            .. helps to keep the default run fast plus reduces the risk of rate limiting wall:
            - ___.json___ output _Dice_ data structure: 
    
                ```json
                    {
                    "metadata": {
                        "source": "Dice.com",
                        "total_jobs": 25,
                        "scraped_at": "...",
                        "pages_scraped": 2,
                        "detailed_scraping_enabled": true,
                        "search_params": { "query": "...", "location": "..." }
                    },
                    "jobs": [
                        {
                        "query": "...",
                        "location": "...",
                        "title": "...",
                        "company": "...",
                        "job_location": "...",
                        "salary": "...",
                        "url": "...",
                        "job_id": "...",
                        "job_details": {
                            "skills": ["Python", "AWS", ...],
                            "full_description": "...",
                            "page_title": "..."
                        },
                        "detailed_scraped": true
                        }
                    ]
                    }
                ```

---
* Glassdoor Scraper - **Module:** [scraper_glassdoor.py](/modules/scraper_glassdoor.py)
    - **Design:** - Glassdoor scraper operates without authentication using a single-page, infinite-scroll model: <br>
        - To handle frequent HTML changes, it injects and executes a JavaScript snippet that walks the page's DOM to extract job data. 
        - ...help the scraper to adapt to minor frontend updates:
        - ___.json___ output _Indeed & Glassdoor_ data structure:<br>
            ```json 
                {
                "metadata": {
                    "total_jobs": 25,
                    "scraped_at": "...",
                    "scraped_at_readable": "...",
                    "search_params": { "query": "...", "location": "..." }
                },
                "jobs": [
                    {
                    "title": "...",
                    "company": "...",
                    "location": "...",
                    "salary": "...",
                    "url": "...",
                    "job_id": "...",
                    "posted_date": "...",
                    "job_type": "...",
                    "description": "..."
                    }
                ]
                }
                ```


---

## Cross-Scraper Field Mapping:

For downstream tools (e.g. `job_apply_filters.py`) that consume all three:

| Concept   | Indeed         | Dice         | Glassdoor    |
|----------|----------------|--------------|--------------|
| Query    | `search_query` | `query`      | `query`      |
| Location | `location`     | `job_location` | `job_location` |
| Job type | `job_type`     | `job_type`   | `job_type` (if extracted) |



## Init | How to:

Scraper's [main.py](/src/main.py) as the primary entry point can be run in interactive or automated mode:

**Interactive Mode:** - The script will prompt for the job board, search criteria, and other options:
```bash
python src/main.py
```
```bash
python src/main.py -h

usage: main.py [-h] [--auto] [--board {indeed,glassdoor,dice}] [--query QUERY] [--queries QUERIES]
               [--location LOCATION] [--remote] [--min-salary MIN_SALARY] [--max-salary MAX_SALARY]
               [--days {1,3,7,14}] [--max MAX] [--headless] [--incognito]
               [--window-size WINDOW_SIZE] [--proxy PROXY] [--proxy-user PROXY_USER]
               [--proxy-pass PROXY_PASS] [--output-dir OUTPUT_DIR] [--screenshots]
               [--screenshots-dir SCREENSHOTS_DIR]

Indeed Job Scraper - Cookie-Based Authentication with SeleniumBase UC Mode

options:
  -h, --help                         show this help message and exit

Operation Mode:
  --auto                             Run in automated mode (no interactive prompts) (default: False)

Search Parameters:
  --board {indeed,glassdoor,dice}    Job board to scrape (indeed, glassdoor, or dice) (default: indeed)
  --query QUERY                      Job search query (e.g., "DevOps Engineer") (default: None)
  --queries QUERIES                  Multiple queries comma-separated (e.g., "DevOps,SDET,SRE") (default: None)
  --location LOCATION                Job location (default: Remote)
  --remote                           Filter for remote jobs only (default: False)

Filters:
  --min-salary MIN_SALARY            Minimum salary (e.g., 150000) (default: None)
  --max-salary MAX_SALARY            Maximum salary (e.g., 200000) (default: None)
  --days {1,3,7,14}                  Posted within last N days (default: None)
  --max MAX                          Maximum results per search (default: 25)

Browser Settings:
  --headless                         Run browser in headless mode (no GUI) (default: False)
  --incognito                        Run in incognito mode (fresh session, no saved cookies) (default: False)
  --window-size WINDOW_SIZE          Window size: "maximized" or "WIDTHxHEIGHT" (e.g., "1280x720") (default: maximized)

Proxy Settings:
  --proxy PROXY                      Proxy server URL (e.g., "http://user:pass@proxy.example.com:8080") (default: None)
  --proxy-user PROXY_USER            Proxy username (if not included in proxy URL) (default: None)
  --proxy-pass PROXY_PASS            Proxy password (if not included in proxy URL) (default: None)

Output Settings:
  --output-dir OUTPUT_DIR            Output directory for JSON files (default: artifacts/json)
  --screenshots                      Capture screenshots of pages and job cards (default: False)
  --screenshots-dir SCREENSHOTS_DIR  Directory for screenshots (default: artifacts/screenshots)

    ======================================================================================================
                                *** CLI Examples Reference ***
    ======================================================================================================

    Interactive Mode - guided prompts:
        python main.py

    Basic Automated Search:
        python main.py --auto --query "DevOps Engineer"
        python main.py --auto --query "SDET" --location "Remote" --remote

    With Filters:
        python main.py --auto --query "Software Engineer" --location "Remote" --remote --min-salary 150000 --max-salary 200000 --days 7 --max 50

    Multiple Queries:
        python main.py --auto --queries "DevOps,SDET,SRE" --remote --days 7 --max 25

    With Screenshots:
        python main.py --auto --query "Backend Engineer" --remote --screenshots --max 25

    Headless Mode (servers/cron):
        python main.py --auto --query "Platform Engineer" --remote --headless --max 50

    With Proxy:
        python main.py --auto --query "Cloud Engineer" --proxy "http://user:pass@proxy.example.com:8080" --remote

    Custom Output Directory:
        python main.py --auto --query "DevOps" --output-dir "./results" --max 50

    Full Example:
        python main.py --auto --query "DevOps Engineer" --location "Remote" --remote --days 7 --max 50 --screenshots --output-dir "./artifacts/json"

    ======================================================================================================

```


**Automated Mode (Examples):**
```bash
# ___ scrape Indeed for a remote DevOps Engineer role (requires cookies):
python src/main.py --auto --board indeed --query "DevOps Engineer" --location "Remote" --remote

# ___ scrape Glassdoor for 25 remote Software Engineer roles:
python src/main.py --auto --board glassdoor --query "Software Engineer" --remote --max 25

# ___ scrape Indeed for multiple queries with screenshots enabled:
python src/main.py --auto --board indeed --queries "SDET,SRE" --remote --screenshots --max 50
```

### CLI Reference:

| Argument | Description | Example |
|---|---|---|
| `--auto` | Run in automated mode without prompts. | `--auto` |
| `--board` | Specify the job board: `indeed`, `glassdoor`. | `--board glassdoor` |
| `--query` | A single job search query. | `--query "DevOps"` |
| `--queries` | A comma-separated list of multiple queries. | `--queries "DevOps,SDET,SRE"` |
| `--location` | Search location (defaults to "Remote"). | `--location "New York"` |
| `--remote` | Apply the remote-only filter. | `--remote` |
| `--max` | Maximum number of results per query (default 25). | `--max 50` |
| `--headless` | Run the browser in headless mode. | `--headless` |
| `--screenshots` | Capture screenshots during the process. | `--screenshots` |
| `--proxy` | Use a proxy server for requests. | `--proxy "http://user:pass@host:8080"` |

---

## Technical Considerations:
### Proxies:

* For casual use, your local IP address is sufficient:<br> 
However, for sustained or high-volume scraping, Cloudflare will eventually notice and block your IP:<br> 
To avoid this, you can use a **residential proxy**, which routes your traffic through an IP address belonging to a real home internet connection, making your requests appear authentic.

- **Recommendation:** Services like **IPRoyal**, **Bright Data**, or **Smartproxy** offer residential proxies:
- **Usage:** Simply pass your proxy string via the `--proxy` argument.

```bash
python src/main.py --auto --proxy "http://user:pass@proxy.example.com:8080" --query "Search Name"
```

## Chromium's SSD Cache Bug:
### Running this setup will cause SSD space consumption due to Chromium Bug:
### I had to find it the hard way ...  
```bash
 sudo du -sh /private/var/* 2>/dev/null | sort -hr | head -n 50
```
![](/docs/png_repo_screenshots/chromium_bug_local.png)
* And sure enough it was reported already by others see --> [code sign clone bug](https://github.com/teamcapybara/capybara/issues/2795)
* All I needed was to search for it ... 🤦

![](/docs/png_repo_screenshots/chromium_bug.png)

### Keep an eye on your Mac's SSD size if you are a heavy selenium user:
* You can run shell command manually to identify where / what has consumed your disk space:
```bash
    sudo du -sh /System/Volumes/Data/* 2>/dev/null | sort -hr | head -n 50
    Password:
    
    461G /System/Volumes/Data/Users
    60G	 /System/Volumes/Data/private
    48G	 /System/Volumes/Data/Library
    28G	 /System/Volumes/Data/Applications
    11G	 /System/Volumes/Data/System
    9.7G	/System/Volumes/Data/usr
    7.6G	/System/Volumes/Data/opt
    1.5M	/System/Volumes/Data/MobileSoftwareUpdate
    1.0K	/System/Volumes/Data/home
    0B	/System/Volumes/Data/Volumes
    0B	/System/Volumes/Data/sw
    0B	/System/Volumes/Data/mnt
    0B	/System/Volumes/Data/cores
```

* and if this is a Chromim bug - this [chrome_cache_cleanup.sh](/maintance/chrome_cache_cleanup.sh) shell script should help: 
---

## Post-Scraping - Filtering and Viewing Jobs:

* All scraped jobs kept in .josn files in the _artifacts/json/_ path. <br>
    - Optional -  [job_apply_filters.py](/src/job_apply_filters.py) script helps to filter and view scraped results:
    - Works with the output from all three scrapers -  they share a normalized data schema:

```bash
# ____ preview filtered jobs in the console:
python src/job_apply_filters.py --read-only
```

```bash
# ___ filter by pay rate and open results in Firefox:
python src/job_apply_filters.py --payrate --brwsr firefox
```

```bash
# ___filter by job type:
python src/job_apply_filters.py --type "Part-time"
```

```bash
python src/job_apply_filters.py -h
usage: job_apply_filters.py [-h] [--brwsr {firefox,os}] [--read-only] [--payrate] [--type {Full-time,Part-time,Contract,Remote}]

Collected Job Applications & Filters:

options:
  -h, --help            show this help message and exit
  --brwsr {firefox,os}
  --read-only           no browser, just terminal stdout
  --payrate             do not show jobs without salary in J.D
  --type {Full-time,Part-time,Contract,Remote}
                        filter for job terms (e.g Part / Full Time, Contract or Remote)
```

---

### P.S: <br> ... lets talk about containerizing this thing: 
- *Docker containers are intentionally not covered here when it comes to network settigns and use of proxies*: 
- *While useful in many contexts, containerizing this setup increases resource overhead (notably GPU usage) and still relies on the local host’s ISP and network characteristics:*
- *Which offers limited benefit for this particular use case, HOWEVER:*
- *if you are anything like Me a __Docker Freak__  and like to put everything in container as oppose to some __python venv__ and such, <br> 
go ahead and try [Scraper_Docker_Setup.md](/docs/Scraper_Docker_Setup.md) which has everything you need for indeed scraper container support:* 
- see [build_logic.md](/docs/build_logic.md) for dev architectural info: 
---

# Thank you !
