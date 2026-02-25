#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Camoufox Scraper Module:
    Anti-detect browser automation using Camoufox for bypassing Cloudflare protection """

import time
import random
from datetime import datetime
from urllib.parse import quote_plus
from camoufox.sync_api import Camoufox


class CamoufoxIndeedScraper:
    """ Indeed scraper | trying Camoufox:
        Camoufox advantages:
            - Fingerprint injection at C++ level (undetectable via JS)
            - WebGL, WebRTC, navigator spoofing
            - Human-like mouse movement
            - Firefox-based (less targeted than Chromium)
            - Automatic fingerprint rotation
            - Built-in Cloudflare Turnstile support """
    
    def __init__(self, headless=False, incognito=False, window_size="maximized", proxy=None):
        """ Initialize Camoufox scraper:
            Args:
                headless (bool):    <-- Run in headless mode (use 'virtual' on Linux for Xvfb)
                incognito (bool):   <-- Use fresh context (no persistent data)
                window_size (str):  <-- Window size - "maximized" or "WIDTHxHEIGHT"
                proxy (dict):       <-- Proxy configuration {'server': 'http://...', 'username': '...', 'password': '...'} """
        
        self.headless = headless
        self.incognito = incognito
        self.window_size = window_size
        self.proxy = proxy
        self.browser = None
        self.page = None
        self._camoufox_context = None
        
        # ___ Browser Start:
        self._start_browser()
    
    def __enter__(self):
        """Context manager entry:"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit:"""
        self.close()
    
    def _start_browser(self):
        """Start Camoufox browser with anti-detection settings:"""
        # ___ parse window size:
        if self.window_size == "maximized":
            window = (1920, 1080)
        else:
            try:
                width, height = map(int, self.window_size.split('x'))
                window = (width, height)
            except:
                window = (1920, 1080)
        
        # ___ Configure headless mode:
        # ___ On Linux | 'virtual' for Xvfb-based headless is needed:
        headless_mode = 'virtual' if self.headless else False
        
        # ___ Build Camoufox options:
        camoufox_options = {
            'headless': headless_mode,
            'humanize': True,                 # <-- Enable human-like mouse movements
            'window': window,
            # 'os': ['windows', 'macos'],     # <-- Rotate between Windows and macOS fingerprints | did not work
            # 'os': None,                     # <-- Rotate between Windows and macOS fingerprints | did not work
            'locale': 'en-US',
            'block_webrtc': True,             # <-- Prevent WebRTC IP leaks
            'disable_coop': True,             # <-- Allow clicking Turnstile checkbox in iframes
            'enable_cache': False,            # <-- Disable cache for cleaner sessions
        }
        
        # ___ add proxy if provided:
        if self.proxy:
            camoufox_options['proxy'] = self.proxy
            # ___ needs geoip to match location with proxy IP:
            if 'server' in self.proxy:
                camoufox_options['geoip'] = True
        
        # ___ Start Camoufox:
        self._camoufox_context = Camoufox(**camoufox_options)
        self.browser = self._camoufox_context.__enter__()
        self.page = self.browser.new_page()
        
        if self.incognito:
            print("[*] Running Camoufox in fresh context mode")
        else:
            print("[*] Camoufox browser started with anti-detection")
    
    def login(self, email, password):
        """ Login to Indeed account:
            Args:
                email (str): Indeed account email:
                password (str): Indeed account password:
            Returns:
                bool: True if login successful: """
        try:
            print("\n[*] Attempting Indeed login...")
            self.page.goto("https://secure.indeed.com/auth", wait_until='networkidle', timeout=30000)
            self._human_delay(2, 4)
            
            # ___ check for Cloudflare challenge first:
            if self._handle_cloudflare():
                print("[+] Cloudflare challenge handled")
            
            # ___ Fill email:
            email_input = self.page.wait_for_selector('input[type="email"], input[name="__email"]', timeout=10000)
            if email_input:
                email_input.fill(email)
                self._human_delay(1, 2)
            
            # ___ click continue/next:
            continue_btn = self.page.query_selector('button[type="submit"]')
            if continue_btn:
                continue_btn.click()
                self._human_delay(2, 4)
            
            # ___ Fill password:
            password_input = self.page.wait_for_selector('input[type="password"]', timeout=10000)
            if password_input:
                password_input.fill(password)
                self._human_delay(1, 2)
            
            # ___ Submit login:
            submit_btn = self.page.query_selector('button[type="submit"]')
            if submit_btn:
                submit_btn.click()
                self._human_delay(3, 5)
            
            # ___ Check if login went through:
            if 'indeed.com' in self.page.url and 'auth' not in self.page.url:
                print("[+] Login successful")
                return True
            else:
                print("[X] Login may have failed - check browser")
                return False
                
        except Exception as e:
            print(f"[X] Login error: {e}")
            return False
    
    def search_jobs(self, query, location="", remote_only=False,
                   min_salary=None, max_salary=None, date_posted=None,
                   max_results=25):
        """ Search Indeed jobs with Camoufox:
            Args:
                query (str):        <-- Job search query:
                location (str):     <-- Job location:
                remote_only (bool): <-- Remote filter:
                min_salary (int):   <-- Min salary:
                max_salary (int):   <-- Max salary:
                date_posted (int):  <-- Days filter:
                max_results (int):  <-- Max results:
            Returns:
                list: Job dictionaries: """
        
        # ___ Build url:
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
        
        while len(all_jobs) < max_results and consecutive_failures < max_failures:
            # ___ Build page url:
            if page_num > 0:
                url = f"{base_url}&start={page_num * 10}"
            else:
                url = base_url
            
            print(f"\n[*] Page {page_num + 1}: {url}")
            
            try:
                # ___ Navigate with realistic timing:
                self.page.goto(url, wait_until='networkidle', timeout=45000)
                
                # ___ Random delay to appear human:
                self._human_delay(2, 4)
                
                # ___ Handle Cloudflare challenge if true:
                if self._handle_cloudflare():
                    print("[+] Cloudflare challenge handled")
                    self._human_delay(2, 3)
                
                # ___ Wait for job cards:
                try:
                    self.page.wait_for_selector('div.job_seen_beacon', timeout=15000)
                except:
                    # ___ Try alternative selector...
                    try:
                        self.page.wait_for_selector('[data-testid="jobsearch-ResultsList"]', timeout=10000)
                    except:
                        print("[!] Could not find job listings - may be blocked")
                        consecutive_failures += 1
                        self._human_delay(5, 10)
                        continue
                
                # ___ Extract jobs:
                job_cards = self.page.query_selector_all('div.job_seen_beacon')
                
                if not job_cards:
                    # ___ Try alternative selector...
                    job_cards = self.page.query_selector_all('div.jobsearch-ResultsList > div')
                
                print(f"[*] Found {len(job_cards)} job cards")
                
                page_jobs = 0
                for card in job_cards:
                    if len(all_jobs) >= max_results:
                        break
                    
                    try:
                        job_data = self._extract_job_from_element(card, query, location)
                        
                        # ___ Check duplicates:
                        if job_data['job_key'] != "N/A":
                            if any(j['job_key'] == job_data['job_key'] for j in all_jobs):
                                continue
                        
                        if job_data['title'] != "N/A":
                            all_jobs.append(job_data)
                            page_jobs += 1
                            print(f"  [{len(all_jobs)}] {job_data['title'][:60]}")
                    
                    except Exception as e:
                        print(f"  [!] Error parsing job: {e}")
                        continue
                
                if page_jobs == 0:
                    print("[!] No new jobs on this page")
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0  # ___ Reset on success:
                
                if len(all_jobs) >= max_results:
                    break
                
                # ___ Human like delay between pages:
                self._human_delay(3, 6)
                page_num += 1
                
            except Exception as e:
                print(f"[X] Error on page {page_num + 1}: {e}")
                consecutive_failures += 1
                self._human_delay(5, 10)
        
        if consecutive_failures >= max_failures:
            print(f"\n[!] Stopped after {max_failures} consecutive failures")
        
        return all_jobs if all_jobs else None
    
    def _extract_job_from_element(self, element, query, location):
        """Extract job data from Camoufox/Playwright element:"""
        job_data = {
            'scraped_at': datetime.now().isoformat(),
            'search_query': query,
            'search_location': location,
        }
        
        # ___ Job key:
        try:
            job_key = element.get_attribute('data-jk')
            job_data['job_key'] = job_key if job_key else "N/A"
        except:
            job_data['job_key'] = "N/A"
        
        # ___ Title:
        try:
            title_elem = element.query_selector('h2.jobTitle span[title]')
            if title_elem:
                job_data['title'] = title_elem.get_attribute('title')
            else:
                title_elem = element.query_selector('h2.jobTitle')
                job_data['title'] = title_elem.inner_text() if title_elem else "N/A"
        except:
            job_data['title'] = "N/A"
        
        # ___ Company:
        try:
            company_elem = element.query_selector('span[data-testid="company-name"]')
            job_data['company'] = company_elem.inner_text() if company_elem else "N/A"
        except:
            job_data['company'] = "N/A"
        
        # ___ Location:
        try:
            location_elem = element.query_selector('div[data-testid="text-location"]')
            job_data['location'] = location_elem.inner_text() if location_elem else "N/A"
        except:
            job_data['location'] = "N/A"
        
        # ___ Salary:
        try:
            salary_elem = element.query_selector('div.salary-snippet-container')
            if not salary_elem:
                salary_elem = element.query_selector('[data-testid="attribute_snippet_testid"]')
            job_data['salary'] = salary_elem.inner_text() if salary_elem else "N/A"
        except:
            job_data['salary'] = "N/A"
        
        # ___ Snippet:
        try:
            snippet_elem = element.query_selector('div.job-snippet')
            if not snippet_elem:
                snippet_elem = element.query_selector('[class*="job-snippet"]')
            job_data['snippet'] = snippet_elem.inner_text()[:200] if snippet_elem else "N/A"
        except:
            job_data['snippet'] = "N/A"
        
        # ___ job url:
        if job_data['job_key'] != "N/A":
            job_data['url'] = f"https://www.indeed.com/viewjob?jk={job_data['job_key']}"
        else:
            job_data['url'] = "N/A"
        
        # ___ Posted:
        try:
            date_elem = element.query_selector('span.date')
            if not date_elem:
                date_elem = element.query_selector('[data-testid="myJobsStateDate"]')
            job_data['posted'] = date_elem.inner_text() if date_elem else "N/A"
        except:
            job_data['posted'] = "N/A"
        
        return job_data
    
    def _handle_cloudflare(self):
        """ Handle Cloudflare challenge if present:
            Returns:
                bool: True if challenge was detected and handled """
        if not self._is_cloudflare_challenge():
            return False
        
        print("[*] Cloudflare challenge detected - attempting to solve...")
        
        try:
            # ___ Wait for the challenge to load:
            self._human_delay(2, 4)
            
            # ___ search for Turnstile iframe:
            turnstile_frame = self.page.query_selector('iframe[src*="challenges.cloudflare.com"]')
            
            if turnstile_frame:
                # ___ get the bounding box of the iframe:
                box = turnstile_frame.bounding_box()
                if box:
                    # ___ calculate center of the checkbox | <-- usually around 30px from left, center vertically:
                    click_x = box['x'] + 30
                    click_y = box['y'] + box['height'] / 2
                    
                    # ___ mimic human mouse movement to click:
                    self.page.mouse.click(click_x, click_y)
                    print("[*] Clicked Turnstile checkbox")
                    
                    # ___ Wait for verification:
                    self._human_delay(3, 6)
                    
                    # ___ Check if challenge is solved:
                    if not self._is_cloudflare_challenge():
                        return True
            
            # ___ alternative | look for the checkbox directly:
            checkbox = self.page.query_selector('input[type="checkbox"]')
            if checkbox:
                checkbox.click()
                self._human_delay(3, 5)
                if not self._is_cloudflare_challenge():
                    return True
            
            # ___ if automatic solving fails, wait for manual click | at the run time in terminal:
            print("[!] Automatic Cloudflare bypass failed")
            print("[*] Please solve the challenge manually in the browser...")
            
            # ___ Wait up to 60 seconds for manual solving:
            for i in range(12):
                self._human_delay(5, 5)
                if not self._is_cloudflare_challenge():
                    print("[+] Challenge solved!")
                    return True
            
            print("[X] Cloudflare challenge timeout")
            return False
            
        except Exception as e:
            print(f"[!] Error handling Cloudflare: {e}")
            return False
    
    def _is_cloudflare_challenge(self):
        """Check if current page is Cloudflare challenge."""
        try:
            title = self.page.title().lower()
            content = self.page.content().lower()
            
            return any([
                'cloudflare' in title,
                'just a moment' in title,
                'additional verification' in content,
                'verify you are human' in content,
                'ray id' in content and 'cloudflare' in content,
                'challenges.cloudflare.com' in content
            ])
        except:
            return False
    
    def _human_delay(self, min_seconds=1, max_seconds=3):
        """Random human-like delay."""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def close(self):
        """Close browser and cleanup."""
        try:
            if self._camoufox_context:
                self._camoufox_context.__exit__(None, None, None)
                print("[*] Camoufox browser closed")
        except Exception as e:
            print(f"[!] Error closing browser: {e}")


if __name__ == "__main__":
    pass