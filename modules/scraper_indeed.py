#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""SeleniumBase UC Mode Scraper - Cloudflare bypass with cookie authentication (REFACTORED)

This refactored version addresses the following issues:
    1. Replaced all bare except clauses with specific exception handling
    2. Implemented proper logging instead of print statements
    3. Improved separation of concerns
    4. Ensured consistent return types across all functions
    5. Moved error handling to outer layers
    6. Fixed commented out imports and used specific exceptions
    7. Improved code modularity and testability

Features:
    - UC Mode: Undetected ChromeDriver evading bot detection
    - CDP Events: Low-level Chrome DevTools Protocol control
    - Auto CAPTCHA: Turnstile/Cloudflare challenge solving
    - Reconnection: Evade fingerprinting after actions
    - Screenshots: Page and job card capture for verification
"""

import re
import time
import pickle
import random
import logging
from pathlib import Path
from seleniumbase import SB
from datetime import datetime
from urllib.parse import quote_plus
from modules.cfg import get_base_url
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (TimeoutException, NoSuchElementException, WebDriverException)

# __ configure logging:
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# __ global vars:
DEFAULT_DELAY_MIN = 1
DEFAULT_DELAY_MAX = 3
PAGE_DELAY_MIN = 2
PAGE_DELAY_MAX = 4
CLOUDFLARE_DELAY = 3
RECONNECT_TIMEOUT = 3
NOT_AVAILABLE = "Not Available"
MAX_SNIPPET_LENGTH = 300
MAX_CONSECUTIVE_FAILURES = 2
BASE_URL = get_base_url(jb_board="indeed")

class SeleniumBaseIndeedScraper:
    """Indeed scraper using SeleniumBase UC Mode for Cloudflare bypass:
        UC Mode advantages:
            - Runtime ChromeDriver patching to avoid detection:
            - Removes automation flags Cloudflare checks:
            - Built-in CAPTCHA solver for Turnstile challenges:
            - Reconnection strategy to evade fingerprinting: """
    
    def __init__(self, headless=False, incognito=False, window_size="maximized", proxy=None, screenshots=False, artifacts_dir=None, cookie_file=None):
        """Initialize SeleniumBase scraper in UC Mode:
            Args:
                headless (bool):        <-- Run headless (uses xvfb on Linux)
                incognito (bool):       <-- Use incognito mode:
                window_size (str):      <-- "maximized" or "WIDTHxHEIGHT"
                proxy (dict):           <-- Proxy config {'server': '...', 'username': '...', 'password': '...'}
                screenshots (bool):     <-- Enable screenshot capture:
                artifacts_dir (Path):   <-- Base artifacts directory:
                cookie_file (str):      <-- Path to cookie file: """
        
        self.window_size = window_size
        self.screenshots = screenshots
        self.cookie_file = cookie_file
        self.incognito = incognito
        self.headless = headless
        self.proxy = proxy
        self.driver = None
        self.sb = None
        
        # __ setup screenshot directories:
        if artifacts_dir:
            self.artifacts_dir = Path(artifacts_dir)
        else:
            self.artifacts_dir = Path(__file__).parent.parent / "artifacts"

        self.screenshots_dir = self.artifacts_dir / "screenshots"
        self.pages_dir = self.screenshots_dir / "pages"
        self.cards_dir = self.screenshots_dir / "cards"
        
        if self.screenshots:
            self.pages_dir.mkdir(parents=True, exist_ok=True)
            self.cards_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Page screenshots: {self.pages_dir}")
            logger.info(f"Card screenshots: {self.cards_dir}")
        
        self._start_browser()
        
        # __ load cookies if provided:
        if self.cookie_file:
            self._load_cookies_from_file()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def _start_browser(self):
        """ Start SeleniumBase browser in UC Mode: """
        logger.info("Starting SeleniumBase UC Mode browser...")
        
        # __ build SB options:
        sb_options = {
            'uc': True,
            'uc_cdp_events': True,
            'uc_subprocess': False,
            'incognito': self.incognito,
            'locale_code': 'en',
            'disable_csp': True,
            'block_images': False,
        }
        
        # __ headless mode - use xvfb on Linux:
        if self.headless:
            sb_options['headless'] = True
            sb_options['xvfb'] = True
        
        # __ proxy support:
        if self.proxy:
            proxy_str = self.proxy.get('server', '')
            if 'username' in self.proxy and self.proxy['username']:
                auth = f"{self.proxy['username']}:{self.proxy.get('password', '')}"
                server = proxy_str.replace('http://', '').replace('https://', '')
                proxy_str = f"{auth}@{server}"
            sb_options['proxy'] = proxy_str
        
        # __ create SB context manager:
        self._sb_context = SB(**sb_options)
        self.sb = self._sb_context.__enter__()
        self.driver = self.sb.driver
        
        # __ set window size:
        if self.window_size == "maximized":
            self.sb.maximize_window()
        else:
            try:
                width, height = map(int, self.window_size.split('x'))
                self.sb.set_window_size(width, height)
            except (ValueError, AttributeError) as e:
                logger.warning(f"Invalid window size format '{self.window_size}': {e}")
                logger.info("Falling back to maximized window")
                self.sb.maximize_window()
        
        logger.info("SeleniumBase UC Mode browser started")

    def _load_cookies_from_file(self):
        """ Load cookies from file to bypass login:
            Returns: bool:              <-- True if successful, False otherwise:
            Raises: FileNotFoundError:  <-- If cookie file doesn't exist: """
        
        cookie_path = Path(self.cookie_file)
        if not cookie_path.exists():
            logger.error(f"Cookie file not found: {cookie_path}")
            logger.info("Run cookie setup first:")
            logger.info("    python3 modules/get_cookies.py --auto")
            raise FileNotFoundError(f"Cookie file not found: {cookie_path}")
        
        logger.info(f"Loading cookies from: {cookie_path}")
        
        # __ visit Indeed first:
        self.sb.uc_open_with_reconnect(BASE_URL, reconnect_time=3)
        time.sleep(2)
        
        # __ load cookies:
        try:
            with open(cookie_path, 'rb') as f:
                cookies = pickle.load(f)
        except (IOError, OSError, pickle.UnpicklingError) as e:
            logger.error(f"Failed to load cookies from file: {e}")
            return False
        
        logger.info(f"Adding {len(cookies)} cookies ...")
        
        # __ add cookies:
        added = 0
        for cookie in cookies:
            try:
                if 'expiry' in cookie:
                    cookie['expiry'] = int(cookie['expiry'])
                cookie.pop('sameSite', None)
                self.driver.add_cookie(cookie)
                added += 1
            except (WebDriverException, ValueError, TypeError) as e:
                logger.debug(f"Failed to add cookie {cookie.get('name', 'unknown')}: {e}")
                continue
        
        logger.info(f"Added {added}/{len(cookies)} cookies")
        
        # __ refresh to apply:
        self.sb.refresh()
        time.sleep(2)
        
        # __ verify login:
        if self._is_logged_in():
            logger.info("Successfully logged in via cookies!")
            return True
        else:
            logger.warning("Cookies may be expired - refresh them")
            return False
    
    def _is_logged_in(self):
        """ Check if logged in:
            Returns: bool: <-- True if logged in: """
        try:
            page_source = self.sb.get_page_source().lower()
            current_url = self.sb.get_current_url()
            return 'sign out' in page_source or ('account' in page_source and 'auth' not in current_url)
        except WebDriverException as e:
            logger.debug(f"Error checking login status: {e}")
            return False

    def search_jobs(self, query, location="", remote_only=False, min_salary=None, max_salary=None, date_posted=None, max_results=25):
        """ Search Indeed jobs with UC Mode Cloudflare bypass:
            Args:
                query (str):        <-- Job search query:
                location (str):     <-- Job location
                remote_only (bool): <-- Filter remote jobs only
                min_salary (int):   <-- Minimum salary
                max_salary (int):   <-- Maximum salary
                date_posted (int):  <-- Days filter (1, 3, 7, 14)
                max_results (int):  <-- Maximum results to return
            Returns: list:          <-- Job dictionaries, or empty list if no jobs found: """
        
        base_url = self._build_search_url(query, location, remote_only, min_salary, max_salary, date_posted)
        all_jobs = []
        page_num = 0
        consecutive_failures = 0
        session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        while len(all_jobs) < max_results and consecutive_failures < MAX_CONSECUTIVE_FAILURES:
            url = f"{base_url}&start={page_num * 10}" if page_num > 0 else base_url
            logger.info(f"\nPage {page_num + 1}: {url}")
            try:
                # __ navigate with UC mode:
                self.sb.uc_open_with_reconnect(url, reconnect_time=5)
                self._human_delay(PAGE_DELAY_MIN, PAGE_DELAY_MAX)
                
                # __ handle Cloudflare if present:
                if self._handle_cloudflare():
                    logger.info("Cloudflare challenge handled")
                    self.sb.reconnect(timeout=RECONNECT_TIMEOUT)
                    self._human_delay(PAGE_DELAY_MIN, CLOUDFLARE_DELAY)
                
                # __ wait for job cards:
                if not self._wait_for_job_listings():
                    consecutive_failures += 1
                    if self._is_cloudflare_challenge():
                        logger.warning("Still blocked by Cloudflare - retrying...")
                        self._handle_cloudflare()
                    self._human_delay(5, 10)
                    continue
                
                # __ take page screenshot:
                if self.screenshots:
                    self._take_page_screenshot(page_num + 1, query, session_ts)
                
                # __ extract jobs from page:
                # page_jobs = self._extract_jobs_from_page(all_jobs, max_results, query, location, page_num, session_ts)
                page_jobs, total_cards = self._extract_jobs_from_page(all_jobs, max_results, query, location, page_num, session_ts)
                
                if page_jobs == 0:
                    logger.warning("No new jobs on this page")
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0
                
                # __ stop if mostly duplicates (indicates end of results):
                if total_cards > 0:
                    duplicate_rate = (total_cards - page_jobs) / total_cards
                    if duplicate_rate > 0.8 and page_jobs < 3:
                        logger.info(f"High duplicate rate ({duplicate_rate:.0%}) - likely end of results")
                        consecutive_failures += 1
                
                if len(all_jobs) >= max_results:
                    break
                
                # __ reconnect before pagination:
                logger.info("Reconnecting before next page...")
                self.sb.reconnect(timeout=2)
                self._human_delay(4, 8)
                page_num += 1
                
            except WebDriverException as e:
                logger.error(f"WebDriver error on page {page_num + 1}: {e}")
                consecutive_failures += 1
                self._human_delay(5, 10)
            except Exception as e:
                logger.error(f"Unexpected error on page {page_num + 1}: {e}")
                consecutive_failures += 1
                self._human_delay(5, 10)
        
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.warning(f"Stopped after {MAX_CONSECUTIVE_FAILURES} consecutive failures")
        
        return all_jobs
    
    def _build_search_url(self, query, location, remote_only, min_salary, max_salary, date_posted):
        """ Build Indeed search url with parameters:
            Args:
                query (str):        <-- Job search query:
                location (str):     <-- Job location:
                remote_only (bool): <-- Filter remote jobs only:
                min_salary (int):   <-- Minimum salary:
                max_salary (int):   <-- Maximum salary:
                date_posted (int):  <-- Days filter:
            Returns: str:           <-- Complete search url: """
        
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
        
        return f"{BASE_URL}/jobs?{'&'.join(params)}"
    
    def _wait_for_job_listings(self):
        """ Wait for job listings to appear on page:
            Returns: bool: <-- True if job listings found, False otherwise: """
        try:
            self.sb.wait_for_element('div.job_seen_beacon', timeout=15)
            return True
        except TimeoutException:
            logger.debug("Primary job card selector timed out, trying alternative...")
            try:
                self.sb.wait_for_element('[data-testid="jobsearch-ResultsList"]', timeout=10)
                return True
            except TimeoutException:
                logger.warning("Could not find job listings")
                return False
    
    def _extract_jobs_from_page(self, all_jobs, max_results, query, location, page_num, session_ts):
        """ Extract all jobs from current page:
            Args:
                all_jobs (list):    <-- Existing list of jobs:
                max_results (int):  <-- Maximum total results:
                query (str):        <-- Search query:
                location (str):     <-- Search location:
                page_num (int):     <-- Current page number:
                session_ts (str):   <-- Session timestamp:
            Returns: tuple:         <-- (page_jobs, total_cards) - new jobs added and total cards found:"""
            # Returns: int:           <-- Number of jobs extracted from this page:"""
        
        job_cards = self.sb.find_elements('div.job_seen_beacon')
        if not job_cards:
            job_cards = self.sb.find_elements('div.jobsearch-ResultsList > div')
        
        logger.info(f"Found {len(job_cards)} job cards")
        
        page_jobs = 0
        for idx, card in enumerate(job_cards):
            if len(all_jobs) >= max_results:
                break
            
            try:
                job_data = self._extract_job_from_element(card, query, location, page_num + 1)
                
                # __ check duplicates:
                if self._is_duplicate_job(job_data, all_jobs):
                    continue
                
                if job_data['title'] != NOT_AVAILABLE:
                    # __ take job screenshot:
                    if self.screenshots:
                        screenshot_path = self._take_job_screenshot(
                            card, page_num + 1, len(all_jobs) + 1, job_data['title'], job_data['job_key'], session_ts)
                        job_data['screenshot'] = str(screenshot_path) if screenshot_path else NOT_AVAILABLE
                    
                    all_jobs.append(job_data)
                    page_jobs += 1
                    title_short = job_data['title'][:50]
                    url_short = job_data['url'][:60] if job_data['url'] != NOT_AVAILABLE else 'No URL'
                    logger.info(f"  [{len(all_jobs)}] {title_short} | {url_short}")
            
            except (NoSuchElementException, WebDriverException) as e:
                logger.debug(f"Error parsing job card: {e}")
                continue
        
        # return page_jobs
        return page_jobs, len(job_cards)
    
    def _is_duplicate_job(self, job_data, all_jobs):
        """ Check if job is a duplicate:
            Args:   job_data (dict): <-- Job data to check:
                    all_jobs (list): <-- Existing jobs list:
            Returns: bool:           <-- True if duplicate: """
        
        if job_data['job_key'] != NOT_AVAILABLE:
            return any(j['job_key'] == job_data['job_key'] for j in all_jobs)
        elif job_data['url'] != NOT_AVAILABLE:
            return any(j['url'] == job_data['url'] for j in all_jobs)
        return False

    def _handle_cloudflare(self):
        """ Handle Cloudflare challenge using UC Mode:
            Returns: bool: <-- True if challenge was detected and handled: """
        
        if not self._is_cloudflare_challenge():
            return False
        
        logger.info("Cloudflare challenge detected - attempting bypass ...")
        
        # __ method - 1: Built-in CAPTCHA clicker:
        if self._try_auto_click_captcha():
            return True
        
        # __ method - 2: Manual iframe checkbox:
        if self._try_iframe_checkbox():
            return True
        
        # __ method - 3: Wait for manual intervention:
        return self._wait_for_manual_solve()
    
    def _try_auto_click_captcha(self):
        """ Try to auto-click Cloudflare CAPTCHA:
            Returns: bool: <-- True if successful: """
        try:
            self.sb.uc_gui_click_captcha()
            logger.info("Clicked Cloudflare checkbox")
            self._human_delay(CLOUDFLARE_DELAY, 5)
            
            if not self._is_cloudflare_challenge():
                logger.info("Cloudflare challenge solved!")
                return True
        except WebDriverException as e:
            logger.debug(f"Auto-click failed: {e}")
        
        return False
    
    def _try_iframe_checkbox(self):
        """ Try to click checkbox in Cloudflare iframe:
            Returns: bool: <-- True if successful:"""
        
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
                            logger.info("Clicked Turnstile checkbox in iframe")
                            self._human_delay(CLOUDFLARE_DELAY, 5)
                    except NoSuchElementException:
                        pass
                    finally:
                        self.sb.switch_to_default_content()
            
            if not self._is_cloudflare_challenge():
                logger.info("Cloudflare challenge solved!")
                return True
        except WebDriverException as e:
            logger.debug(f"Iframe method failed: {e}")
        
        return False
    
    def _wait_for_manual_solve(self):
        """ Wait for manual Cloudflare challenge solution:
            Returns: bool: <-- True if solved within timeout:"""
        
        logger.warning("\n" + "=" * 60)
        logger.warning("MANUAL INTERVENTION REQUIRED")
        logger.warning("=" * 60)
        logger.warning("Cloudflare challenge could not be auto-solved.")
        logger.warning("Please solve it manually in the browser.")
        logger.warning("=" * 60)
        
        for wait_iteration in range(12):
            self._human_delay(5, 5)
            if not self._is_cloudflare_challenge():
                logger.info("Challenge solved manually!")
                return True
            logger.info(f"Waiting... ({(wait_iteration + 1) * 5}s)")
        
        logger.error("Cloudflare challenge timeout")
        logger.error("=" * 60)
        return True
    
    def _is_cloudflare_challenge(self):
        """ Check if current page is Cloudflare challenge:
            Returns: bool: <-- True if Cloudflare challenge detected:"""
        
        try:
            title = self.sb.get_title().lower()
            page_source = self.sb.get_page_source().lower()
            
            indicators = [
                'just a moment' in title,
                'cloudflare' in title,
                'verify you are human' in page_source,
                'checking your browser' in page_source,
                'challenges.cloudflare.com' in page_source,
                'cf-turnstile' in page_source,
            ]
            
            return any(indicators)
        except WebDriverException as e:
            logger.debug(f"Error checking Cloudflare challenge: {e}")
            return False

    def _extract_job_from_element(self, element, query, location, page_num):
        """ Extract job data from Selenium element:
            Args:
                element:        <-- Selenium WebElement of job card:
                query (str):    <-- Search query:
                location (str): <-- Search location:
                page_num (int): <-- Page number:
            Returns: dict:      <-- Job data: """
        
        job_data = {
            'scraped_at': datetime.now().isoformat(),
            'search_query': query,
            'search_location': location,
            'page_number': page_num,
        }
        
        # __ extract job key and url:
        job_key, job_url = self._extract_job_key_and_url(element)
        job_data['job_key'] = job_key if job_key else NOT_AVAILABLE
        
        # __ build url:
        if job_key:
            job_data['url'] = f"{BASE_URL}/viewjob?jk={job_key}"
        elif job_url:
            job_data['url'] = job_url
        else:
            job_data['url'] = NOT_AVAILABLE
        
        # __ extract other fields:
        job_data['title'] = self._extract_title(element)
        job_data['company'] = self._extract_company(element)
        job_data['location'] = self._extract_location(element)
        job_data['salary'] = self._extract_salary(element)
        job_data['snippet'] = self._extract_snippet(element)
        job_data['posted'] = self._extract_posted_date(element)
        
        return job_data
    
    def _extract_job_key_and_url(self, element):
        """ Extract job key and URL from element:
            Args: element:  <-- Selenium WebElement:
            Returns: tuple: <-- (job_key, job_url) or (None, None):"""
        
        job_key = None
        job_url = None
        
        # __ try multiple extraction methods:
        extraction_methods = [
            lambda: element.get_attribute('data-jk'),
            lambda: element.find_element(By.CSS_SELECTOR, 'a[data-jk]').get_attribute('data-jk'),
            lambda: element.find_element(By.CSS_SELECTOR, 'h2.jobTitle a').get_attribute('data-jk'),
        ]
        
        for method in extraction_methods:
            try:
                job_key = method()
                if job_key:
                    return job_key, None
            except (NoSuchElementException, WebDriverException):
                continue
        
        # __ extract from href:
        href_selectors = [
            'a[href*="jk="]',
            'a[href*="viewjob"]',
            'h2.jobTitle a'
        ]
        
        for selector in href_selectors:
            try:
                link = element.find_element(By.CSS_SELECTOR, selector)
                href = link.get_attribute('href')
                if href:
                    job_url = href
                    if 'jk=' in href:
                        job_key = href.split('jk=')[1].split('&')[0]
                        return job_key, job_url
            except (NoSuchElementException, WebDriverException):
                continue
        
        # __ try alternative attributes:
        try:
            job_key = element.get_attribute('data-mobtk') or element.get_attribute('id')
            if job_key and job_key.startswith('job_'):
                job_key = job_key.replace('job_', '')
        except WebDriverException:
            pass
        
        return job_key, job_url
    
    def _extract_title(self, element):
        """ Extract job title:
            Args: element:  <-- Selenium WebElement:
            Returns: str:   <-- Job title or NOT_AVAILABLE: """
        
        selectors = [
            'h2.jobTitle span[title]',
            'h2.jobTitle a',
            'h2.jobTitle'
        ]
        
        for selector in selectors:
            try:
                elem = element.find_element(By.CSS_SELECTOR, selector)
                if selector == 'h2.jobTitle span[title]':
                    return elem.get_attribute('title')
                return elem.text.strip()
            except (NoSuchElementException, WebDriverException):
                continue
        return NOT_AVAILABLE
    
    def _extract_company(self, element):
        """ Extract company name:
            Args: element:  <-- Selenium WebElement:
            Returns: str:   <-- Company name or NOT_AVAILABLE: """
        
        selectors = [
            'span[data-testid="company-name"]',
            '.companyName',
            '[data-testid="company-name"]'
        ]
        
        for selector in selectors:
            try:
                elem = element.find_element(By.CSS_SELECTOR, selector)
                return elem.text.strip()
            except (NoSuchElementException, WebDriverException):
                continue
        return NOT_AVAILABLE
    
    def _extract_location(self, element):
        """ Extract job location:
            Args: element:  <-- Selenium WebElement:
            Returns: str:   <-- Job location or NOT_AVAILABLE: """
        
        selectors = [
            'div[data-testid="text-location"]',
            '.companyLocation'
        ]
        
        for selector in selectors:
            try:
                elem = element.find_element(By.CSS_SELECTOR, selector)
                return elem.text.strip()
            except (NoSuchElementException, WebDriverException):
                continue
        return NOT_AVAILABLE
    
    def _extract_salary(self, element):
        """ Extract salary from job card:
            Args: element:  <-- Selenium WebElement:
            Returns: str:   <-- Salary text or NOT_AVAILABLE:"""
        
        salary_selectors = [
            'div[data-testid="attribute_snippet_testid"]',
            'div.salary-snippet-container',
            'div.salaryOnly',
            '.salary-snippet',
            '.salaryText',
            'div.metadata',
            'div[class*="salary"]',
        ]
        
        for selector in salary_selectors:
            try:
                elems = element.find_elements(By.CSS_SELECTOR, selector)
                for elem in elems:
                    text = elem.text.strip()
                    if text and self._looks_like_salary(text):
                        return text.split('\n')[0].strip()
            except (NoSuchElementException, WebDriverException):
                continue
        
        # __ Regex fallback:
        try:
            salary = self._extract_salary_regex(element.text)
            if salary:
                return salary
        except WebDriverException:
            pass
        
        return NOT_AVAILABLE
    
    def _looks_like_salary(self, text):
        """ Check if text looks like salary:
            Args: text (str):   <-- Text to check:
            Returns: bool:      <-- True if appears to be salary: """
        
        if not text:
            return False
        
        text_lower = text.lower()
        has_dollar = '$' in text
        has_salary_keyword = any(kw in text_lower for kw in ['year', 'hour', 'month', 'week', '/yr', '/hr', 'annually', 'per '])
        exclude_patterns = ['posted', 'ago', 'apply', 'easily', 'active', 'hiring']
        has_exclude = any(ex in text_lower for ex in exclude_patterns)
        return (has_dollar or has_salary_keyword) and not has_exclude
    
    def _extract_salary_regex(self, text):
        """ Extract salary using regex patterns:
            Args: text (str):   <-- Full text to search:            
            Returns: str:       <-- Extracted salary or None: """
        
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
        """ Extract job description snippet:
            Args: element:  <-- Selenium WebElement:
            Returns: str:   <-- Snippet text or NOT_AVAILABLE:"""
        
        selectors = [
            'div.job-snippet',
            'div[class*="job-snippet"]',
            'div.jobsearch-JobComponent-description',
            'ul.css-kyg8or',
            'table.jobCardShelfContainer td',
        ]
        
        for selector in selectors:
            try:
                elems = element.find_elements(By.CSS_SELECTOR, selector)
                for elem in elems:
                    text = elem.text.strip()
                    if text and len(text) > 20:
                        if not self._looks_like_salary(text) and 'posted' not in text.lower():
                            return text[:MAX_SNIPPET_LENGTH]
            except (NoSuchElementException, WebDriverException):
                continue
        return NOT_AVAILABLE
    
    def _extract_posted_date(self, element):
        """ Extract posted date:
            Args: element:  <-- Selenium WebElement:
            Returns: str:   <-- Posted date or NOT_AVAILABLE:"""
        
        selectors = [
            'span.date',
            'span[data-testid="myJobsStateDate"]',
            'span[class*="date"]',
            'div.metadata span',
        ]
        
        for selector in selectors:
            try:
                elems = element.find_elements(By.CSS_SELECTOR, selector)
                for elem in elems:
                    text = elem.text.strip().lower()
                    if any(kw in text for kw in ['posted', 'ago', 'day', 'hour', 'week', 'month', 'just', 'today']):
                        return elem.text.strip()
            except (NoSuchElementException, WebDriverException):
                continue
        
        # __ Regex fallback:
        try:
            card_text = element.text.lower()
            patterns = [
                r'posted\s+\d+\s+(?:day|hour|week|month)s?\s+ago',
                r'just\s+posted',
                r'today',
                r'\d+\s+(?:day|hour|week|month)s?\s+ago',
            ]
            for pattern in patterns:
                match = re.search(pattern, card_text)
                if match:
                    return match.group(0).title()
        except WebDriverException:
            pass
        
        return NOT_AVAILABLE

    def _take_page_screenshot(self, page_num, query, session_ts):
        """ Take screenshot of entire page:
            Args: page_num (int):   <-- Page number:
                  query (str):      <-- Search query:
                  session_ts (str): <-- Session timestamp:
            Returns: Path:          <-- Screenshot file path or None:"""
        
        try:
            safe_query = re.sub(r'[^\w\s-]', '', query).strip().replace(' ', '_')[:30]
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"page{page_num:02d}_{safe_query}_{session_ts}_{timestamp}.png"
            filepath = self.pages_dir / filename
            
            self.sb.save_screenshot(str(filepath))
            logger.info(f"  [Screenshot] Page: {filename}")
            return filepath
        except WebDriverException as e:
            logger.warning(f"Screenshot error: {e}")
            return None
    
    def _take_job_screenshot(self, element, page_num, job_num, title, job_key, session_ts):
        """ Take screenshot of job card:
            Args:
                element:            <-- Selenium WebElement:
                page_num (int):     <-- Page number:
                job_num (int):      <-- Job number:
                title (str):        <-- Job title:
                job_key (str):      <-- Job key:
                session_ts (str):   <-- Session timestamp:
            Returns: Path:          <-- Screenshot file path or None: """
        try:
            # __ scroll into view:
            self.sb.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            self._human_delay(0.3, 0.5)
            
            # __ build filename:
            safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')[:25]
            safe_key = job_key if job_key not in [NOT_AVAILABLE, "N/A"] else "nokey"
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"page{page_num:02d}_job{job_num:03d}_{safe_title}_{safe_key}_{timestamp}.png"
            filepath = self.cards_dir / filename
            
            # __ take screenshot:
            element.screenshot(str(filepath))
            return filepath
        except WebDriverException as e:
            logger.debug(f"Element screenshot failed: {e}")
            
            # __ fallback to full page:
            try:
                safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')[:25]
                timestamp = datetime.now().strftime("%H%M%S")
                filename = f"page{page_num:02d}_job{job_num:03d}_{safe_title}_full_{timestamp}.png"
                filepath = self.cards_dir / filename
                self.sb.save_screenshot(str(filepath))
                return filepath
            except WebDriverException as e2:
                logger.warning(f"Fallback screenshot failed: {e2}")
                return None
    
    def _human_delay(self, min_seconds=DEFAULT_DELAY_MIN, max_seconds=DEFAULT_DELAY_MAX):
        """ Random human-like delay:
            Args:
                min_seconds (float): <-- Minimum delay
                max_seconds (float): <-- Maximum delay: """
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def close(self):
        """ Close browser and cleanup: """
        try:
            if self._sb_context:
                self._sb_context.__exit__(None, None, None)
                logger.info("SeleniumBase browser closed")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")


if __name__ == "__main__":
    pass
