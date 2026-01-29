#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Indeed Job Scraper Module
    Handles web scraping logic for Indeed job postings: """

import time
import random
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from urllib.parse import quote_plus
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException


class IndeedJobScraper:
    """Scraper for Indeed job postings using Selenium."""
    
    def __init__(self, headless=False, incognito=False, window_size="maximized"):
        """ Initialize the scraper with browser options:
            Args:
                headless (bool):    <-- Run browser in headless mode (no GUI)
                incognito (bool):   <-- Run in incognito/private mode
                window_size (str):  <-- Window size - "maximized" or "WIDTHxHEIGHT" (e.g., "1280x720") """
        
        chrome_options = Options()
        
        # __ Incognito mode:
        if incognito:
            chrome_options.add_argument('--incognito')
            print("🕶️  Running in incognito mode")
        
        # __ Window size for headless or specific size:
        if headless:
            if window_size == "maximized":
                chrome_options.add_argument('--window-size=1920,1080')
            else:
                chrome_options.add_argument(f'--window-size={window_size.replace("x", ",")}')
        
        # __ Enhanced anti-detection options:
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # __ Additional anti-detection:
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=IsolateOrigins,site-per-process')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--start-maximized')
        
        # __ Language and location:
        chrome_options.add_argument('--lang=en-US')
        chrome_options.add_experimental_option('prefs', {
            'intl.accept_languages': 'en-US,en',
            'profile.default_content_setting_values.notifications': 2
        })
        
        if headless:
            chrome_options.add_argument('--headless=new')  # Use new headless mode
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--window-size=1920,1080')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        
        # __ Set window size if not headless:
        if not headless:
            if window_size == "maximized":
                self.driver.maximize_window()
            else:
                # __ Parse custom size (e.g., "1280x720"):
                try:
                    width, height = map(int, window_size.split('x'))
                    self.driver.set_window_size(width, height)
                except (ValueError, AttributeError) as e:
                    print(f"\tInvalid window size '{window_size}', maximizing instead: {e}\n")
                    self.driver.maximize_window()
        
        self.wait = WebDriverWait(self.driver, 15)
        
        # __ Enhanced anti-detection: Override navigator properties:
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            "platform": "MacIntel",
            "acceptLanguage": "en-US,en;q=0.9"
        })
        
        # __ Remove webdriver flag:
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # __ Override permissions:
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                Object.defineProperty(navigator, 'permissions', {
                    get: () => ({
                        query: () => Promise.resolve({state: 'prompt'})
                    })
                });
                window.chrome = {
                    runtime: {}
                };
            '''
        })
    
    def login(self, email, password):
        """ Login to Indeed with credentials:
            Args:
                email (str):    <-- Indeed account email:
                password (str): <-- Indeed account password:
            Returns: bool:      <-- True if login successful, False otherwise: """
        print("Navigating to Indeed login page...")
        self.driver.get("https://secure.indeed.com/account/login")
        
        time.sleep(3)
        
        try:
            print("Entering email...")
            email_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
            )
            email_input.clear()
            email_input.send_keys(email)
            
            continue_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            continue_btn.click()
            
            time.sleep(3)
            
            # __ Check for Google auth:
            try:
                self.driver.find_element(By.CSS_SELECTOR, "button[data-tn-element='google-auth-button']")
                print("\nGoogle authentication detected!")
                print("Click 'Sign in with email and password' or use Google auth")
                input("\nComplete authentication, then press Enter...")
                time.sleep(2)
            except NoSuchElementException:
                pass
            
            # __ password field:
            try:
                print("Entering password...")
                password_input = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
                )
                password_input.clear()
                password_input.send_keys(password)
                
                signin_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                signin_btn.click()
                
                time.sleep(5)
            except TimeoutException as e:
                print(f"Password field not found - alternative auth used: {e}")
            
            # __ 2FA check:
            if "verification" in self.driver.current_url.lower() or "challenge" in self.driver.current_url.lower():
                print("\n2FA/CAPTCHA detected!")
                input("Complete verification, then press Enter...")
            
            time.sleep(3)
            if "account" in self.driver.current_url or len(self.driver.get_cookies()) > 3:
                print("✓ Login successful!")
                return True
            else:
                print("\tLogin may have failed")
                return False
            
        except TimeoutException as e:
            print(f"Login timeout error: {e}")
            return False
        except NoSuchElementException as e:
            print(f"Login element not found: {e}")
            return False
        except WebDriverException as e:
            print(f"WebDriver error during login: {e}")
            return False
    
    def build_search_url(self, query, location="", remote_only=False, min_salary=None, max_salary=None, date_posted=None):
        """ Build Indeed search URL with parameters:
            Args:
                query (str):        <-- Job search query:
                location (str):     <-- Job location:
                remote_only (bool): <-- Filter for remote jobs only:
                min_salary (int):   <-- Minimum salary:
                max_salary (int):   <-- Maximum salary:
                date_posted (int):  <-- Posted within last N days (1, 3, 7, or 14):
            Returns: str:           <-- Complete search url:"""
        base_url = "https://www.indeed.com/jobs"
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
        
        url = f"{base_url}?{'&'.join(params)}"
        return url
    
    def search_jobs(self, query, location="", remote_only=False, min_salary=None, max_salary=None, date_posted=None, max_results=25, use_url_pagination=True):
        """ Search for jobs on Indeed with pagination support:
            Args:
                query (str):               <-- Job search query:
                location (str):            <-- Job location:
                remote_only (bool):        <-- Filter for remote jobs only:
                min_salary (int):          <-- Minimum salary:
                max_salary (int):          <-- Maximum salary:
                date_posted (int):         <-- Posted within last N days:
                max_results (int):         <-- Maximum number of results to scrape:
                use_url_pagination (bool): <-- Use URL parameters instead of clicking Next:
            Returns: list:                 <-- List of job dictionaries, or None if failed:"""
        base_search_url = self.build_search_url(
            query=query,
            location=location,
            remote_only=remote_only,
            min_salary=min_salary,
            max_salary=max_salary,
            date_posted=date_posted
        )
        
        all_jobs = []
        page_num = 0  # Indeed uses 0 indexed start parameter:
        
        while len(all_jobs) < max_results:
            # __ Build URL for current page:
            if use_url_pagination and page_num > 0:
                # __ Indeed uses &start=N where N = page * 10
                start = page_num * 10
                search_url = f"{base_search_url}&start={start}"
            else:
                search_url = base_search_url
            
            print(f"\nPage {page_num + 1}: {search_url}")
            
            self.driver.get(search_url)
            self._human_delay(3, 5)
            
            # __ Cloudflare challenge check:
            if self._handle_cloudflare_challenge():
                print("⚠ Cloudflare challenge detected")
                self._human_delay(8, 12)
            
            # __ page loaded check:
            try:
                self.driver.find_element(By.ID, "mosaic-provider-jobcards")
                print("✓ Page loaded successfully")
            except NoSuchElementException as e:
                page_title = self.driver.title.lower()
                if "access denied" in page_title or "captcha" in page_title:
                    print(f"✗ Blocked by Indeed: {e}")
                    self._save_debug_html()
                    if len(all_jobs) > 0:
                        return all_jobs
                    return None
                else:
                    print(f"\tNo job results found: {e}")
                    if len(all_jobs) > 0:
                        return all_jobs
                    return None
            
            # __ extract jobs from current page:
            try:
                job_cards = self.wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.job_seen_beacon"))
                )
                
                print(f"Found {len(job_cards)} job cards")
                
                page_jobs = 0
                for card in job_cards:
                    if len(all_jobs) >= max_results:
                        break
                    
                    try:
                        job_data = self._extract_job_data(card, query, location)
                        
                        # __ dups check:
                        if job_data['job_key'] != "N/A":
                            if any(j['job_key'] == job_data['job_key'] for j in all_jobs):
                                continue
                        
                        if job_data['title'] != "N/A" and job_data['url'] != "N/A":
                            all_jobs.append(job_data)
                            page_jobs += 1
                            print(f"  [{len(all_jobs)}] {job_data['title'][:60]}")
                            print(f"      {job_data['company']} - {job_data['location']}")
                            if job_data['salary'] != "N/A":
                                print(f"      Salary: {job_data['salary']}")
                    
                    except (NoSuchElementException, WebDriverException) as e:
                        print(f"  Error parsing job card: {e}")
                        continue
                
                print(f"Extracted {page_jobs} jobs from page {page_num + 1} (total: {len(all_jobs)})")
                
                # __ any jobs on page check:
                if page_jobs == 0:
                    print("No new jobs on this page - stopping")
                    break
                
                # __ enough jobs on page check:
                if len(all_jobs) >= max_results:
                    print(f"✓ Reached target of {max_results} jobs")
                    break
                
                # __ move to next page:
                page_num += 1
                
                # __ delay between pages to avoid Cloudflare triggers:
                print(f"Waiting before loading page {page_num + 1}...")
                self._human_delay(5, 10)  # Longer delay between pages
                
            except TimeoutException as e:
                print(f"✗ Timeout waiting for job cards: {e}")
                
                # __ is Cloudflare check:
                page_source = self.driver.page_source.lower()
                if 'cloudflare' in page_source or 'verification' in page_source:
                    print("⚠ Likely blocked by Cloudflare")
                    self._save_debug_html()
                
                if len(all_jobs) > 0:
                    print(f"Returning {len(all_jobs)} jobs collected so far")
                    return all_jobs
                else:
                    self._save_debug_html()
                    return None
            
            except WebDriverException as e:
                print(f"WebDriver error on page {page_num + 1}: {e}")
                if len(all_jobs) > 0:
                    print(f"Returning {len(all_jobs)} jobs collected so far")
                    return all_jobs
                else:
                    import traceback
                    traceback.print_exc()
                    return None
        
        return all_jobs if all_jobs else None
    
    def _extract_job_data(self, card, query, location):
        """ Extract job data from a job card element:
            Args:
                card:           <-- Selenium WebElement representing a job card:
                query (str):    <-- Original search query:
                location (str): <-- Original search location:
            Returns: dict:      <-- Job data dictionary: """
        job_data = {
            'scraped_at': datetime.now().isoformat(),
            'search_query': query,
            'search_location': location,
        }
        
        # __ Job key:
        try:
            job_key = card.get_attribute('data-jk')
            if not job_key:
                link = card.find_element(By.CSS_SELECTOR, "a[data-jk]")
                job_key = link.get_attribute('data-jk')
            job_data['job_key'] = job_key
        except (NoSuchElementException, WebDriverException) as e:
            print(f"    Job key extraction failed: {e}")
            job_data['job_key'] = "N/A"
        
        # __ Title:
        try:
            title_elem = card.find_element(By.CSS_SELECTOR, "h2.jobTitle span[title]")
            job_data['title'] = title_elem.get_attribute('title')
        except NoSuchElementException as e:
            try:
                title_elem = card.find_element(By.CSS_SELECTOR, "h2.jobTitle")
                job_data['title'] = title_elem.text
            except (NoSuchElementException, WebDriverException) as e2:
                print(f"    Title extraction failed: {e2}")
                job_data['title'] = "N/A"
        
        # __ Company:
        try:
            company_elem = card.find_element(By.CSS_SELECTOR, "span[data-testid='company-name']")
            job_data['company'] = company_elem.text
        except NoSuchElementException:
            try:
                company_elem = card.find_element(By.CSS_SELECTOR, ".companyName")
                job_data['company'] = company_elem.text
            except (NoSuchElementException, WebDriverException) as e:
                print(f"    Company extraction failed: {e}")
                job_data['company'] = "N/A"
        
        # __ Location:
        try:
            location_elem = card.find_element(By.CSS_SELECTOR, "div[data-testid='text-location']")
            job_data['location'] = location_elem.text
        except NoSuchElementException:
            try:
                location_elem = card.find_element(By.CSS_SELECTOR, ".companyLocation")
                job_data['location'] = location_elem.text
            except (NoSuchElementException, WebDriverException) as e:
                print(f"    Location extraction failed: {e}")
                job_data['location'] = "N/A"
        
        # __ Salary:
        try:
            salary_elem = card.find_element(By.CSS_SELECTOR, "div.salary-snippet-container")
            job_data['salary'] = salary_elem.text
        except NoSuchElementException:
            try:
                salary_elem = card.find_element(By.CSS_SELECTOR, ".salary-snippet")
                job_data['salary'] = salary_elem.text
            except (NoSuchElementException, WebDriverException):
                job_data['salary'] = "N/A"
        
        # __ Snippet:
        try:
            snippet_elem = card.find_element(By.CSS_SELECTOR, "div.job-snippet")
            job_data['snippet'] = snippet_elem.text[:200]
        except (NoSuchElementException, WebDriverException):
            job_data['snippet'] = "N/A"
        
        # __ Build URL:
        if job_data['job_key'] != "N/A":
            job_data['url'] = f"https://www.indeed.com/viewjob?jk={job_data['job_key']}"
        else:
            try:
                link_elem = card.find_element(By.CSS_SELECTOR, "a")
                job_data['url'] = link_elem.get_attribute('href')
            except (NoSuchElementException, WebDriverException) as e:
                print(f"    URL extraction failed: {e}")
                job_data['url'] = "N/A"
        
        # __ Posted date:
        try:
            date_elem = card.find_element(By.CSS_SELECTOR, "span.date")
            job_data['posted'] = date_elem.text
        except (NoSuchElementException, WebDriverException):
            job_data['posted'] = "N/A"
        
        return job_data
    
    def _human_delay(self, min_seconds=1, max_seconds=3):
        """ Add random delay to mimic human behavior:
            Args:
                min_seconds (float): <-- Minimum delay:
                max_seconds (float): <-- Maximum delay: """
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def _save_debug_html(self):
        """Save current page source to HTML file for debugging."""
        
        artifacts_dir = Path(__file__).parent.parent / "artifacts" / "html"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = artifacts_dir / f"debug_{timestamp}.html"
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            
            print(f"Debug HTML saved to: {filepath}")
        except (IOError, OSError) as e:
            print(f"Failed to save debug HTML: {e}")
    
    def _handle_cloudflare_challenge(self):
        """ Detect and handle Cloudflare challenges:
            Returns: bool: <-- True if challenge was detected, False otherwise: """
        try:
            page_source = self.driver.page_source.lower()
            page_title = self.driver.title.lower()
            
            # __ Check for Cloudflare indicators:
            cloudflare_indicators = [
                'cloudflare' in page_title,
                'additional verification required' in page_source,
                'verify you are human' in page_source,
                'ray id' in page_source,
                'checking your browser' in page_source
            ]
            
            if any(cloudflare_indicators):
                print("✗ Cloudflare challenge detected!")
                print(f"   Page title: {self.driver.title}")
                
                # __ Try to find and click the checkbox:
                try:
                    # __ Wait for Cloudflare iframe:
                    time.sleep(3)
                    
                    # __ Switch to Cloudflare iframe if present:
                    iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                    for iframe in iframes:
                        try:
                            self.driver.switch_to.frame(iframe)
                            checkbox = self.driver.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                            if checkbox.is_displayed():
                                print("   Found Cloudflare checkbox, clicking...")
                                checkbox.click()
                                time.sleep(5)
                                self.driver.switch_to.default_content()
                                return True
                        except NoSuchElementException:
                            self.driver.switch_to.default_content()
                            continue
                except (NoSuchElementException, WebDriverException) as e:
                    print(f"   Could not auto-solve challenge: {e}")
                
                # __ If auto-solve failed, prompt user:
                print("\n" + "="*80)
                print("MANUAL INTERVENTION REQUIRED")
                print("="*80)
                print("Cloudflare is blocking automated access.")
                print("\nOptions:")
                print("1. Complete the challenge in the browser window")
                print("2. Wait for automatic verification (may take 5-10 seconds)")
                print("3. Press Ctrl+C to abort")
                print("\nWaiting for challenge to be solved...")
                input("\nPress Enter once the page loads successfully...")
                
                return True
            
            return False
            
        except WebDriverException as e:
            print(f"Error checking for Cloudflare: {e}")
            return False
    
    def close(self):
        """Close the browser."""
        try:
            self.driver.quit()
        except WebDriverException as e:
            print(f"Error closing browser: {e}")