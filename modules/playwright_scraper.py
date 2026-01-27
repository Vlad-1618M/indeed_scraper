#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Playwright Scraper Module:
    Uses JavaScript injection for DOM extraction to bypass selector issues:
    Supports full page screenshots, proxy, and improved extraction: """

import re
import time
import random
from pathlib import Path
from datetime import datetime
from urllib.parse import quote_plus
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

try:
    import pyautogui
    pyautogui.FAILSAFE = False  # Disable fail-safe for automated use
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("[!] PyAutoGUI not installed. Cloudflare auto-click disabled.")
    print("    Install with: pip install pyautogui")


class PlaywrightIndeedScraper:
    """ Indeed scraper using Playwright with JavaScript injection:
        Uses JS to directly query the DOM, bypassing CSS selector issues: """
    
    # JavaScript to extract all job data from the page
    EXTRACT_JOBS_JS = """
    () => {
        const jobs = [];
        
        // Try multiple ways to find job cards
        const selectors = [
            'div.job_seen_beacon',
            'div.jobsearch-ResultsList > div',
            'div[data-testid="job-card"]',
            'li.css-5lfssm',
            'td.resultContent',
            'div.tapItem',
            'a.tapItem',
            '[data-jk]',
        ];
        
        let cards = [];
        let usedSelector = '';
        
        for (const selector of selectors) {
            const found = document.querySelectorAll(selector);
            if (found && found.length > 0) {
                cards = Array.from(found);
                usedSelector = selector;
                console.log(`Found ${cards.length} cards with: ${selector}`);
                break;
            }
        }
        
        // If still no cards, try finding anything with data-jk
        if (cards.length === 0) {
            const allElements = document.querySelectorAll('*');
            cards = Array.from(allElements).filter(el => el.hasAttribute('data-jk'));
            usedSelector = 'data-jk attribute scan';
        }
        
        console.log(`Processing ${cards.length} job cards`);
        
        for (const card of cards) {
            try {
                const job = {};
                
                // Job Key - try multiple methods
                job.job_key = card.getAttribute('data-jk') || 
                              card.querySelector('[data-jk]')?.getAttribute('data-jk') ||
                              card.querySelector('a[data-jk]')?.getAttribute('data-jk') ||
                              card.getAttribute('data-mobtk') ||
                              null;
                
                // Extract from href if no data-jk
                if (!job.job_key) {
                    const link = card.querySelector('a[href*="jk="]') || 
                                 card.querySelector('h2 a') ||
                                 card.querySelector('a.jcs-JobTitle');
                    if (link) {
                        const href = link.getAttribute('href');
                        const match = href?.match(/jk=([a-f0-9]+)/i);
                        if (match) job.job_key = match[1];
                    }
                }
                
                // Title
                const titleEl = card.querySelector('h2.jobTitle span[title]') ||
                               card.querySelector('h2.jobTitle a') ||
                               card.querySelector('h2.jobTitle') ||
                               card.querySelector('a.jcs-JobTitle') ||
                               card.querySelector('[data-testid="jobTitle"]') ||
                               card.querySelector('.jobTitle');
                job.title = titleEl?.getAttribute('title') || 
                           titleEl?.innerText?.trim() || 
                           null;
                
                // Company
                const companyEl = card.querySelector('span[data-testid="company-name"]') ||
                                 card.querySelector('.companyName') ||
                                 card.querySelector('[data-testid="company-name"]') ||
                                 card.querySelector('.company');
                job.company = companyEl?.innerText?.trim() || null;
                
                // Location
                const locationEl = card.querySelector('div[data-testid="text-location"]') ||
                                  card.querySelector('.companyLocation') ||
                                  card.querySelector('[data-testid="text-location"]');
                job.location = locationEl?.innerText?.trim() || null;
                
                // Salary - check multiple elements
                const salarySelectors = [
                    'div[data-testid="attribute_snippet_testid"]',
                    '.salary-snippet-container',
                    '.salaryOnly',
                    '.salary-snippet',
                    '.salaryText',
                    'div.metadata.salary-snippet-container',
                    '[class*="salary"]',
                ];
                
                job.salary = null;
                for (const sel of salarySelectors) {
                    const els = card.querySelectorAll(sel);
                    for (const el of els) {
                        const text = el.innerText?.trim();
                        if (text && (text.includes('$') || text.toLowerCase().includes('year') || 
                            text.toLowerCase().includes('hour'))) {
                            // Exclude non-salary text
                            if (!text.toLowerCase().includes('posted') && 
                                !text.toLowerCase().includes('ago') &&
                                !text.toLowerCase().includes('apply')) {
                                job.salary = text;
                                break;
                            }
                        }
                    }
                    if (job.salary) break;
                }
                
                // Fallback: regex search in card text
                if (!job.salary) {
                    const cardText = card.innerText;
                    const salaryMatch = cardText.match(/\\$[\\d,]+(?:\\.\\d{2})?\\s*[-–]?\\s*(?:\\$[\\d,]+(?:\\.\\d{2})?)?\\s*(?:a |per |an |\\/)?\\s*(?:year|hour|month|week|yr|hr)/i);
                    if (salaryMatch) job.salary = salaryMatch[0];
                }
                
                // Snippet
                const snippetEl = card.querySelector('.job-snippet') ||
                                 card.querySelector('div[class*="job-snippet"]') ||
                                 card.querySelector('.jobsearch-JobComponent-description');
                job.snippet = snippetEl?.innerText?.trim()?.substring(0, 500) || null;
                
                // Posted date
                const dateSelectors = [
                    'span.date',
                    'span[data-testid="myJobsStateDate"]',
                    '[class*="date"]',
                ];
                
                job.posted = null;
                for (const sel of dateSelectors) {
                    const els = card.querySelectorAll(sel);
                    for (const el of els) {
                        const text = el.innerText?.trim()?.toLowerCase();
                        if (text && (text.includes('posted') || text.includes('ago') || 
                            text.includes('day') || text.includes('hour') || text.includes('just'))) {
                            job.posted = el.innerText?.trim();
                            break;
                        }
                    }
                    if (job.posted) break;
                }
                
                // Fallback: regex for posted date
                if (!job.posted) {
                    const cardText = card.innerText;
                    const dateMatch = cardText.match(/(?:Posted\\s+)?\\d+\\+?\\s*(?:day|hour|week|month)s?\\s*ago|Just\\s+posted|Today|Yesterday/i);
                    if (dateMatch) job.posted = dateMatch[0];
                }
                
                // Get bounding box for screenshot
                const rect = card.getBoundingClientRect();
                job.boundingBox = {
                    x: rect.x + window.scrollX,
                    y: rect.y + window.scrollY,
                    width: rect.width,
                    height: rect.height
                };
                
                // Only add if we have at least a title or job_key
                if (job.title || job.job_key) {
                    jobs.push(job);
                }
                
            } catch (e) {
                console.error('Error extracting job:', e);
            }
        }
        
        return {
            jobs: jobs,
            selector: usedSelector,
            totalFound: cards.length
        };
    }
    """
    
    def __init__(self, headless=False, incognito=False, window_size="maximized", 
                 proxy=None, screenshots=False, artifacts_dir=None):
        """
        Initialize Playwright scraper.
        
        Args:
            headless (bool): Run in headless mode
            incognito (bool): Use incognito context
            window_size (str): Window size - "maximized" or "WIDTHxHEIGHT"
            proxy (dict): Proxy configuration
            screenshots (bool): Enable screenshot capture
            artifacts_dir (str): Base directory for artifacts
        """
        self.headless = headless
        self.incognito = incognito
        self.window_size = window_size
        self.proxy = proxy
        self.screenshots = screenshots
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        
        # Setup screenshot directories
        if artifacts_dir:
            self.artifacts_dir = Path(artifacts_dir)
        else:
            self.artifacts_dir = Path.cwd() / 'artifacts'
        
        if self.screenshots:
            self.screenshots_dir = self.artifacts_dir / 'screenshots'
            self.pages_dir = self.screenshots_dir / 'pages'
            self.cards_dir = self.screenshots_dir / 'cards'
            self.pages_dir.mkdir(parents=True, exist_ok=True)
            self.cards_dir.mkdir(parents=True, exist_ok=True)
        
        # Start browser immediately
        self._start_browser()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
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
        
        # Add proxy if provided
        if self.proxy:
            launch_options['proxy'] = {
                'server': self.proxy.get('server', ''),
            }
            if self.proxy.get('username'):
                launch_options['proxy']['username'] = self.proxy['username']
                launch_options['proxy']['password'] = self.proxy.get('password', '')
        
        # Launch browser
        self.browser = self.playwright.chromium.launch(**launch_options)
        
        # Parse window size
        if self.window_size == "maximized":
            viewport = {'width': 1920, 'height': 1080}
        else:
            try:
                width, height = map(int, self.window_size.split('x'))
                viewport = {'width': width, 'height': height}
            except:
                viewport = {'width': 1920, 'height': 1080}
        
        # Create context with anti-detection settings
        context_options = {
            'viewport': viewport,
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'locale': 'en-US',
            'timezone_id': 'America/New_York',
            'geolocation': {'latitude': 40.7128, 'longitude': -74.0060},
            'permissions': ['geolocation'],
            'java_script_enabled': True,
            'bypass_csp': True,
        }
        
        self.context = self.browser.new_context(**context_options)
        
        # Add stealth scripts to evade detection
        self.context.add_init_script("""
            // Remove webdriver flag
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Mock plugins array
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Add chrome object
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // Mock permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Hide automation indicators
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        """)
        
        # Create page
        self.page = self.context.new_page()
        
        # Set extra headers
        self.page.set_extra_http_headers({
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        })
        
        if self.incognito:
            print("[*] Running in incognito mode (Playwright)")
        
        print("[+] Playwright browser started")
    
    def scrape_jobs(self, query, location="", remote_only=False,
                    min_salary=None, max_salary=None, date_posted=None,
                    max_results=25):
        """
        Scrape Indeed jobs using JavaScript injection.
        
        Args:
            query (str): Job search query
            location (str): Job location
            remote_only (bool): Remote filter
            min_salary (int): Min salary
            max_salary (int): Max salary
            date_posted (int): Days filter
            max_results (int): Max results
            
        Returns:
            list: Job dictionaries
        """
        # Build URL
        params = []
        if query:
            params.append(f"q={quote_plus(query)}")
        if location:
            params.append(f"l={quote_plus(location)}")
        if remote_only:
            params.append("sc=0kf%3Aattr%28DSQF7%29%3B")
        if min_salary and max_salary:
            params.append(f"salary={min_salary}-{max_salary}")
        if date_posted:
            params.append(f"fromage={date_posted}")
        
        base_url = f"https://www.indeed.com/jobs?{'&'.join(params)}"
        
        all_jobs = []
        page_num = 0
        session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        print(f"\n{'='*80}")
        print(f"Starting scrape: {query} in {location if location else 'Any location'}")
        print(f"{'='*80}")
        
        while len(all_jobs) < max_results:
            # Build page URL
            if page_num > 0:
                url = f"{base_url}&start={page_num * 10}"
            else:
                url = base_url
            
            print(f"\n[*] Page {page_num + 1}: {url}")
            
            try:
                # Navigate with realistic timing
                self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
                
                # Wait for page to stabilize
                self._human_delay(3, 5)
                
                # Check for Cloudflare
                if self._is_cloudflare_challenge():
                    print("  [!] Cloudflare challenge detected")
                    
                    # Try auto-click first
                    if PYAUTOGUI_AVAILABLE:
                        if self._click_cloudflare_checkbox():
                            # Successfully solved
                            pass
                        else:
                            # Auto-click failed, ask for manual intervention
                            print("="*60)
                            print("MANUAL INTERVENTION REQUIRED")
                            print("Auto-click failed. Please solve the challenge manually.")
                            print("="*60)
                            input("[*] Press Enter after completing the challenge...")
                    else:
                        # PyAutoGUI not available
                        print("="*60)
                        print("MANUAL INTERVENTION REQUIRED")
                        print("Please solve the challenge in the browser window.")
                        print("="*60)
                        input("[*] Press Enter after completing the challenge...")
                    
                    self._human_delay(2, 3)
                    
                    # Verify challenge is solved
                    if self._is_cloudflare_challenge():
                        print("  [!] Challenge still present after intervention")
                        print("  [*] Waiting for page to load...")
                        self._human_delay(5, 8)
                
                # Scroll through page to load all content
                print("  [*] Scrolling page to load content...")
                self._scroll_page()
                
                # Take full page screenshot if enabled
                if self.screenshots:
                    print("  [*] Taking page screenshot...")
                    self._take_page_screenshot(page_num + 1, query, session_ts)
                
                # Use JavaScript injection to extract jobs
                print("  [*] Injecting JavaScript to extract job data...")
                result = self.page.evaluate(self.EXTRACT_JOBS_JS)
                
                if not result or not result.get('jobs'):
                    print(f"  [!] No jobs found via JS injection")
                    print(f"  [*] Selector used: {result.get('selector', 'none')}")
                    print(f"  [*] Total elements found: {result.get('totalFound', 0)}")
                    
                    # Save debug screenshot
                    if self.screenshots:
                        debug_path = self.pages_dir / f"debug_no_jobs_page{page_num + 1}.png"
                        self.page.screenshot(path=str(debug_path), full_page=True)
                        print(f"  [*] Debug screenshot saved: {debug_path}")
                    
                    # Try scrolling and retry
                    print("  [*] Scrolling page and retrying...")
                    self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    self._human_delay(2, 3)
                    result = self.page.evaluate(self.EXTRACT_JOBS_JS)
                    
                    if not result or not result.get('jobs'):
                        print("  [!] Still no jobs after scroll, moving to next page")
                        break
                
                js_jobs = result.get('jobs', [])
                selector_used = result.get('selector', 'unknown')
                
                print(f"  [+] JS extracted {len(js_jobs)} jobs using: {selector_used}")
                
                page_jobs = 0
                for idx, js_job in enumerate(js_jobs):
                    if len(all_jobs) >= max_results:
                        break
                    
                    # Convert JS job to our format
                    job_data = self._convert_js_job(js_job, query, location, page_num + 1)
                    
                    # Check duplicates
                    if job_data['job_key'] != "Not Available":
                        if any(j['job_key'] == job_data['job_key'] for j in all_jobs):
                            continue
                    elif job_data['url'] != "Not Available":
                        if any(j['url'] == job_data['url'] for j in all_jobs):
                            continue
                    
                    if job_data['title'] != "Not Available":
                        # Take job card screenshot if enabled
                        if self.screenshots and js_job.get('boundingBox'):
                            screenshot_path = self._take_job_screenshot_by_coords(
                                js_job['boundingBox'],
                                page_num + 1, len(all_jobs) + 1,
                                job_data['title'], job_data['job_key'], session_ts
                            )
                            job_data['screenshot'] = str(screenshot_path) if screenshot_path else "Not Available"
                        
                        all_jobs.append(job_data)
                        page_jobs += 1
                        print(f"  [{len(all_jobs)}] {job_data['title'][:50]} | {job_data['company'][:25]}")
                
                if page_jobs == 0:
                    print("[*] No new jobs on this page")
                    break
                
                if len(all_jobs) >= max_results:
                    break
                
                # Try to click Next button for pagination
                print("  [*] Looking for Next page button...")
                if not self._click_next_page():
                    print("  [!] No Next button found, trying URL pagination...")
                    # Fallback to URL-based pagination
                    page_num += 1
                    continue
                
                # Human-like delay between pages
                self._human_delay(3, 6)
                page_num += 1
                
            except PlaywrightTimeout:
                print(f"[!] Timeout on page {page_num + 1}")
                if self.screenshots:
                    debug_path = self.pages_dir / f"timeout_page{page_num + 1}.png"
                    try:
                        self.page.screenshot(path=str(debug_path))
                        print(f"  [*] Timeout screenshot saved: {debug_path}")
                    except:
                        pass
                break
            except Exception as e:
                print(f"[X] Error on page {page_num + 1}: {e}")
                import traceback
                traceback.print_exc()
                break
        
        print(f"\n{'='*80}")
        print(f"Scraping complete: {len(all_jobs)} jobs collected")
        print(f"{'='*80}")
        
        return all_jobs if all_jobs else None
    
    # Alias for compatibility
    search_jobs = scrape_jobs
    
    def _convert_js_job(self, js_job, query, location, page_num):
        """
        Convert JavaScript-extracted job to our standard format.
        
        Args:
            js_job (dict): Job data from JavaScript
            query (str): Search query
            location (str): Search location
            page_num (int): Current page number
            
        Returns:
            dict: Standardized job data
        """
        job_key = js_job.get('job_key')
        
        return {
            'scraped_at': datetime.now().isoformat(),
            'search_query': query,
            'search_location': location,
            'page_number': page_num,
            'job_key': job_key if job_key else "Not Available",
            'url': f"https://www.indeed.com/viewjob?jk={job_key}" if job_key else "Not Available",
            'title': js_job.get('title') or "Not Available",
            'company': js_job.get('company') or "Not Available",
            'location': js_job.get('location') or "Not Available",
            'salary': js_job.get('salary') or "Not Available",
            'snippet': js_job.get('snippet') or "Not Available",
            'posted': js_job.get('posted') or "Not Available",
        }
    
    def _take_page_screenshot(self, page_num, query, session_ts):
        """
        Take a FULL PAGE screenshot.
        
        Args:
            page_num (int): Current page number
            query (str): Search query
            session_ts (str): Session timestamp
            
        Returns:
            Path: Screenshot file path
        """
        try:
            safe_query = re.sub(r'[^\w\s-]', '', query).strip().replace(' ', '_')[:30]
            timestamp = datetime.now().strftime("%H%M%S")
            
            filename = f"page{page_num:02d}_{safe_query}_{session_ts}_{timestamp}.png"
            filepath = self.pages_dir / filename
            
            # Playwright native full page screenshot
            self.page.screenshot(path=str(filepath), full_page=True)
            print(f"  [Screenshot] Full page saved: {filename}")
            
            return filepath
        except Exception as e:
            print(f"  [!] Screenshot error: {e}")
            return None
    
    def _take_job_screenshot_by_coords(self, bounding_box, page_num, job_num, title, job_key, session_ts):
        """
        Take a screenshot of a specific job card using coordinates.
        
        Args:
            bounding_box (dict): {x, y, width, height} from JS
            page_num (int): Current page number
            job_num (int): Job number
            title (str): Job title
            job_key (str): Job key
            session_ts (str): Session timestamp
            
        Returns:
            Path: Screenshot file path
        """
        try:
            safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')[:25]
            safe_key = job_key if job_key != "Not Available" else "nokey"
            timestamp = datetime.now().strftime("%H%M%S")
            
            filename = f"page{page_num:02d}_job{job_num:03d}_{safe_title}_{safe_key}_{timestamp}.png"
            filepath = self.cards_dir / filename
            
            # Scroll element into view first
            self.page.evaluate(f"window.scrollTo(0, {bounding_box['y'] - 100})")
            self._human_delay(0.2, 0.4)
            
            # Take screenshot with clip
            self.page.screenshot(
                path=str(filepath),
                clip={
                    'x': max(0, bounding_box['x']),
                    'y': max(0, bounding_box['y']),
                    'width': bounding_box['width'],
                    'height': bounding_box['height']
                }
            )
            
            return filepath
        except Exception as e:
            # Fallback to viewport screenshot
            try:
                safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')[:25]
                timestamp = datetime.now().strftime("%H%M%S")
                filename = f"page{page_num:02d}_job{job_num:03d}_{safe_title}_viewport_{timestamp}.png"
                filepath = self.cards_dir / filename
                self.page.screenshot(path=str(filepath))
                return filepath
            except:
                return None
    
    def _scroll_page(self):
        """
        Scroll through the page to load lazy-loaded content.
        """
        try:
            # Get page height
            page_height = self.page.evaluate("document.body.scrollHeight")
            viewport_height = self.page.evaluate("window.innerHeight")
            
            # Scroll in increments
            current_position = 0
            scroll_step = viewport_height * 0.8
            
            while current_position < page_height:
                current_position += scroll_step
                self.page.evaluate(f"window.scrollTo(0, {current_position})")
                self._human_delay(0.3, 0.6)
                
                # Update page height (might have loaded more content)
                new_height = self.page.evaluate("document.body.scrollHeight")
                if new_height > page_height:
                    page_height = new_height
            
            # Scroll back to top
            self.page.evaluate("window.scrollTo(0, 0)")
            self._human_delay(0.5, 1)
            
        except Exception as e:
            print(f"  [!] Scroll error: {e}")
    
    def _click_next_page(self):
        """
        Click the Next page button.
        
        Returns:
            bool: True if clicked successfully, False otherwise
        """
        try:
            # Try multiple selectors for Next button
            next_selectors = [
                'a[data-testid="pagination-page-next"]',
                'a[aria-label="Next Page"]',
                'a[aria-label="Next"]',
                'nav[aria-label="pagination"] a:last-child',
                'ul.pagination-list li:last-child a',
                'a.np',  # Indeed's next page class
                '[data-testid="pagination"] a:has-text("Next")',
            ]
            
            for selector in next_selectors:
                try:
                    next_btn = self.page.query_selector(selector)
                    if next_btn and next_btn.is_visible():
                        # Scroll to button
                        next_btn.scroll_into_view_if_needed()
                        self._human_delay(0.5, 1)
                        
                        # Click
                        next_btn.click()
                        print(f"  [+] Clicked Next button: {selector}")
                        
                        # Wait for navigation
                        self.page.wait_for_load_state('domcontentloaded', timeout=15000)
                        self._human_delay(2, 4)
                        
                        return True
                except:
                    continue
            
            # Try JavaScript click as fallback
            clicked = self.page.evaluate("""
                () => {
                    // Find Next link by text
                    const links = document.querySelectorAll('a');
                    for (const link of links) {
                        const text = link.innerText?.toLowerCase() || '';
                        const ariaLabel = link.getAttribute('aria-label')?.toLowerCase() || '';
                        if (text.includes('next') || ariaLabel.includes('next')) {
                            link.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            
            if clicked:
                print("  [+] Clicked Next button via JS")
                self.page.wait_for_load_state('domcontentloaded', timeout=15000)
                self._human_delay(2, 4)
                return True
            
            return False
            
        except Exception as e:
            print(f"  [!] Next button click error: {e}")
            return False
    
    def _is_cloudflare_challenge(self):
        """Check if current page is Cloudflare challenge."""
        try:
            # Use JS to check page content
            result = self.page.evaluate("""
                () => {
                    const title = document.title.toLowerCase();
                    const body = document.body?.innerText?.toLowerCase() || '';
                    
                    return {
                        isCloudflare: title.includes('cloudflare') || 
                                     title.includes('just a moment') ||
                                     body.includes('verify you are human') ||
                                     body.includes('checking your browser') ||
                                     body.includes('ray id') ||
                                     body.includes('additional verification'),
                        title: document.title,
                        hasJobCards: document.querySelectorAll('[data-jk], .job_seen_beacon, .jobsearch-ResultsList').length > 0
                    };
                }
            """)
            
            if result.get('isCloudflare') and not result.get('hasJobCards'):
                print(f"  [*] Page title: {result.get('title')}")
                return True
            return False
        except:
            return False
    
    def _click_cloudflare_checkbox(self, max_attempts=5):
        """
        Automatically click the Cloudflare Turnstile checkbox using PyAutoGUI.
        
        This mimics SeleniumBase's uc_gui_click_captcha() approach.
        
        Args:
            max_attempts (int): Maximum click attempts
            
        Returns:
            bool: True if challenge was solved, False otherwise
        """
        if not PYAUTOGUI_AVAILABLE:
            print("  [!] PyAutoGUI not available for auto-click")
            return False
        
        print("  [*] Attempting to auto-click Cloudflare checkbox...")
        
        # First, wait for the challenge to fully load
        print("  [*] Waiting for Cloudflare challenge to load...")
        self._human_delay(2, 4)
        
        for attempt in range(max_attempts):
            try:
                # Get browser window position
                window_info = self.page.evaluate("""
                    () => {
                        return {
                            screenX: window.screenX,
                            screenY: window.screenY,
                            outerWidth: window.outerWidth,
                            outerHeight: window.outerHeight,
                            innerWidth: window.innerWidth,
                            innerHeight: window.innerHeight
                        };
                    }
                """)
                
                # Find the Cloudflare checkbox using multiple methods
                checkbox_info = self.page.evaluate("""
                    () => {
                        // Method 1: Find any iframe (Cloudflare embeds in iframe)
                        const iframes = document.querySelectorAll('iframe');
                        for (const iframe of iframes) {
                            const src = iframe.src || '';
                            const title = iframe.title || '';
                            const name = iframe.name || '';
                            
                            // Check if it's a Cloudflare/Turnstile iframe
                            if (src.includes('cloudflare') || 
                                src.includes('turnstile') ||
                                src.includes('challenges') ||
                                title.toLowerCase().includes('challenge') ||
                                name.includes('cf-') ||
                                iframe.id?.includes('cf-')) {
                                
                                const rect = iframe.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0) {
                                    return {
                                        found: true,
                                        type: 'cloudflare-iframe',
                                        x: rect.x + 30,  // Checkbox is on the left side
                                        y: rect.y + rect.height / 2,
                                        width: rect.width,
                                        height: rect.height
                                    };
                                }
                            }
                        }
                        
                        // Method 2: Find by common Cloudflare container classes
                        const cfContainers = document.querySelectorAll(
                            '.cf-turnstile, #cf-turnstile, [data-sitekey], .h-captcha, .g-recaptcha, ' +
                            'div[style*="challenges.cloudflare.com"], div.challenge-container'
                        );
                        
                        for (const container of cfContainers) {
                            const rect = container.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                return {
                                    found: true,
                                    type: 'cf-container',
                                    x: rect.x + 30,
                                    y: rect.y + rect.height / 2,
                                    width: rect.width,
                                    height: rect.height
                                };
                            }
                        }
                        
                        // Method 3: Find checkbox by text proximity
                        const verifyTexts = [
                            'Verify you are human',
                            'verify you are human',
                            'I am human',
                            'Confirm you are human'
                        ];
                        
                        for (const text of verifyTexts) {
                            const xpath = `//*[contains(text(), '${text}')]`;
                            const result = document.evaluate(
                                xpath, document, null, 
                                XPathResult.FIRST_ORDERED_NODE_TYPE, null
                            );
                            
                            if (result.singleNodeValue) {
                                const el = result.singleNodeValue;
                                const rect = el.getBoundingClientRect();
                                // Checkbox is typically to the left of the text
                                return {
                                    found: true,
                                    type: 'verify-text',
                                    x: rect.x - 25,
                                    y: rect.y + rect.height / 2,
                                    width: 50,
                                    height: rect.height
                                };
                            }
                        }
                        
                        // Method 4: Find any visible checkbox on the page
                        const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                        for (const cb of checkboxes) {
                            const rect = cb.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0 && rect.y > 0) {
                                return {
                                    found: true,
                                    type: 'checkbox-input',
                                    x: rect.x + rect.width / 2,
                                    y: rect.y + rect.height / 2,
                                    width: rect.width,
                                    height: rect.height
                                };
                            }
                        }
                        
                        // Method 5: Look for any iframe and try clicking center-left
                        if (iframes.length > 0) {
                            const iframe = iframes[0];
                            const rect = iframe.getBoundingClientRect();
                            if (rect.width > 50 && rect.height > 20) {
                                return {
                                    found: true,
                                    type: 'any-iframe',
                                    x: rect.x + 30,
                                    y: rect.y + rect.height / 2,
                                    width: rect.width,
                                    height: rect.height
                                };
                            }
                        }
                        
                        // Method 6: Find element with 'challenge' in any attribute
                        const allElements = document.querySelectorAll('*');
                        for (const el of allElements) {
                            const attrs = el.attributes;
                            for (const attr of attrs) {
                                if (attr.value?.toLowerCase().includes('challenge') ||
                                    attr.value?.toLowerCase().includes('turnstile') ||
                                    attr.value?.toLowerCase().includes('captcha')) {
                                    const rect = el.getBoundingClientRect();
                                    if (rect.width > 50 && rect.height > 20) {
                                        return {
                                            found: true,
                                            type: 'challenge-attr',
                                            x: rect.x + 30,
                                            y: rect.y + rect.height / 2,
                                            width: rect.width,
                                            height: rect.height
                                        };
                                    }
                                }
                            }
                        }
                        
                        return { found: false, iframeCount: iframes.length };
                    }
                """)
                
                if not checkbox_info.get('found'):
                    iframe_count = checkbox_info.get('iframeCount', 0)
                    print(f"  [!] Attempt {attempt + 1}: Checkbox not found (iframes: {iframe_count})")
                    
                    # Take a debug screenshot to see what's on the page
                    if attempt == 0 and self.screenshots:
                        debug_path = self.pages_dir / f"debug_cloudflare_attempt{attempt + 1}.png"
                        self.page.screenshot(path=str(debug_path))
                        print(f"  [*] Debug screenshot: {debug_path}")
                    
                    # Wait longer for challenge to load
                    self._human_delay(2, 4)
                    continue
                
                print(f"  [*] Found {checkbox_info['type']} at ({checkbox_info['x']:.0f}, {checkbox_info['y']:.0f})")
                print(f"  [*] Element size: {checkbox_info['width']:.0f}x{checkbox_info['height']:.0f}")
                
                # Calculate screen coordinates
                # Account for browser chrome (toolbar, etc.)
                # macOS Chrome: ~85px, Windows Chrome: ~75px
                import platform
                if platform.system() == 'Darwin':  # macOS
                    browser_chrome_height = 85
                else:
                    browser_chrome_height = 75
                
                screen_x = window_info['screenX'] + checkbox_info['x']
                screen_y = window_info['screenY'] + browser_chrome_height + checkbox_info['y']
                
                print(f"  [*] Screen coordinates: ({screen_x:.0f}, {screen_y:.0f})")
                
                # Add some randomness to the target
                target_x = screen_x + random.randint(-3, 3)
                target_y = screen_y + random.randint(-3, 3)
                
                # Move mouse with human-like motion
                pyautogui.moveTo(
                    target_x, target_y,
                    duration=random.uniform(0.4, 0.8),
                    tween=pyautogui.easeOutQuad
                )
                
                # Small pause before click (human behavior)
                time.sleep(random.uniform(0.15, 0.35))
                
                # Click
                pyautogui.click()
                print(f"  [+] Clicked at ({target_x:.0f}, {target_y:.0f})")
                
                # Wait for challenge to process
                print("  [*] Waiting for challenge to process...")
                self._human_delay(4, 6)
                
                # Check if challenge is solved
                if not self._is_cloudflare_challenge():
                    print("  [+] Cloudflare challenge solved!")
                    return True
                
                print(f"  [!] Attempt {attempt + 1}: Challenge still present, retrying...")
                self._human_delay(1, 2)
                
            except Exception as e:
                print(f"  [!] Auto-click error: {e}")
                import traceback
                traceback.print_exc()
                
        print("  [X] Failed to auto-solve Cloudflare challenge")
        return False
    
    def _human_delay(self, min_seconds=1, max_seconds=3):
        """Random human-like delay."""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def close(self):
        """Close browser and cleanup."""
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            print("[*] Playwright browser closed")
        except Exception as e:
            print(f"[!] Error closing browser: {e}")


if __name__ == "__main__":
    pass