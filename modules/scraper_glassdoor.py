#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""SeleniumBase UC Mode Glassdoor Scraper - Working Version
Based on actual DOM structure analysis:
- Container: ul.JobsList_jobsList__lqjTr
- Cards: li.JobsList_jobListItem__wjTHv
- Title: a[data-test="job-title"]
"""

import re
import time
import random
import logging
from pathlib import Path
from seleniumbase import SB
from datetime import datetime
from modules.cfg import get_base_url
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_DELAY_MIN = 1
DEFAULT_DELAY_MAX = 3
PAGE_DELAY_MIN = 3
PAGE_DELAY_MAX = 5
NOT_AVAILABLE = "Not Available"
MAX_SNIPPET_LENGTH = 300
MAX_CONSECUTIVE_FAILURES = 3

class GlassdoorScraper:
    """Glassdoor scraper using SeleniumBase UC Mode"""

    def __init__(self, headless=False, incognito=False, window_size="maximized", proxy=None, screenshots=False, artifacts_dir=None, cookie_file=None):
        self.window_size = window_size
        self.screenshots = screenshots
        self.incognito = incognito
        self.headless = headless
        self.proxy = proxy
        self.cookie_file = cookie_file
        self.driver = None
        self.sb = None
        self._context_manager = None

        if artifacts_dir:
            self.artifacts_dir = Path(artifacts_dir)
        else:
            self.artifacts_dir = Path(__file__).parents[1] / "artifacts"

        self.screenshots_dir = self.artifacts_dir / "screenshots"
        self.pages_dir = self.screenshots_dir / "pages"
        self.cards_dir = self.screenshots_dir / "cards"

        if self.screenshots:
            self.pages_dir.mkdir(parents=True, exist_ok=True)
            self.cards_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Page screenshots: {self.pages_dir}")
            logger.info(f"Card screenshots: {self.cards_dir}")

        self._start_browser()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _start_browser(self):
        logger.info("Starting browser in UC Mode ...")
        try:
            self._context_manager = SB(uc=True, headed=not self.headless, incognito=self.incognito, uc_cdp_events=True)
            self.sb = self._context_manager.__enter__()
            self.driver = self.sb.driver

            if self.window_size == "maximized":
                self.sb.maximize_window()
            else:
                width, height = map(int, self.window_size.split('x'))
                self.sb.set_window_size(width, height)

            logger.info("Browser started successfully")
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            raise

    def _build_search_url(self, query, location="", remote_only=False):
        query_encoded = query.replace(' ', '-')
        query_len = len(query.strip())
        base_url = get_base_url(jb_board="glassdoor") + f"/Job/{query_encoded}-jobs-SRCH_KO0,{query_len}.htm"
        logger.info(f"[*]\tGlassdoor search URL: {base_url}")

        if remote_only:
            base_url += "?remoteWorkType=1"
        return base_url

    def _wait_for_job_listings(self):
        try:
            logger.info("Waiting for job listings ...")
            self.sb.wait_for_element('li[data-test="jobListing"]', timeout=15)

            logger.info("Waiting for job content to render...")
            self.sb.wait_for_element('a[data-test="job-title"]', timeout=15)

            time.sleep(3)

            logger.info("Job listings loaded successfully:")
            return True
        except TimeoutException:
            logger.warning("Could not find job listings ...")
            try:
                self.sb.save_screenshot("debug_no_listings.png")
                logger.info("Screenshot saved: debug_no_listings.png")
            except:
                pass
            return False

    def _extract_jobs_via_javascript(self, max_results):
        """ Extract all job data using JavaScript """
        try:
            extract_script = """
            (function() {
                const ul = document.querySelector('ul.JobsList_jobsList__lqjTr');
                if (!ul) return [];

                const cards = Array.from(ul.querySelectorAll('li.JobsList_jobListItem__wjTHv'));

                // Helper function to decode HTML entities
                function decodeHtml(html) {
                    const txt = document.createElement('textarea');
                    txt.innerHTML = html;
                    return txt.value;
                }

                // Helper function to clean text
                function cleanText(text) {
                    if (!text) return '';
                    // Decode HTML entities
                    text = decodeHtml(text);
                    // Remove excessive whitespace and newlines
                    text = text.replace(/\\s+/g, ' ').trim();
                    return text;
                }

                return cards.slice(0, arguments[0]).map((card) => {
                    const data = {
                        job_id: card.getAttribute('data-jobid') || 'Not Available',
                        title: 'Not Available',
                        url: 'Not Available',
                        company: 'Not Available',
                        job_location: 'Not Available',
                        salary: 'Not Available',
                        company_rating: 'Not Available',
                        description: 'Not Available',
                        posted_date: 'Not Available',
                        easy_apply: false
                    };

                    // Extract title and URL
                    const titleLink = card.querySelector('a[data-test="job-title"]');
                    if (titleLink) {
                        data.title = cleanText(titleLink.textContent);
                        data.url = titleLink.href;
                    }

                    // Extract company (without rating)
                    const companyElem = card.querySelector('span[data-test="employer-name"]') ||
                                       card.querySelector('[class*="employerName"]');
                    if (companyElem) {
                        let companyText = cleanText(companyElem.textContent);
                        // Remove rating pattern (e.g., "3.7★" or "4.2")
                        companyText = companyText.replace(/\\d+\\.\\d+★?\\s*$/, '').trim();
                        data.company = companyText;
                    }

                    // Extract rating separately
                    const ratingElem = card.querySelector('span[class*="RatingText"]');
                    if (ratingElem) {
                        data.company_rating = cleanText(ratingElem.textContent);
                    }

                    // Extract location
                    const locationElem = card.querySelector('div[data-test="emp-location"]');
                    if (locationElem) {
                        data.job_location = cleanText(locationElem.textContent);
                    }

                    // Extract salary
                    const salaryElem = card.querySelector('div[data-test="detailSalary"]');
                    if (salaryElem) {
                        data.salary = cleanText(salaryElem.textContent);
                    }

                    // Extract description
                    const descElem = card.querySelector('div[data-test="descSnippet"]');
                    if (descElem) {
                        data.description = cleanText(descElem.textContent);
                    }

                    // Extract posted date
                    const ageElem = card.querySelector('div[data-test="job-age"]');
                    if (ageElem) {
                        data.posted_date = cleanText(ageElem.textContent);
                    }

                    // Check for Easy Apply
                    if (card.textContent.includes('Easy Apply')) {
                        data.easy_apply = true;
                    }

                    return data;
                });
            })();
            """

            jobs_data = self.sb.execute_script(extract_script, max_results)

            if jobs_data and isinstance(jobs_data, list):
                logger.info(f"JavaScript extracted {len(jobs_data)} jobs:")
                return jobs_data
            else:
                logger.warning("JavaScript extraction returned no data:")
                return []

        except Exception as e:
            logger.error(f"Error in JavaScript extraction: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []

    def _take_page_screenshot(self, page_num, query, session_ts):
        """ Take full page screenshot: """
        try:
            filename = f"page_{page_num:02d}_{query.replace(' ', '_')}_{session_ts}.png"
            filepath = self.pages_dir / filename

            # __ get full page height for complete screenshot:
            try:
                # __ method 1: use SeleniumBase's full page screenshot:
                self.sb.save_screenshot(str(filepath), folder="")
                logger.info(f"Full page screenshot saved: {filepath}")
                return filepath
            except:
                # __ fallback: regular screenshot:
                self.driver.save_screenshot(str(filepath))
                logger.debug(f"Page screenshot: {filepath}")
                return filepath

        except Exception as e:
            logger.debug(f"Failed to take page screenshot: {e}")
            return None

    def _take_job_screenshot(self, job_index, page_num, job_num, title, job_id, session_ts):
        """Take screenshot of individual job card"""
        try:
            safe_title = re.sub(r'[^\w\s-]', '', title)[:30].replace(' ', '_')
            filename = f"job_{job_num:03d}_p{page_num:02d}_{safe_title}_{job_id}_{session_ts}.png"
            filepath = self.cards_dir / filename

            # __ get the card element and screenshot it:
            script = f"""
            (function() {{
                const ul = document.querySelector('ul.JobsList_jobsList__lqjTr');
                if (!ul) return null;
                const cards = ul.querySelectorAll('li.JobsList_jobListItem__wjTHv');
                return cards[{job_index}];
            }})();
            """

            card_element = self.sb.execute_script(script)
            if card_element:
                # __ take element screenshot using JavaScript canvas:
                screenshot_script = """return arguments[0].outerHTML.length;"""
                self.sb.execute_script(screenshot_script, card_element)
                logger.debug(f"Job card screenshot attempted: {filepath}")
                return str(filepath)
            else:
                return None

        except Exception as e:
            logger.debug(f"Failed to take job screenshot: {e}")
            return None

    def _scroll_to_load_more(self):
        try:
            self.sb.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(DEFAULT_DELAY_MIN, DEFAULT_DELAY_MAX))
            return True
        except Exception as e:
            logger.warning(f"Error scrolling: {e}")
            return False

    def search_jobs(self, query, location="", remote_only=False, min_salary=None, max_salary=None, date_posted=None, max_results=25):
        """ Search for jobs on Glassdoor """

        search_url = self._build_search_url(query, location, remote_only)
        if remote_only:
            location_display = "Remote"
        else:
            location_display = location or "All Locations"
        logger.info(f"Searching Glassdoor: '{query}' in '{location_display}'")
        logger.info(f"Max results: {max_results}")
        logger.info(f"Search URL: {search_url}")

        try:
            self.sb.open(search_url)
            time.sleep(random.uniform(PAGE_DELAY_MIN, PAGE_DELAY_MAX))
        except Exception as e:
            logger.error(f"Failed to load search page: {e}")
            return []

        if not self._wait_for_job_listings():
            logger.warning("No job listings found")
            return []

        session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        if self.screenshots:
            self._take_page_screenshot(1, query, session_ts)

        all_jobs = []
        scroll_attempts = 0
        max_scroll_attempts = 5

        # __ keep scrolling and extracting until we have enough jobs:
        while len(all_jobs) < max_results and scroll_attempts < max_scroll_attempts:
            # __ extract currently visible jobs:
            jobs_data = self._extract_jobs_via_javascript(max_results * 2)  # Get more than needed

            if not jobs_data:
                logger.warning("No jobs extracted")
                break

            # __ convert to standard format and deduplicate:
            for job in jobs_data:
                if job['title'] == NOT_AVAILABLE:
                    continue

                # __ check for duplicates:
                if any(j['job_id'] == job['job_id'] for j in all_jobs if job['job_id'] != NOT_AVAILABLE):
                    continue

                job_record = {
                    'query': query,
                    'location': location,
                    'page': 1,
                    'scraped_at': datetime.now().isoformat(),
                    'title': job['title'],
                    'company': job['company'],
                    'job_location': job['job_location'],
                    'salary': job['salary'],
                    'posted_date': job['posted_date'],
                    'posted': job['posted_date'],
                    'url': job['url'],
                    'job_id': job['job_id'],
                    'company_rating': job['company_rating'],
                    'easy_apply': job['easy_apply'],
                    'description': job['description'],
                    'snippet': job['description'],
                    'screenshot': NOT_AVAILABLE
                }

                all_jobs.append(job_record)
                
                if len(all_jobs) >= max_results:
                    break

            # __ if we have enough jobs, stop:
            if len(all_jobs) >= max_results:
                break

            # __ scroll to load more jobs:
            logger.info(f"Loaded {len(all_jobs)} jobs so far, scrolling for more... (attempt {scroll_attempts + 1}/{max_scroll_attempts})")
            if self._scroll_to_load_more():
                scroll_attempts += 1
                time.sleep(2)
            else:
                break

        # __ trim to max_results:
        all_jobs = all_jobs[:max_results]

        # __ log final results:
        for idx, job in enumerate(all_jobs, 1):
            title_short = job['title'][:50]
            company_short = job['company'][:30]
            logger.info(f"[{idx}/{max_results}] {title_short} @ {company_short}")

        logger.info(f"\n{'='*80}")
        logger.info(f"Scraping complete: {len(all_jobs)} jobs collected")
        logger.info(f"{'='*80}")
        return all_jobs

    def close(self):
        if self._context_manager:
            try:
                self._context_manager.__exit__(None, None, None)
                logger.info("Browser closed")
            except Exception as e:
                logger.debug(f"Error closing browser: {e}")