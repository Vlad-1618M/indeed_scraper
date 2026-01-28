# Preamble:

#### Like many of us in early 2025, I discovered that my Staff Software Engineering role had been “selected” as part of an ongoing workforce reduction — simply put, a layoff.<br> Despite the work and meaning behind it, I had to lay off my entire team myself, and soon enough I found myself scrolling through _Indeed_ endlessly — for days, then months, and eventually nearly a full year.<br>

#### During this time, I began to notice what I initially thought was intentionally filtered behavior on _Indeed_.<br> Presumably, this is designed to customize the job search experience and improve results. However, at least in my case, I started seeing patterns that appeared to limit or alter my search results and its existing filters.<br>

* For example:
    - Logged-in sessions produced _X_ results:  
    - Non-authenticated sessions produced _Y_ results:
    - Incognito sessions produced _Z_ results:

#### On the surface, everything looked correct and aligned with the search criteria.<br> However, it was odd that identical search queries on _Indeed_ produced different results — assuming the same location, search criteria, and IP address were used.<br> I got curios and wrote this scraper specifically dedicated to [indeed.com](https://www.indeed.com), built from scratch:<br>
I hope some of you may find it useful one day.<br>
> ___Yes, I’m fully aware that _Indeed_ will continue to modify and improve its scraping, bot, and automation detection — and frankly, they should.<br>
That said, if you’ve encountered similar challenges before and know what you’re doing, it won’t take you long to understand the approach ;0)<br>
If this is new to you, this project can serve as a solid learning exercise or a promising starting point — and potentially time well saved:<br>
In the meantime, enjoy it and if you can, please, make it better for everyone:<br>
Good luck ;0)___
---
# Indeed Scraping with Bypassing Cloudflare detections:
Readme is for anyone looking to scrape [indeed.com](https://www.indeed.com): <br> It explains the primary obstacle such as _Cloudflare_ anti scraping mechanism: <br>Details the different scraping tools inside: <br> Helps tp understand how proxy servers work, and gives a final, definitive recommendations for reliable and potentially long term data extraction methods:

## Chapter 1: The Core Problem - Understanding _Cloudflare_:
* At its heart, _scraping_ as a concept is pretty simple: <br>
An automated script visits a website and copies information. <br> The _problem_ is that the websites like [indeed.com](https://www.indeed.com) don't *want* to be scraped by bots.<br> They employ security services to block them, and the most formidable of these is - [**Cloudflare**](https://www.cloudflare.com):

![start](/docs/png_repo_screenshots/runtime_0.png)

* Cloudflare acts as a gatekeeper, inspecting every visitor to determine if they are a real human or a bot. <br> If it detects a bot, it presents the infamous _"Additional Verification Required"_ page, effectively stopping the scraper in its tracks.

### How Cloudflare Detects Bots:

Cloudflare uses a sophisticated, multi-layered approach to detection. <br>So the scraper must be able, somehow, _bypass_ all of these checks:

1.  **IP Reputation:** The most basic check. 
    * If your requests come from a known datacenter IP address (like AWS, Google Cloud, or a VPN), you are immediately suspicious. 
    * Real users have **residential IPs** from Internet Service Providers (ISPs) like Comcast, At&t or Verizon:

2.  **Browser Fingerprinting:** Cloudflare inspects your browser for tell-tale signs of automation. 
    * These include:
        * _navigator.webdriver_: - This flag is `navigator.webdriver=True` in most standard automation browsers:
        * **Headless Mode:** Running a browser without a visible UI is a dead giveaway:
        * **Browser Properties:** Inconsistencies in screen resolution, plugins, fonts, and language settings can reveal a bot:

3.  **Behavioral Analysis:** Cloudflare watches *how* you interact with the page. _Bots are often clumsy_:
    *   **Mouse Movements:** Instant, linear mouse movements are robotic. Humans move the mouse in slight curves:
    *   **Click Patterns:** Clicking the exact center of a button every time is unnatural:
    *   **Typing Speed:** Typing too fast or with perfect consistency is a red flag:

4.  **TLS/HTTP2 Fingerprinting:** The very first connection your scraper makes has a unique technical signature (a "fingerprint"). 
    * Cloudflare maintains a massive database of these fingerprints and can block known automation libraries before they even load the page:

5.  **Interactive Challenges:** If all else fails, Cloudflare presents the "Verify you are human" checkbox (known as **Turnstile** or **reCAPTCHA**)    
    * This is the final point, designed to be clicked by a human, not a script:

---

<!-- ## Chapter 2: The ToolBox - What Scraping Tools can be used to get through: -->
## Chapter 2: The Toolbox — Scraping Backends:
* After researching, testing, and experimenting, I've found four different scraping backends to determine the most effective tool for the job:
    * __I’ll be upfront__ - I am not a fan of _Selenium_ at all and I would typically avoid it completely in any professional setting at all costs: 
* However, I must admit that _SeleniumBase_ proved to be the best fit for this use case: 
    * Primarily due to its use of _PyAutoGUI_ to simulate real user interactions: 
    * For those who have been around long enough may recognize _PyAutoGUI_ lib from the earlier days of UX automation techniques used in sales and product demonstrations:

## Here is a high-level comparison:

| Scraper Backend | Cloudflare Bypass | Stability | Recommendation |
| :--- | :--- | :--- | :--- |
| [**SeleniumBase (UC Mode)**](https://seleniumbase.io/): | **Excellent** | **High** | **Strongly recommended at the time of this document writing**: |
| [Playwright](https://playwright.dev/python/docs/intro): | Poor | High | Suitable for unprotected sites, but unreliable against Cloudflare: |
| [Camoufox](https://camoufox.com/): | Failed | Very Low | Experimental _C++_ based lib, yet buggy and unstable: |
|          |        |          | I kept it here for reference — at the time of writing, _Cloudflare_ effectively blocks this approach: |
|          |        |          | I hope _Camoufox_ dev team can make it work: 
|          |        |          | ...  the Idea is great and alsmot perfect, just did not work for this use case: |
| [Standard Selenium](https://www.selenium.dev/documentation/): | Very Poor | High | Not an option at all: Fails almost immediately. Included only for completeness: |

### 1. SeleniumBase UC Mode:
* **SeleniumBase** - is a framework built on top of Selenium that adds some extra features, including special _"Undetected-Chromedriver"_ or <br> _UC_ mode designed specifically to evade bot detections for one:

* **How does it in code:** - [seleniumbase_scraper.py](/modules/seleniumbase_scraper.py) inits the scraper with _uc=True_:

```python
from seleniumbase import SB
with SB(uc=True, headless=self.headless, ...) as self.sb:
    # SB() in UC mode patches the browser:
    self.sb.uc_open_with_reconnect(url, reconnect_time=5)
```
```python
try:
            print("\n[*] Attempting Indeed login...")
            self.sb.uc_open_with_reconnect("https://secure.indeed.com/auth", reconnect_time=4)
```     
* **Why THis one Worked**: 
    * The key is how it handles the Cloudflare checkbox. 
    * Instead of trying to use JavaScript to click it (which is easily detected), it uses a library called [**PyAutoGUI**](https://pyautogui.readthedocs.io/en/latest/) to take control of your *actual mouse cursor* and perform a *real click* on the screen. 
    * Succesfully mimics human click actions: 
```python
    def _handle_cloudflare(self):
            """ Handle Cloudflare challenge using SeleniumBase UC Mode.
                Returns: bool: True if challenge was detected and handled """
            if not self._is_cloudflare_challenge():
                return False
        
```

```python
    def _is_cloudflare_challenge(self):
            """Check if current page is Cloudflare challenge."""
            try:
                title = self.sb.get_title().lower()
                page_source = self.sb.get_page_source().lower()
                
                indicators = [
                    'just a moment' in title,
                    'cloudflare' in title,
                    'verify you are human' in page_source,
                    'additional verification required' in page_source,
                    'checking your browser' in page_source,
                    'challenges.cloudflare.com' in page_source,
                    'cf-turnstile' in page_source,
                ]
                
                return any(indicators)
            except:
                return False
```

- **Pros:** The only method that reliably solved the Cloudflare challenge on pagination.
- **Cons:** Requires the browser window to be visible for the mouse click to work, so no headless calls.

### 2. Playwright:
* Modern fast browser automation library from Microsoft - originally comes from _Puppeteer_ by Google / Chrome DevTools team.  
* Automation ( e.g SDET) and Devs like to use this one, primerly due to its support and clean APIs:

* **How does it in code:** - [playwright_scraper.py](/modules/playwright_scraper.py) start the browser and apply stealth settings:

```python
def _start_browser(self):
        """Start Playwright browser with anti-detection."""
        print("[*] Starting Playwright browser...")
        self.playwright = sync_playwright().start()
        
        # Browser launch options
        launch_options = {
            'headless': self.headless,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        }
```

* **Why it Did Not Work:** 
    * Playwright is excellent for scraping unprotected sites:
    * However, it was consistently blocked by Cloudflare when navigating to the second page: 
    * I tried to replicate the _PyAutoGUI_ mouse-clicking logic, but it was not as reliable as SeleniumBase's tested implementation: 
    * Cloudflare's fingerprinting is simply too advanced for the standard Playwright stealth plugins at thsi time: 

- **Pros:** Fast, modern, great for general purpose scraping:
- **Cons:** Fails against advanced bot detectors like Cloudflare's:

### 3. Camoufox:
* An anti-detect browser based on Firefox that promises to spoof your browser fingerprint to look like a different OS or browser:

* **Why this one Failed** 
    * Camoufox was a complete failure. It was plagued by bugs that made it unusable:
        - 1.  **Version Mismatches:** - Python package and the browser binary it downloaded were out of sync, causing constant crashes:
        - 2.  **Critical Rendering Bugs:** - It had a font-rendering issue that turned all web page text into garbled symbols:
        - 3.  **Poor Maintenance:** - The tool did not properly clean up old files, making it difficult to debug or downgrade:

- **Pros:** None. The concept is good, but the execution is flawed:
- **Cons:** Unstable, buggy, and abandoned at this time:
- see:
    - [install_camoufox.sh](/maintance/install_camoufox.sh)
    - [camoufox_cleanup.sh](/maintance/camoufox_cleanup.sh)

### 4. Standard Selenium:

* The original, classic browser automation tool:
* **Why Ii always fails on sites liek Indeed** 
* Standard Selenium is instantly detected. 
* It sets a _`navigator.webdriver`_ flag in the browser to _`true`_, which is like wearing a sign that says "I AM A BOT": 
* It is not a good option for any modern/protected website, hence why I dont like it and woudl not use it, but still had to try tobe sure: 

---

## Chapter 3: Proxies - Optional:
* Even with the _"best"_ scraper, you still have one final vulnerability: your own **IP address**. 
* If you send hundreds of requests from the same IP, Cloudflare will notice the unusual activity and block you. This is where proxies come in.

### What is a Proxy Server ?
* Think of a proxy as a **middleman**. 
* Instead of your scraper connecting directly to a web ( in this case) [indeed.com](https://www.indeed.com) 
* it connects to a proxy server, which then forwards the request to Indeed.com on your behalf:

>- **Standard or TYpicall Connection:**
>   - `Your Computer --> Indeed.com`
>- **Proxy Connection:**
>   - `Your Computer --> Proxy Server --> Indeed.com`

* To Indeed.com, it looks like the visitor is the Proxy Server since an actaul  IP address is hidden due to network redirects:

## Types of Proxies & Why it Matters:
* Not all proxies are created equal. The type of IP address the proxy server has is critical:
* For Example:
    - **Datacenter Proxies:** 
        - These are IP addresses owned by cloud hosting providers such as _AWS_, _Google Cloud_, or _DigitalOcean_: 
        - They are relativly cheap and plentiful, however, _Cloudflare_ knows these IP ranges and is highly suspicious of them. 
        - **They are not effective for bypassing Cloudflare.**
    - **Residential Proxies:** 
        - These are IP addresses belonging to real home internet connections from ISPs like Comcast, AT&T or Verizon: 
        - Since they look like a real users - they are trusted by Cloudflare.
        - One can say that ISP based proxies are the **gold standard for scraping**:

### How to Get and Use a Residential Proxy:
* Normally there is no need to set up your own server - You simply subscribe to a service:

#### Possible Choices / Variants out there:
1.  **Choose a Provider:** Sign up for a residential proxy provider. Here are some recommendations:

    | Provider | Approx. Cost (Pay-as-you-go) | Reason to select one: |
    | :--- | :--- | :--- |
    | [**IPRoyal**](https://iproyal.com/) | ~$7 / GB | Ok balance between the price and performance: |
    | [**Bright Data**](https://brightdata.com/) | ~$15 / GB | Portraits itself as industry leader, reliable but more expensive:|
    | [**Smartproxy**](https://www.smartproxy.org/) | ~$8.5 / GB | Another popular option:|

2.  **Get Credentials:** 
    * After signing up, go to your user dashboard. 
    * The provider will give you a **proxy string** that contains your username, password, and the server address:

3.  **Enter it into the Scraper:** 
    * When you run the scraper, it will ask for this information ( _optional argument call_ ):

    ```
      ~/DEV/indeed_scraper ❯ py src/main.py
    ================================================================================
    Indeed Job Scraper - Interactive Mode
    ================================================================================

    Scraper options:
    1. SeleniumBase UC Mode (recommended - best for Cloudflare bypass)
    2. Camoufox (experimental)
    3. Playwright
    4. Selenium
    Choice (1/2/3/4, default=1): 1

    Login? (y/n): n
    Run in incognito mode? (y/n): y

    Window size options:
    1. Maximized (full screen)
    2. Custom size (e.g., 1280x720)
    Choice (1 or 2, default=1): 1
    Capture screenshots? (y/n): y
    Use proxy? (y/n): y
    Proxy server (e.g., http://proxy.example.com:8080): 
    ```
    * Paste the **full proxy string** they gave you. 
    * It will look something like this: _`http://<username>:<password>@<proxy_provider_address>:<port>`_
        * **Real-world Example (for Bright Data):** _`http://brd-customer-hl_a1b2c3d4-zone-residential:z5y6x7w8v9@brd.superproxy.io:22225`_

And that shoudl do it: The scraper will automatically route all its traffic through the residential proxy server:

---
## Chapter 4: Final Recommendation:

* After extensive testing, it’s clear that reliable, long-term scraping of Indeed.com is achievable, but remains subject to continuous platform changes. <br>For this reason, I’ve intentionally retained all four scraping options in the project to preserve flexibility as conditions evolve.

### **Step 1: Use the SeleniumBase Scraper**
- This is currently the only backend that consistently succeeds against Indeed’s interactive Cloudflare challenges, largely due to its real mouse and keyboard interaction model:
- See -> [Demo](https://www.youtube.com/watch?v=2uSVOocKWGs):

```bash
# --> auto mode SeleniumBase call:
python src/main.py --auto --scraper seleniumbase --query "Software Engineer"
python src/main.py --auto --scraper seleniumbase --query "DevOps Engineer"
```

```bash
# --> auto mode SeleniumBase call - real example:
py src/main.py --auto --scraper seleniumbase --query "Software Engineer"
================================================================================
Indeed Job Scraper - Automated Mode
================================================================================
Started: January 19, 2026 at 07:16 PM
[*] Using SeleniumBase UC Mode
[*] Starting SeleniumBase UC Mode browser...
[+] SeleniumBase UC Mode browser started

================================================================================
Searching: Software Engineer
================================================================================

[*] Page 1: https://www.indeed.com/jobs?q=Software+Engineer&l=Remote
[*] Found 16 job cards
  [1] Software Engineer-Entry Level | https://www.indeed.com/viewjob?jk=e270ee0b848896c1
  [2] Software Engineer Level 1 | https://www.indeed.com/viewjob?jk=b5fd5ce235d453a0
  [3] Software Engineer (entry) | https://www.indeed.com/viewjob?jk=2292b5587382bf2f
  [4] Associate AI Software Engineer | https://www.indeed.com/viewjob?jk=1ac2ae991a3a1bf9
  [5] Software Engineer | https://www.indeed.com/viewjob?jk=04349ef92dd67603
  [6] Software Engineer | https://www.indeed.com/viewjob?jk=fedcba9876543210
  [7] Full-Stack Software Engineer | https://www.indeed.com/viewjob?jk=89f452a2cb15092b
  [8] Software Engineer, Frontend | https://www.indeed.com/viewjob?jk=4afd31e7fd195c88
  [9] Mid-Level Software Engineer | https://www.indeed.com/viewjob?jk=ecb78dba239ff4ae
  [10] Software Engineer - Production Support | https://www.indeed.com/viewjob?jk=331c25f90952cdd1
  [11] Software Engineer | https://www.indeed.com/viewjob?jk=d9441771c89a6db0
  [12] Software Engineer | https://www.indeed.com/viewjob?jk=60be1bc3c74e1b1a
  [13] Software Engineer | https://www.indeed.com/viewjob?jk=5becccf92540cc6a
  [14] Software Engineer | https://www.indeed.com/viewjob?jk=43184a1b34556735
  [15] Software Engineer | https://www.indeed.com/viewjob?jk=94c839990fa22ffd
  [16] Junior Software Engineer | https://www.indeed.com/viewjob?jk=797a5f4737568318
[*] Reconnecting before next page...

[*] Page 2: https://www.indeed.com/jobs?q=Software+Engineer&l=Remote&start=10
[*] Found 16 job cards
  [17] Junior Application Developer | https://www.indeed.com/viewjob?jk=e31c1b1b4ed2dd1a
  [18] Fullstack Software Engineer | https://www.indeed.com/viewjob?jk=18f69febed88dff3
  [19] Applied Software Engineer II | https://www.indeed.com/viewjob?jk=3913de0060f17e8e
  [20] Software Engineer | https://www.indeed.com/viewjob?jk=27b1c182c0c5b609
  [21] Python & JavaScript Web Scraper | https://www.indeed.com/viewjob?jk=a4402c63b9bd77a6
  [22] Senior Software Engineer | https://www.indeed.com/viewjob?jk=38363ed6da841130
  [23] Unity Software Engineer | https://www.indeed.com/viewjob?jk=c98fa7907955475a
  [24] Frontend Software Engineer 2 | https://www.indeed.com/viewjob?jk=0e5c1a7785091c2a
  [25] Frontend Software Engineer 2 | https://www.indeed.com/viewjob?jk=890abcdef0123456
[+] Found 25 jobs for 'Software Engineer'

✓ Saved 25 jobs to: /Users/vtool/DEV/indeed_scraper/artifacts/json/software_engineer_20260119_191646.json

================================================================================
Summary
================================================================================
Total queries: 1
Total jobs scraped: 25
Started: January 19, 2026 at 07:16 PM
Completed: January 19, 2026 at 07:16 PM
Duration: 0m 34s
[*] SeleniumBase browser closed

[+] Browser closed
```
### **Step 2: Use a Residential Proxy** (when applicable):
- Optional for casual or personal use:
- Recommended for sustained or higher-volume use cases, where avoiding IP-based blocking becomes essential:
- This typically requires a third-party provider such as _IPRoyal_, _Smartproxy_, _Bright Data_, or another comparable service available at the time of writing:

```python
# --> auto mode with a residential proxy call:
python src/main.py --auto --scraper seleniumbase --proxy "http://user:pass@proxy.example.com:8080" --query "The Ruler of Emojis"
```

#### Combining _**SeleniumBase UC Mode**_ automation with the anonymity of a _**residential proxy**_, <br> You can create a scraper that is both resilient and difficult to detect,<br> Capable of achieving consistent or at least _repeatable results_ against one of the web’s more aggressive anti-bot systems:

![runtime](/docs/png_repo_screenshots/runtime.png)

### P.S: <br> ... lets talk about containerizing this thing: 
- *Docker containers are intentionally not covered here when it comes to network settigns and use of proxies*: 
- *While useful in many contexts, containerizing this setup increases resource overhead (notably GPU usage) and still relies on the local host’s ISP and network characteristics:*
- *Which offers limited benefit for this particular use case, HOWEVER:*
- *if you are anything like Me a __Docker Freak__  and like to put everything in container as oppose to some __python venv__ and such, <br> go ahead and try [Scraper_Docker_Setup.md](/docs/Scraper_Docker_Setup.md) which has everything you need for indeed scraper container support:* 
---

# Thank you !
