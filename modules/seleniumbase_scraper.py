#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Indeed Job Scraper - SeleniumBase UC Mode
Uses SeleniumBase's Undetected ChromeDriver mode for Cloudflare bypass

Key features:
- uc=True: Undetected ChromeDriver that evades bot detection
- uc_cdp_events=True: Enables CDP events for better stealth
- uc_gui_click_captcha(): Automatically clicks Turnstile/Cloudflare checkbox
- reconnect(): Disconnects/reconnects to evade detection after actions
- Screenshot support for cross-referencing with JSON output
"""

import re
import time
import random
from pathlib import Path
from datetime import datetime
from seleniumbase import SB, Driver
from selenium.webdriver.common.by import By
from urllib.parse import quote_plus, urlparse, parse_qs
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class SeleniumBaseIndeedScraper:
    """
    Indeed scraper using SeleniumBase UC Mode for Cloudflare bypass.
    
    UC Mode advantages over regular Selenium:
    - Patches ChromeDriver at runtime to avoid detection
    - Removes automation flags that Cloudflare checks
    - uc_gui_click_captcha() can solve Turnstile challenges
    - reconnect() helps evade detection after suspicious actions
    """
    
    def __init__(self, headless=False, incognito=False, window_size="maximized", 
                 proxy=None, screenshots=False, artifacts_dir=None):
        """
        Initialize SeleniumBase scraper in UC Mode.
        
        Args:
            headless (bool): Run headless (uses xvfb on Linux)
            incognito (bool): Use incognito mode
            window_size (str): "maximized" or "WIDTHxHEIGHT"
            proxy (dict): Proxy config {'server': '...', 'username': '...', 'password': '...'}
            screenshots (bool): Enable screenshot capture for each job
            artifacts_dir (Path): Base artifacts directory
        """
        self.headless = headless
        self.incognito = incognito
        self.window_size = window_size
        self.proxy = proxy
        self.screenshots = screenshots
        self.sb = None
        self.driver = None
        
        # Setup screenshots directories
        if artifacts_dir:
            self.artifacts_dir = Path(artifacts_dir)
        else:
            self.artifacts_dir = Path(__file__).parent.parent / "artifacts"
        
        self.screenshots_dir = self.artifacts_dir / "screenshots"
        self.pages_dir = self.screenshots_dir / "pages"      # Full page screenshots
        self.cards_dir = self.screenshots_dir / "cards"      # Individual job card screenshots
        
        if self.screenshots:
            self.pages_dir.mkdir(parents=True, exist_ok=True)
            self.cards_dir.mkdir(parents=True, exist_ok=True)
            print(f"[*] Page screenshots: {self.pages_dir}")
            print(f"[*] Card screenshots: {self.cards_dir}")
        
        self._start_browser()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def _start_browser(self):
        """Start SeleniumBase browser in UC Mode."""
        print("[*] Starting SeleniumBase UC Mode browser...")
        
        # Build SB options
        sb_options = {
            'uc': True,  # Undetected ChromeDriver mode
            'uc_cdp_events': True,  # Enable CDP events for stealth
            'uc_subprocess': False,  # Run in same process for better control
            'incognito': self.incognito,
            'locale_code': 'en',
            'disable_csp': True,  # Disable Content Security Policy
            'block_images': False,  # Keep images for CAPTCHA solving
        }
        
        # Headless mode - use xvfb on Linux for UC mode
        if self.headless:
            sb_options['headless'] = True
            sb_options['xvfb'] = True  # Virtual framebuffer for Linux
        
        # Proxy support
        if self.proxy:
            proxy_str = self.proxy.get('server', '')
            if 'username' in self.proxy and self.proxy['username']:
                auth = f"{self.proxy['username']}:{self.proxy.get('password', '')}"
                server = proxy_str.replace('http://', '').replace('https://', '')
                proxy_str = f"{auth}@{server}"
            sb_options['proxy'] = proxy_str
        
        # Create SB context manager but manage it manually
        self._sb_context = SB(**sb_options)
        self.sb = self._sb_context.__enter__()
        self.driver = self.sb.driver
        
        # Set window size
        if self.window_size == "maximized":
            self.sb.maximize_window()
        else:
            try:
                width, height = map(int, self.window_size.split('x'))
                self.sb.set_window_size(width, height)
            except:
                self.sb.maximize_window()
        
        print("[+] SeleniumBase UC Mode browser started")
    
    def login(self, email, password):
        """
        Login to Indeed account.
        
        Args:
            email (str): Indeed account email
            password (str): Indeed account password
            
        Returns:
            bool: True if login successful
        """
        try:
            print("\n[*] Attempting Indeed login...")
            self.sb.uc_open_with_reconnect("https://secure.indeed.com/auth", reconnect_time=4)
            
            # Handle Cloudflare if present
            self._handle_cloudflare()
            
            # Fill email
            self.sb.wait_for_element('input[type="email"], input[name="__email"]', timeout=10)
            self.sb.type('input[type="email"], input[name="__email"]', email)
            self._human_delay(1, 2)
            
            # Click continue
            self.sb.click('button[type="submit"]')
            self._human_delay(2, 4)
            
            # Fill password
            try:
                self.sb.wait_for_element('input[type="password"]', timeout=10)
                self.sb.type('input[type="password"]', password)
                self._human_delay(1, 2)
                
                # Submit
                self.sb.click('button[type="submit"]')
                self._human_delay(3, 5)
            except:
                print("[!] Password field not found - may need alternative auth")
            
            # Check success
            if 'indeed.com' in self.sb.get_current_url() and 'auth' not in self.sb.get_current_url():
                print("[+] Login successful")
                return True
            else:
                print("[X] Login may have failed")
                return False
                
        except Exception as e:
            print(f"[X] Login error: {e}")
            return False
    
    def search_jobs(self, query, location="", remote_only=False,
                   min_salary=None, max_salary=None, date_posted=None,
                   max_results=25):
        """
        Search Indeed jobs with UC Mode Cloudflare bypass.
        
        Args:
            query (str): Job search query
            location (str): Job location
            remote_only (bool): Remote filter
            min_salary (int): Min salary
            max_salary (int): Max salary
            date_posted (int): Days filter
            max_results (int): Max results
            
        Returns:
            list: Job dictionaries or None
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
        consecutive_failures = 0
        max_failures = 3
        
        # Session timestamp for screenshot naming
        session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        while len(all_jobs) < max_results and consecutive_failures < max_failures:
            # Build page URL
            if page_num > 0:
                url = f"{base_url}&start={page_num * 10}"
            else:
                url = base_url
            
            print(f"\n[*] Page {page_num + 1}: {url}")
            
            try:
                # Use uc_open_with_reconnect for stealth navigation
                self.sb.uc_open_with_reconnect(url, reconnect_time=5)
                
                # Human-like delay
                self._human_delay(2, 4)
                
                # Handle Cloudflare challenge if present
                if self._handle_cloudflare():
                    print("[+] Cloudflare challenge handled")
                    self.sb.reconnect(timeout=3)
                    self._human_delay(2, 3)
                
                # Wait for job cards
                try:
                    self.sb.wait_for_element('div.job_seen_beacon', timeout=15)
                except:
                    try:
                        self.sb.wait_for_element('[data-testid="jobsearch-ResultsList"]', timeout=10)
                    except:
                        print("[!] Could not find job listings")
                        consecutive_failures += 1
                        
                        if self._is_cloudflare_challenge():
                            print("[!] Still blocked by Cloudflare - trying again...")
                            self._handle_cloudflare()
                        
                        self._human_delay(5, 10)
                        continue
                
                # Take page screenshot if enabled
                if self.screenshots:
                    self._take_page_screenshot(page_num + 1, query, session_ts)
                
                # Extract jobs
                job_cards = self.sb.find_elements('div.job_seen_beacon')
                
                if not job_cards:
                    job_cards = self.sb.find_elements('div.jobsearch-ResultsList > div')
                
                print(f"[*] Found {len(job_cards)} job cards")
                
                page_jobs = 0
                for idx, card in enumerate(job_cards):
                    if len(all_jobs) >= max_results:
                        break
                    
                    try:
                        job_data = self._extract_job_from_element(card, query, location, page_num + 1)
                        
                        # Check duplicates by job_key or URL
                        if job_data['job_key'] != "Not Available":
                            if any(j['job_key'] == job_data['job_key'] for j in all_jobs):
                                continue
                        elif job_data['url'] != "Not Available":
                            if any(j['url'] == job_data['url'] for j in all_jobs):
                                continue
                        
                        if job_data['title'] != "Not Available":
                            # Take individual job screenshot if enabled
                            if self.screenshots:
                                screenshot_path = self._take_job_screenshot(
                                    card, page_num + 1, len(all_jobs) + 1, 
                                    job_data['title'], job_data['job_key'], session_ts
                                )
                                job_data['screenshot'] = str(screenshot_path) if screenshot_path else "Not Available"
                            
                            all_jobs.append(job_data)
                            page_jobs += 1
                            print(f"  [{len(all_jobs)}] {job_data['title'][:50]} | {job_data['url'][:60] if job_data['url'] != 'Not Available' else 'No URL'}")
                    
                    except Exception as e:
                        print(f"  [!] Error parsing job: {e}")
                        continue
                
                if page_jobs == 0:
                    print("[!] No new jobs on this page")
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0
                
                if len(all_jobs) >= max_results:
                    break
                
                # Reconnect before pagination
                print("[*] Reconnecting before next page...")
                self.sb.reconnect(timeout=2)
                
                # Human-like delay between pages
                self._human_delay(4, 8)
                page_num += 1
                
            except Exception as e:
                print(f"[X] Error on page {page_num + 1}: {e}")
                consecutive_failures += 1
                self._human_delay(5, 10)
        
        if consecutive_failures >= max_failures:
            print(f"\n[!] Stopped after {max_failures} consecutive failures")
        
        return all_jobs if all_jobs else None
    
    def _handle_cloudflare(self):
        """ Handle Cloudflare challenge using SeleniumBase UC Mode.
            Returns: bool: True if challenge was detected and handled """
        if not self._is_cloudflare_challenge():
            return False
        
        print("[*] Cloudflare challenge detected - attempting UC Mode bypass...")
        
        try:
            # Method 1: Use SeleniumBase's built-in CAPTCHA clicker
            try:
                self.sb.uc_gui_click_captcha()
                print("[*] Clicked Cloudflare checkbox via uc_gui_click_captcha()")
                self._human_delay(3, 5)
                
                if not self._is_cloudflare_challenge():
                    print("[+] Cloudflare challenge solved!")
                    return True
            except Exception as e:
                print(f"[!] uc_gui_click_captcha failed: {e}")
            
            # Method 2: Try clicking iframe checkbox directly
            try:
                iframes = self.sb.find_elements('iframe')
                for iframe in iframes:
                    src = iframe.get_attribute('src') or ''
                    if 'challenges.cloudflare.com' in src or 'turnstile' in src:
                        self.sb.switch_to_frame(iframe)
                        try:
                            checkbox = self.sb.find_element('input[type="checkbox"]')
                            if checkbox:
                                self.sb.execute_script("arguments[0].click();", checkbox)
                                print("[*] Clicked Turnstile checkbox in iframe")
                                self._human_delay(3, 5)
                        except:
                            pass
                        finally:
                            self.sb.switch_to_default_content()
                
                if not self._is_cloudflare_challenge():
                    print("[+] Cloudflare challenge solved!")
                    return True
            except Exception as e:
                print(f"[!] Iframe method failed: {e}")
            
            # Method 3: Wait for manual intervention
            print("\n" + "="*60)
            print("MANUAL INTERVENTION REQUIRED")
            print("="*60)
            print("Cloudflare challenge could not be auto-solved.")
            print("Please solve the challenge in the browser window.")
            print("="*60)
            
            for i in range(12):
                self._human_delay(5, 5)
                if not self._is_cloudflare_challenge():
                    print("[+] Challenge solved manually!")
                    return True
                print(f"[*] Waiting... ({(i+1)*5}s)")
            
            print("[X] Cloudflare challenge timeout")
            return True
            
        except Exception as e:
            print(f"[!] Error handling Cloudflare: {e}")
            return False
    
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
    
    def _extract_job_from_element(self, element, query, location, page_num):
        """
        Extract job data from a Selenium element.
        Fixed to properly extract job_key and URL from multiple sources.
        """
        job_data = {
            'scraped_at': datetime.now().isoformat(),
            'search_query': query,
            'search_location': location,
            'page_number': page_num,
        }
        
        # Job key - try multiple methods
        job_key = None
        job_url = None
        
        # Method 1: data-jk attribute on the card itself
        try:
            job_key = element.get_attribute('data-jk')
        except:
            pass
        
        # Method 2: data-jk on anchor tag
        if not job_key:
            try:
                link = element.find_element(By.CSS_SELECTOR, 'a[data-jk]')
                job_key = link.get_attribute('data-jk')
            except:
                pass
        
        # Method 3: data-jk on h2 > a
        if not job_key:
            try:
                link = element.find_element(By.CSS_SELECTOR, 'h2.jobTitle a')
                job_key = link.get_attribute('data-jk')
            except:
                pass
        
        # Method 4: Extract from href
        if not job_key:
            try:
                link = element.find_element(By.CSS_SELECTOR, 'a[href*="jk="]')
                href = link.get_attribute('href')
                if href:
                    # Parse jk from URL
                    if 'jk=' in href:
                        job_key = href.split('jk=')[1].split('&')[0]
                    job_url = href
            except:
                pass
        
        # Method 5: Any anchor with viewjob
        if not job_key and not job_url:
            try:
                link = element.find_element(By.CSS_SELECTOR, 'a[href*="viewjob"]')
                href = link.get_attribute('href')
                if href:
                    job_url = href
                    if 'jk=' in href:
                        job_key = href.split('jk=')[1].split('&')[0]
            except:
                pass
        
        # Method 6: Title link href
        if not job_key and not job_url:
            try:
                title_link = element.find_element(By.CSS_SELECTOR, 'h2.jobTitle a')
                href = title_link.get_attribute('href')
                if href:
                    job_url = href
                    if 'jk=' in href:
                        job_key = href.split('jk=')[1].split('&')[0]
            except:
                pass
        
        # Method 7: data-mobtk or data-ci attributes (alternative identifiers)
        if not job_key:
            try:
                job_key = element.get_attribute('data-mobtk')
            except:
                pass
        
        if not job_key:
            try:
                job_key = element.get_attribute('id')
                if job_key and job_key.startswith('job_'):
                    job_key = job_key.replace('job_', '')
            except:
                pass
        
        job_data['job_key'] = job_key if job_key else "Not Available"
        
        # Build URL
        if job_key:
            job_data['url'] = f"https://www.indeed.com/viewjob?jk={job_key}"
        elif job_url:
            job_data['url'] = job_url
        else:
            job_data['url'] = "Not Available"
        
        # Title
        try:
            title_elem = element.find_element(By.CSS_SELECTOR, 'h2.jobTitle span[title]')
            job_data['title'] = title_elem.get_attribute('title')
        except:
            try:
                title_elem = element.find_element(By.CSS_SELECTOR, 'h2.jobTitle a')
                job_data['title'] = title_elem.text.strip()
            except:
                try:
                    title_elem = element.find_element(By.CSS_SELECTOR, 'h2.jobTitle')
                    job_data['title'] = title_elem.text.strip()
                except:
                    job_data['title'] = "Not Available"
        
        # Company
        try:
            company_elem = element.find_element(By.CSS_SELECTOR, 'span[data-testid="company-name"]')
            job_data['company'] = company_elem.text.strip()
        except:
            try:
                company_elem = element.find_element(By.CSS_SELECTOR, '.companyName')
                job_data['company'] = company_elem.text.strip()
            except:
                try:
                    company_elem = element.find_element(By.CSS_SELECTOR, '[data-testid="company-name"]')
                    job_data['company'] = company_elem.text.strip()
                except:
                    job_data['company'] = "Not Available"
        
        # Location
        try:
            location_elem = element.find_element(By.CSS_SELECTOR, 'div[data-testid="text-location"]')
            job_data['location'] = location_elem.text.strip()
        except:
            try:
                location_elem = element.find_element(By.CSS_SELECTOR, '.companyLocation')
                job_data['location'] = location_elem.text.strip()
            except:
                job_data['location'] = "Not Available"
        
        # Salary - try multiple selectors and regex fallback
        job_data['salary'] = self._extract_salary(element)
        
        # Snippet/Description - try multiple selectors
        job_data['snippet'] = self._extract_snippet(element)
        
        # Posted date - try multiple selectors
        job_data['posted'] = self._extract_posted_date(element)
        
        return job_data
    
    def _extract_salary(self, element):
        """
        Extract salary from job card using multiple methods.
        Indeed frequently changes their HTML structure, so we try many selectors.
        
        Args:
            element: Selenium element of the job card
            
        Returns:
            str: Salary text or "Not Available"
        """
        # List of CSS selectors to try (in order of specificity)
        salary_selectors = [
            'div[data-testid="attribute_snippet_testid"]',
            'div.salary-snippet-container',
            'div.salaryOnly',
            'div.metadata.salary-snippet-container',
            '.salary-snippet',
            '.salaryText',
            'div.metadataContainer div.metadata',
            'div.metadata.estimated-salary',
            'div[class*="salary"]',
            'span[class*="salary"]',
            'div.metadata',
            'div.heading6 div',
            'td.resultContent div div',
        ]
        
        for selector in salary_selectors:
            try:
                elems = element.find_elements(By.CSS_SELECTOR, selector)
                for elem in elems:
                    text = elem.text.strip()
                    if text and self._looks_like_salary(text):
                        # Take first line only (avoid extra metadata)
                        return text.split('\n')[0].strip()
            except:
                continue
        
        # Fallback: regex search entire card text
        try:
            card_text = element.text
            salary = self._extract_salary_regex(card_text)
            if salary:
                return salary
        except:
            pass
        
        return "Not Available"
    
    def _looks_like_salary(self, text):
        """
        Check if text looks like a salary string.
        
        Args:
            text (str): Text to check
            
        Returns:
            bool: True if text appears to be salary
        """
        if not text:
            return False
        
        text_lower = text.lower()
        
        # Must contain dollar sign or salary keywords
        has_dollar = '$' in text
        has_salary_keyword = any(kw in text_lower for kw in [
            'year', 'hour', 'month', 'week', '/yr', '/hr', 'annually', 'per '
        ])
        
        # Exclude non-salary text that might match
        exclude_patterns = [
            'posted', 'ago', 'apply', 'easily', 'active', 'hiring',
            'employer', 'urgently', 'responded', 'applications'
        ]
        has_exclude = any(ex in text_lower for ex in exclude_patterns)
        
        return (has_dollar or has_salary_keyword) and not has_exclude
    
    def _extract_salary_regex(self, text):
        """
        Extract salary using regex patterns.
        
        Args:
            text (str): Full text to search
            
        Returns:
            str: Extracted salary or None
        """
        import re
        
        # Pattern for salary ranges like "$140,800 - $184,000 a year"
        patterns = [
            r'\$[\d,]+(?:\.\d{2})?\s*-\s*\$[\d,]+(?:\.\d{2})?\s*(?:a|an|per)?\s*(?:year|hour|month|week)',
            r'\$[\d,]+(?:\.\d{2})?\s*(?:a|an|per)?\s*(?:year|hour|month|week)',
            r'\$[\d,]+(?:\.\d{2})?\s*-\s*\$[\d,]+(?:\.\d{2})?',
            r'\$[\d,]+(?:K)?\s*-\s*\$[\d,]+(?:K)?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        
        return None
    
    def _extract_snippet(self, element):
        """
        Extract job description snippet from card.
        
        Args:
            element: Selenium element of the job card
            
        Returns:
            str: Snippet text or "Not Available"
        """
        snippet_selectors = [
            'div.job-snippet',
            '.job-snippet',
            'div[class*="job-snippet"]',
            'div.jobsearch-JobComponent-description',
            'div[data-testid="jobDescriptionText"]',
            'ul.css-kyg8or',  # Benefits list sometimes shown
            'div.metadata.css-5zy3wz',
            'table.jobCardShelfContainer td',
            'div.underShelfFooter',
        ]
        
        for selector in snippet_selectors:
            try:
                elems = element.find_elements(By.CSS_SELECTOR, selector)
                for elem in elems:
                    text = elem.text.strip()
                    # Filter out non-snippet content
                    if text and len(text) > 20:
                        # Exclude salary-like or date-like text
                        if not self._looks_like_salary(text) and 'posted' not in text.lower():
                            return text[:300]  # Limit to 300 chars
            except:
                continue
        
        return "Not Available"
    
    def _extract_posted_date(self, element):
        """
        Extract posted date from job card.
        
        Args:
            element: Selenium element of the job card
            
        Returns:
            str: Posted date or "Not Available"
        """
        date_selectors = [
            'span.date',
            'span[data-testid="myJobsStateDate"]',
            'span.css-qvloho',
            'span[class*="date"]',
            'div.metadata span',
            'span.underShelfFooter',
        ]
        
        for selector in date_selectors:
            try:
                elems = element.find_elements(By.CSS_SELECTOR, selector)
                for elem in elems:
                    text = elem.text.strip().lower()
                    # Check if text looks like a date
                    if any(kw in text for kw in ['posted', 'ago', 'day', 'hour', 'week', 'month', 'just', 'today', 'active']):
                        return elem.text.strip()
            except:
                continue
        
        # Fallback: search card text for date pattern
        try:
            card_text = element.text.lower()
            import re
            # Match patterns like "Posted 3 days ago", "Just posted", "Active 2 days ago"
            date_patterns = [
                r'posted\s+\d+\s+(?:day|hour|week|month)s?\s+ago',
                r'just\s+posted',
                r'today',
                r'active\s+\d+\s+(?:day|hour|week|month)s?\s+ago',
                r'\d+\s+(?:day|hour|week|month)s?\s+ago',
            ]
            for pattern in date_patterns:
                match = re.search(pattern, card_text)
                if match:
                    return match.group(0).title()
        except:
            pass
        
        return "Not Available"
    
    def _take_page_screenshot(self, page_num, query, session_ts):
        """
        Take a screenshot of the entire page.
        
        Args:
            page_num (int): Current page number
            query (str): Search query
            session_ts (str): Session timestamp
            
        Returns:
            Path: Screenshot file path
        """
        try:
            # Sanitize query for filename
            safe_query = re.sub(r'[^\w\s-]', '', query).strip().replace(' ', '_')[:30]
            timestamp = datetime.now().strftime("%H%M%S")
            
            filename = f"page{page_num:02d}_{safe_query}_{session_ts}_{timestamp}.png"
            filepath = self.pages_dir / filename
            
            self.sb.save_screenshot(str(filepath))
            print(f"  [Screenshot] Page saved: {filename}")
            
            return filepath
        except Exception as e:
            print(f"  [!] Screenshot error: {e}")
            return None
    
    def _take_job_screenshot(self, element, page_num, job_num, title, job_key, session_ts):
        """
        Take a screenshot of a specific job card.
        
        Naming format: page{N}_job{M}_{title}_{job_key}_{timestamp}.png
        This allows cross-referencing with JSON output.
        
        Args:
            element: Selenium element of the job card
            page_num (int): Current page number
            job_num (int): Job number in results
            title (str): Job title
            job_key (str): Indeed job key
            session_ts (str): Session timestamp
            
        Returns:
            Path: Screenshot file path
        """
        try:
            # Scroll element into view
            self.sb.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            self._human_delay(0.3, 0.5)
            
            # Sanitize title for filename
            safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')[:25]
            safe_key = job_key if job_key not in ["N/A", "Not Available"] else "nokey"
            timestamp = datetime.now().strftime("%H%M%S")
            
            filename = f"page{page_num:02d}_job{job_num:03d}_{safe_title}_{safe_key}_{timestamp}.png"
            filepath = self.cards_dir / filename
            
            # Take screenshot of element
            element.screenshot(str(filepath))
            
            return filepath
        except Exception as e:
            # Fallback to full page screenshot
            try:
                safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')[:25]
                timestamp = datetime.now().strftime("%H%M%S")
                filename = f"page{page_num:02d}_job{job_num:03d}_{safe_title}_full_{timestamp}.png"
                filepath = self.cards_dir / filename
                self.sb.save_screenshot(str(filepath))
                return filepath
            except:
                return None
    
    def _human_delay(self, min_seconds=1, max_seconds=3):
        """Random human-like delay."""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def close(self):
        """Close browser and cleanup."""
        try:
            if self._sb_context:
                self._sb_context.__exit__(None, None, None)
                print("[*] SeleniumBase browser closed")
        except Exception as e:
            print(f"[!] Error closing browser: {e}")


if __name__ == "__main__":
    pass