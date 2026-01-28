#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Indeed Job Scraper Module
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
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class IndeedJobScraper:
    """Scraper for Indeed job postings using Selenium."""
    
    def __init__(self, headless=False, incognito=False, window_size="maximized"):
        """ Initialize the scraper with browser options:
            Args:
                headless (bool): Run browser in headless mode (no GUI)
                incognito (bool): Run in incognito/private mode
                window_size (str): Window size - "maximized" or "WIDTHxHEIGHT" (e.g., "1280x720") """
        
        chrome_options = Options()
        
        # Incognito mode
        if incognito:
            chrome_options.add_argument('--incognito')
            print("🕶️  Running in incognito mode")
        
        # Window size for headless or specific size
        if headless:
            if window_size == "maximized":
                chrome_options.add_argument('--window-size=1920,1080')
            else:
                chrome_options.add_argument(f'--window-size={window_size.replace("x", ",")}')
        
        # Enhanced anti-detection options
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Additional anti-detection
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=IsolateOrigins,site-per-process')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--start-maximized')
        
        # Language and location
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
        
        # Set window size if not headless
        if not headless:
            if window_size == "maximized":
                self.driver.maximize_window()
            else:
                # Parse custom size (e.g., "1280x720")
                try:
                    width, height = map(int, window_size.split('x'))
                    self.driver.set_window_size(width, height)
                except:
                    print(f"⚠ Invalid window size '{window_size}', maximizing instead")
                    self.driver.maximize_window()
        
        self.wait = WebDriverWait(self.driver, 15)
        
        # Enhanced anti-detection: Override navigator properties
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            "platform": "MacIntel",
            "acceptLanguage": "en-US,en;q=0.9"
        })
        
        # Remove webdriver flag
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Override permissions
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
        """
        Login to Indeed with credentials.
        
        Args:
            email (str): Indeed account email
            password (str): Indeed account password
            
        Returns:
            bool: True if login successful, False otherwise
        """
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
            
            # Check for Google auth
            try:
                google_btn = self.driver.find_element(By.CSS_SELECTOR, "button[data-tn-element='google-auth-button']")
                print("\nGoogle authentication detected!")
                print("Click 'Sign in with email and password' or use Google auth")
                input("\nComplete authentication, then press Enter...")
                time.sleep(2)
            except NoSuchElementException:
                pass
            
            # Try password field
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
            except TimeoutException:
                print("Password field not found - alternative auth used")
            
            # Check for 2FA
            if "verification" in self.driver.current_url.lower() or "challenge" in self.driver.current_url.lower():
                print("\n2FA/CAPTCHA detected!")
                input("Complete verification, then press Enter...")
            
            time.sleep(3)
            if "account" in self.driver.current_url or len(self.driver.get_cookies()) > 3:
                print("✓ Login successful!")
                return True
            else:
                print("✗ Login may have failed")
                return False
            
        except Exception as e:
            print(f"Login error: {e}")
            return False
    
    def build_search_url(self, query, location="", remote_only=False, 
                        min_salary=None, max_salary=None, date_posted=None):
        """
        Build Indeed search URL with parameters.
        
        Args:
            query (str): Job search query
            location (str): Job location
            remote_only (bool): Filter for remote jobs only
            min_salary (int): Minimum salary
            max_salary (int): Maximum salary
            date_posted (int): Posted within last N days (1, 3, 7, or 14)
            
        Returns:
            str: Complete search URL
        """
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
    
    def search_jobs(self, query, location="", remote_only=False,
                   min_salary=None, max_salary=None, date_posted=None,
                   max_results=25, use_url_pagination=True):
        """
        Search for jobs on Indeed with pagination support.
        
        Args:
            query (str): Job search query
            location (str): Job location
            remote_only (bool): Filter for remote jobs only
            min_salary (int): Minimum salary
            max_salary (int): Maximum salary
            date_posted (int): Posted within last N days
            max_results (int): Maximum number of results to scrape
            use_url_pagination (bool): Use URL parameters instead of clicking Next
            
        Returns:
            list: List of job dictionaries, or None if failed
        """
        base_search_url = self.build_search_url(
            query=query,
            location=location,
            remote_only=remote_only,
            min_salary=min_salary,
            max_salary=max_salary,
            date_posted=date_posted
        )
        
        all_jobs = []
        page_num = 0  # Indeed uses 0-indexed start parameter
        
        while len(all_jobs) < max_results:
            # Build URL for current page
            if use_url_pagination and page_num > 0:
                # Indeed uses &start=N where N = page * 10
                start = page_num * 10
                search_url = f"{base_search_url}&start={start}"
            else:
                search_url = base_search_url
            
            print(f"\nPage {page_num + 1}: {search_url}")
            
            self.driver.get(search_url)
            self._human_delay(3, 5)
            
            # Check for Cloudflare challenge
            if self._handle_cloudflare_challenge():
                print("⚠ Cloudflare challenge detected")
                self._human_delay(8, 12)
            
            # Check if page loaded
            try:
                job_container = self.driver.find_element(By.ID, "mosaic-provider-jobcards")
                print("✓ Page loaded successfully")
            except NoSuchElementException:
                page_title = self.driver.title.lower()
                if "access denied" in page_title or "captcha" in page_title:
                    print("✗ Blocked by Indeed")
                    self._save_debug_html()
                    if len(all_jobs) > 0:
                        return all_jobs
                    return None
                else:
                    print("⚠ No job results found")
                    if len(all_jobs) > 0:
                        return all_jobs
                    return None
            
            # Extract jobs from current page
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
                        
                        # Check for duplicates
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
                    
                    except Exception as e:
                        print(f"  Error parsing job: {e}")
                        continue
                
                print(f"Extracted {page_jobs} jobs from page {page_num + 1} (total: {len(all_jobs)})")
                
                # Check if we got any jobs on this page
                if page_jobs == 0:
                    print("No new jobs on this page - stopping")
                    break
                
                # Check if we have enough jobs
                if len(all_jobs) >= max_results:
                    print(f"✓ Reached target of {max_results} jobs")
                    break
                
                # Move to next page
                page_num += 1
                
                # Add delay between pages to avoid triggering Cloudflare
                print(f"Waiting before loading page {page_num + 1}...")
                self._human_delay(5, 10)  # Longer delay between pages
                
            except TimeoutException:
                print("✗ Timeout waiting for job cards")
                
                # Check if it's Cloudflare
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
            
            except Exception as e:
                print(f"Error on page {page_num + 1}: {e}")
                if len(all_jobs) > 0:
                    print(f"Returning {len(all_jobs)} jobs collected so far")
                    return all_jobs
                else:
                    import traceback
                    traceback.print_exc()
                    return None
        
        return all_jobs if all_jobs else None
        """
        Search for jobs on Indeed with pagination support.
        
        Args:
            query (str): Job search query
            location (str): Job location
            remote_only (bool): Filter for remote jobs only
            min_salary (int): Minimum salary
            max_salary (int): Maximum salary
            date_posted (int): Posted within last N days
            max_results (int): Maximum number of results to scrape
            
        Returns:
            list: List of job dictionaries, or None if failed
        """
        search_url = self.build_search_url(
            query=query,
            location=location,
            remote_only=remote_only,
            min_salary=min_salary,
            max_salary=max_salary,
            date_posted=date_posted
        )
        
        print(f"\nSearching: {search_url}")
        
        self.driver.get(search_url)
        self._human_delay(3, 5)  # Random 3-5 second delay
        
        # Check for Cloudflare challenge
        if self._handle_cloudflare_challenge():
            print("⚠ Cloudflare challenge detected - waiting for resolution...")
            self._human_delay(8, 12)  # Longer wait after challenge
        
        # Check if page loaded
        try:
            job_container = self.driver.find_element(By.ID, "mosaic-provider-jobcards")
            print("✓ Page loaded successfully")
        except NoSuchElementException:
            page_title = self.driver.title.lower()
            if "access denied" in page_title or "captcha" in page_title:
                print("✗ Blocked by Indeed")
                self._save_debug_html()
                return None
            else:
                print("⚠ No job results found")
        
        # Check for CAPTCHA
        try:
            captcha = self.driver.find_element(By.CSS_SELECTOR, "iframe[title*='recaptcha'], iframe[title*='hCaptcha']")
            print("CAPTCHA detected!")
            input("Solve CAPTCHA in browser, then press Enter...")
            time.sleep(2)
        except NoSuchElementException:
            pass
        
        # Extract jobs with pagination
        all_jobs = []
        page_num = 1
        
        while len(all_jobs) < max_results:
            print(f"\nProcessing page {page_num}...")
            
            try:
                # Wait for job cards to load
                job_cards = self.wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.job_seen_beacon"))
                )
                
                print(f"Found {len(job_cards)} job cards on page {page_num}")
                
                # Extract jobs from current page
                page_jobs = 0
                for i, card in enumerate(job_cards):
                    if len(all_jobs) >= max_results:
                        break
                    
                    try:
                        job_data = self._extract_job_data(card, query, location)
                        
                        # Check for duplicates (by job_key)
                        if job_data['job_key'] != "N/A":
                            if any(j['job_key'] == job_data['job_key'] for j in all_jobs):
                                continue  # Skip duplicate
                        
                        if job_data['title'] != "N/A" and job_data['url'] != "N/A":
                            all_jobs.append(job_data)
                            page_jobs += 1
                            print(f"  [{len(all_jobs)}] {job_data['title'][:60]}")
                            print(f"      {job_data['company']} - {job_data['location']}")
                            if job_data['salary'] != "N/A":
                                print(f"      Salary: {job_data['salary']}")
                        
                    except Exception as e:
                        print(f"  Error parsing job: {e}")
                        continue
                
                print(f"Extracted {page_jobs} jobs from page {page_num} (total: {len(all_jobs)})")
                
                # Check if we have enough jobs
                if len(all_jobs) >= max_results:
                    print(f"✓ Reached target of {max_results} jobs")
                    break
                
                # Try to find and click "Next" button
                try:
                    # Scroll to bottom to ensure pagination is visible
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    self._human_delay(1, 2)  # Random delay after scroll
                    
                    # Try multiple selectors for the next button
                    next_button = None
                    next_selectors = [
                        "a[data-testid='pagination-page-next']",
                        "a[aria-label='Next Page']",
                        "nav[role='navigation'] a[aria-label*='Next']",
                        "div.pagination a:last-child"
                    ]
                    
                    for selector in next_selectors:
                        try:
                            next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                            if next_button and next_button.is_displayed() and next_button.is_enabled():
                                break
                        except NoSuchElementException:
                            continue
                    
                    if next_button:
                        print(f"Clicking 'Next' to page {page_num + 1}...")
                        next_button.click()
                        self._human_delay(4, 7)  # Random delay for page load
                        
                        # Check for Cloudflare after navigation
                        if self._handle_cloudflare_challenge():
                            print("⚠ Cloudflare appeared on page navigation")
                            self._human_delay(8, 12)
                        
                        page_num += 1
                    else:
                        print("No more pages available")
                        break
                        
                except NoSuchElementException:
                    print("No 'Next' button found - reached last page")
                    break
                except Exception as e:
                    print(f"Error navigating to next page: {e}")
                    break
            
            except TimeoutException:
                print("✗ Timeout waiting for job cards")
                
                # Check if it's a Cloudflare issue
                page_source = self.driver.page_source.lower()
                if 'cloudflare' in page_source or 'verification' in page_source:
                    print("⚠ Likely blocked by Cloudflare on this page")
                    if self._handle_cloudflare_challenge():
                        print("Retrying current page after challenge...")
                        continue  # Retry this page
                
                if len(all_jobs) > 0:
                    print(f"Returning {len(all_jobs)} jobs collected so far")
                    return all_jobs
                else:
                    self._save_debug_html()
                    return None
            except Exception as e:
                print(f"Error on page {page_num}: {e}")
                if len(all_jobs) > 0:
                    print(f"Returning {len(all_jobs)} jobs collected so far")
                    return all_jobs
                else:
                    import traceback
                    traceback.print_exc()
                    return None
        
        return all_jobs if all_jobs else None
    
    def _extract_job_data(self, card, query, location):
        """
        Extract job data from a job card element.
        
        Args:
            card: Selenium WebElement representing a job card
            query (str): Original search query
            location (str): Original search location
            
        Returns:
            dict: Job data dictionary
        """
        job_data = {
            'scraped_at': datetime.now().isoformat(),
            'search_query': query,
            'search_location': location,
        }
        
        # Job key
        try:
            job_key = card.get_attribute('data-jk')
            if not job_key:
                link = card.find_element(By.CSS_SELECTOR, "a[data-jk]")
                job_key = link.get_attribute('data-jk')
            job_data['job_key'] = job_key
        except:
            job_data['job_key'] = "N/A"
        
        # Title
        try:
            title_elem = card.find_element(By.CSS_SELECTOR, "h2.jobTitle span[title]")
            job_data['title'] = title_elem.get_attribute('title')
        except:
            try:
                title_elem = card.find_element(By.CSS_SELECTOR, "h2.jobTitle")
                job_data['title'] = title_elem.text
            except:
                job_data['title'] = "N/A"
        
        # Company
        try:
            company_elem = card.find_element(By.CSS_SELECTOR, "span[data-testid='company-name']")
            job_data['company'] = company_elem.text
        except:
            try:
                company_elem = card.find_element(By.CSS_SELECTOR, ".companyName")
                job_data['company'] = company_elem.text
            except:
                job_data['company'] = "N/A"
        
        # Location
        try:
            location_elem = card.find_element(By.CSS_SELECTOR, "div[data-testid='text-location']")
            job_data['location'] = location_elem.text
        except:
            try:
                location_elem = card.find_element(By.CSS_SELECTOR, ".companyLocation")
                job_data['location'] = location_elem.text
            except:
                job_data['location'] = "N/A"
        
        # Salary
        try:
            salary_elem = card.find_element(By.CSS_SELECTOR, "div.salary-snippet-container")
            job_data['salary'] = salary_elem.text
        except:
            try:
                salary_elem = card.find_element(By.CSS_SELECTOR, ".salary-snippet")
                job_data['salary'] = salary_elem.text
            except:
                job_data['salary'] = "N/A"
        
        # Snippet
        try:
            snippet_elem = card.find_element(By.CSS_SELECTOR, "div.job-snippet")
            job_data['snippet'] = snippet_elem.text[:200]
        except:
            job_data['snippet'] = "N/A"
        
        # Build URL
        if job_data['job_key'] != "N/A":
            job_data['url'] = f"https://www.indeed.com/viewjob?jk={job_data['job_key']}"
        else:
            try:
                link_elem = card.find_element(By.CSS_SELECTOR, "a")
                job_data['url'] = link_elem.get_attribute('href')
            except:
                job_data['url'] = "N/A"
        
        # Posted date
        try:
            date_elem = card.find_element(By.CSS_SELECTOR, "span.date")
            job_data['posted'] = date_elem.text
        except:
            job_data['posted'] = "N/A"
        
        return job_data
    
    def _human_delay(self, min_seconds=1, max_seconds=3):
        """
        Add random delay to mimic human behavior.
        
        Args:
            min_seconds (float): Minimum delay
            max_seconds (float): Maximum delay
        """
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def _save_debug_html(self):
        """Save current page source to HTML file for debugging."""
        
        artifacts_dir = Path(__file__).parent.parent / "artifacts" / "html"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = artifacts_dir / f"debug_{timestamp}.html"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.driver.page_source)
        
        print(f"Debug HTML saved to: {filepath}")
    
    def _handle_cloudflare_challenge(self):
        """
        Detect and handle Cloudflare challenges.
        
        Returns:
            bool: True if challenge was detected, False otherwise
        """
        try:
            page_source = self.driver.page_source.lower()
            page_title = self.driver.title.lower()
            
            # Check for Cloudflare indicators
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
                
                # Try to find and click the checkbox
                try:
                    # Wait for Cloudflare iframe
                    time.sleep(3)
                    
                    # Switch to Cloudflare iframe if present
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
                        except:
                            self.driver.switch_to.default_content()
                            continue
                except Exception as e:
                    print(f"   Could not auto-solve challenge: {e}")
                
                # If auto-solve failed, prompt user
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
            
        except Exception as e:
            print(f"Error checking for Cloudflare: {e}")
            return False
    
    def close(self):
        """Close the browser."""
        self.driver.quit()