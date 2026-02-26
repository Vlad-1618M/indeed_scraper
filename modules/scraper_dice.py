#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Dice.com Scraper """

import re
import time
import random
import logging
from pathlib import Path
from seleniumbase import SB
from datetime import datetime
from modules.cfg import get_base_url

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_DELAY_MIN = 1
DEFAULT_DELAY_MAX = 3
PAGE_DELAY_MIN = 2
PAGE_DELAY_MAX = 4
NOT_AVAILABLE = "Not Available"


class DiceScraper:
    """Dice.com scraper"""

    def __init__(self, headless=False, incognito=False, window_size="maximized", proxy=None, screenshots=False, artifacts_dir=None):
        self.window_size = window_size
        self.screenshots = screenshots
        self.incognito = incognito
        self.headless = headless
        self.proxy = proxy
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
        self.details_dir = self.screenshots_dir / "details"

        if self.screenshots:
            self.pages_dir.mkdir(parents=True, exist_ok=True)
            self.cards_dir.mkdir(parents=True, exist_ok=True)
            self.details_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Page screenshots: {self.pages_dir}")
            logger.info(f"Card screenshots: {self.cards_dir}")
            logger.info(f"Detail screenshots: {self.details_dir}")

        self._start_browser()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _start_browser(self):
        logger.info("Starting browser in UC Mode...")
        try:
            sb_options = dict(
                uc=True,
                headed=not self.headless,
                incognito=self.incognito,
                uc_cdp_events=True,
            )
            if self.proxy:
                proxy_str = self.proxy.get('server', '')
                if self.proxy.get('username'):
                    auth = f"{self.proxy['username']}:{self.proxy.get('password', '')}"
                    server = proxy_str.replace('http://', '').replace('https://', '')
                    proxy_str = f"{auth}@{server}"
                sb_options['proxy'] = proxy_str
            self._context_manager = SB(**sb_options)
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

    def _build_search_url(self, query, location="", remote_only=False, page=1):
        """Build Dice.com search URL"""
        base_url = get_base_url(jb_board="dice")
        params = []
        
        if query:
            params.append(f"q={query.replace(' ', '+')}")
        
        if remote_only:
            params.append("filters.workplaceTypes=Remote")
        
        if location and location.lower() != "remote" and not remote_only:
            params.append(f"location={location.replace(' ', '+')}")
        
        params.append(f"page={page}")
        params.append("pageSize=20")
        
        return f"{base_url}?{'&'.join(params)}" if params else base_url

    def _dismiss_cookie_dialog(self):
        """Dismiss cookie dialog"""
        try:
            time.sleep(3)
            script = """
            (function() {
                const btns = Array.from(document.querySelectorAll('button'));
                const reject = btns.find(b => b.textContent.toLowerCase().trim() === 'reject all');
                if (reject) {
                    reject.click();
                    return 'clicked';
                }
                return 'not_found';
            })();
            """
            
            result = self.sb.execute_script(script)
            if result == 'clicked':
                logger.info("✓ Cookie dialog dismissed")
                time.sleep(2)
            return True
        except Exception:
            return True

    def _wait_for_content(self):
        """Wait for job listings to load"""
        try:
            logger.info("Waiting for job listings...")
            self._dismiss_cookie_dialog()
            time.sleep(5)
            
            for attempt in range(30):
                script = """
                (function() {
                    const articles = document.querySelectorAll('[role="article"]');
                    if (articles.length === 0) return {loaded: false};
                    
                    for (let article of articles) {
                        const links = article.querySelectorAll('a');
                        for (let link of links) {
                            if (link.textContent.trim().length > 5) {
                                return {loaded: true, count: articles.length};
                            }
                        }
                    }
                    return {loaded: false};
                })();
                """
                
                result = self.sb.execute_script(script)
                if result.get('loaded'):
                    logger.info(f"✓ Content loaded ({result.get('count')} jobs)")
                    time.sleep(2)
                    return True
                time.sleep(0.5)
            
            logger.warning("Content didn't load")
            return False
        except Exception as e:
            logger.error(f"Error waiting: {e}")
            return False
    
# ______________________________________________________________________________________________________________

    def _scroll_to_load_all_jobs(self):
        """ Lazy load trigger with page scroll | helps to see all job cards """
        try:
            logger.info("Scrolling page ...")
            
            # Get initial count
            init_count_js_script = "return document.querySelectorAll('[role=\"article\"]').length;"
            initial_count = self.sb.execute_script(init_count_js_script)
            
            # Scroll in steps
            for scroll_attempt in range(5):
                # Scroll down
                self.sb.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.5)
                
                # Check if more jobs loaded
                current_count = self.sb.execute_script(init_count_js_script)
                
                if current_count > initial_count:
                    logger.debug(f"  Jobs loaded: {initial_count} → {current_count}")
                    initial_count = current_count
                else:
                    # No new jobs, we're done
                    break
            
            # Scroll back to top
            self.sb.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            final_count = self.sb.execute_script(init_count_js_script)
            logger.info(f"✓ Scroll complete: {final_count} jobs loaded")
            
            return True
        except Exception as e:
            logger.debug(f"Scroll error: {e}")
            return False

# ______________________________________________________________________________________________________________


    def _extract_jobs(self, page_num):
        """Extract jobs from current page"""
        try:
            script = """
            (function() {
                const articles = Array.from(document.querySelectorAll('[role="article"]'));
                
                function clean(text) {
                    if (!text) return '';
                    const txt = document.createElement('textarea');
                    txt.innerHTML = text;
                    return txt.value.replace(/\\s+/g, ' ').trim();
                }
                
                return articles.map((article, idx) => {
                    const data = {
                        card_index: idx,
                        title: 'Not Available',
                        company: 'Not Available',
                        job_location: 'Not Available',
                        salary: 'Not Available',
                        job_type: 'Not Available',
                        posted_date: 'Not Available',
                        description: 'Not Available',
                        url: 'Not Available',
                        job_id: 'Not Available',
                        easy_apply: false
                    };
                    
                    // Get ALL links
                    const allLinks = Array.from(article.querySelectorAll('a'));
                    
                    // Find job detail link (this is the real job URL)
                    const jobDetailLink = allLinks.find(l => l.href && l.href.includes('job-detail'));
                    if (jobDetailLink) {
                        data.url = jobDetailLink.href;
                        const match = jobDetailLink.href.match(/job-detail\\/([a-f0-9-]+)/);
                        if (match) data.job_id = match[1];
                        
                        // Title might be in this link or nearby
                        if (jobDetailLink.textContent.trim().length > 3) {
                            data.title = clean(jobDetailLink.textContent);
                        }
                    }
                    
                    // If no title yet, find first link with substantial text
                    if (data.title === 'Not Available') {
                        const linksWithText = allLinks.filter(l => l.textContent.trim().length > 10);
                        if (linksWithText.length > 0) {
                            data.title = clean(linksWithText[0].textContent);
                        }
                    }
                    
                    // Find company
                    const companyLink = allLinks.find(l => l.href && l.href.includes('company-profile'));
                    if (companyLink) {
                        data.company = clean(companyLink.textContent);
                    }
                    
                    // Extract from text
                    const text = article.textContent;
                    
                    const locMatch = text.match(/Remote|([A-Z][a-z]+,\\s*[A-Z]{2})/);
                    if (locMatch) data.job_location = clean(locMatch[0]);
                    
                    const dateMatch = text.match(/Today|Yesterday|\\d+d ago|\\d+ days? ago/i);
                    if (dateMatch) data.posted_date = clean(dateMatch[0]);
                    
                    const salMatch = text.match(/\\$[\\d,]+(K)?\\s*-\\s*\\$[\\d,]+(K)?/);
                    if (salMatch) data.salary = clean(salMatch[0]);
                    
                    const typeMatch = text.match(/Contract|Full[- ]?time|Part[- ]?time/i);
                    if (typeMatch) data.job_type = clean(typeMatch[0]);
                    
                    // Description
                    const paras = article.querySelectorAll('p, div');
                    let longest = '';
                    for (const p of paras) {
                        const txt = clean(p.textContent);
                        if (txt.length > longest.length && txt.length > 50) {
                            longest = txt;
                        }
                    }
                    if (longest) data.description = longest.substring(0, 500);
                    
                    // Easy Apply
                    const btns = article.querySelectorAll('button, a');
                    for (const btn of btns) {
                        if (btn.textContent.toLowerCase().includes('easy apply')) {
                            data.easy_apply = true;
                            break;
                        }
                    }
                    
                    return data;
                });
            })();
            """
            
            jobs = self.sb.execute_script(script)
            
            if jobs:
                valid = [j for j in jobs if j['title'] != 'Not Available' and j['url'] != 'Not Available']
                logger.info(f"Extracted {len(valid)} valid jobs from page {page_num}")
                return valid
            
            return []
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return []

    def search_jobs(self, query, location="", remote_only=False, min_salary=None, max_salary=None, date_posted=None, max_results=25):
        """Phase 1: Scrape job listings"""
        
        logger.info(f"Searching Dice.com: '{query}' in '{'Remote' if remote_only else location}'")
        logger.info(f"Max results: {max_results}")
        
        session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        all_jobs = []
        page_num = 1
        pages_used = 0
        seen_ids = set()
        
        while len(all_jobs) < max_results and page_num <= 10:
            pages_used = page_num
            url = self._build_search_url(query, location, remote_only, page_num)
            logger.info(f"\nPage {page_num}: {url}")
            
            try:
                self.sb.open(url)
                time.sleep(random.uniform(PAGE_DELAY_MIN, PAGE_DELAY_MAX))
            except Exception as e:
                logger.error(f"Failed to load page: {e}")
                break
            
            if not self._wait_for_content():
                break

            self._scroll_to_load_all_jobs()
            
            if self.screenshots:
                try:
                    filename = f"page_{page_num:02d}_{query.replace(' ', '_')}_{session_ts}.png"
                    self.sb.save_screenshot(str(self.pages_dir / filename), folder="")
                except Exception:
                    pass
            
            jobs_data = self._extract_jobs(page_num)
            
            if not jobs_data:
                break
            
            jobs_added = 0
            for job in jobs_data:
                if len(all_jobs) >= max_results:
                    break
                
                if job['job_id'] != 'Not Available' and job['job_id'] in seen_ids:
                    continue
                if job['job_id'] != 'Not Available':
                    seen_ids.add(job['job_id'])
                
                job_record = {
                    'query': query,
                    'location': location,
                    'page': page_num,
                    'scraped_at': datetime.now().isoformat(),
                    'title': job['title'],
                    'company': job['company'],
                    'job_location': job['job_location'],
                    'salary': job['salary'],
                    'job_type': job['job_type'],
                    'posted_date': job['posted_date'],
                    'posted': job['posted_date'],
                    'url': job['url'],
                    'job_id': job['job_id'],
                    'easy_apply': job['easy_apply'],
                    'apply_button_text': 'Easy Apply' if job['easy_apply'] else 'Apply',
                    'description': job['description'],
                    'snippet': job['description'],
                    'screenshot': NOT_AVAILABLE,
                    'detailed_scraped': False
                }
                
                all_jobs.append(job_record)
                jobs_added += 1
            
            logger.info(f"Added {jobs_added} jobs (total: {len(all_jobs)}/{max_results})")
            
            if len(all_jobs) >= max_results:
                break
            
            page_num += 1
            time.sleep(random.uniform(DEFAULT_DELAY_MIN, DEFAULT_DELAY_MAX))
        
        logger.info(f"\n{'='*80}")
        logger.info("Phase 1 Results")
        logger.info(f"{'='*80}")
        for idx, job in enumerate(all_jobs, 1):
            title = (job.get('title') or '')[:60]
            company = (job.get('company') or '')[:30]
            logger.info(f"[{idx}/{len(all_jobs)}] {title} @ {company}")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Phase 1 complete: {len(all_jobs)} jobs from {pages_used} pages")
        logger.info(f"{'='*80}\n")
        
        return all_jobs

    def scrape_job_details(self, jobs):
        """Phase 2: Get detailed job information"""
        
        logger.info(f"\n{'='*80}")
        logger.info("Phase 2: Scraping detailed job information")
        logger.info(f"{'='*80}\n")
        
        detailed_count = 0
        
        for idx, job in enumerate(jobs, 1):
            logger.info(f"[{idx}/{len(jobs)}] {(job.get('title') or '')[:60]}")
            
            if not job.get('url') or job['url'] == 'Not Available':
                logger.warning("\n\tNo URL")
                continue
            
            try:
                # Navigate to job detail page
                self.sb.open(job['url'])
                time.sleep(6)
                
                # Take screenshot
                if self.screenshots:
                    try:
                        safe_title = re.sub(r'[^\w\s-]', '', (job.get('title') or ''))[:30].replace(' ', '_')
                        filename = f"detail_{idx:03d}_{safe_title}.png"
                        self.sb.save_screenshot(str(self.details_dir / filename), folder="")
                    except Exception:
                        pass
                
                # Extract details: skills with multiple selectors + fallback from description
                script = """
                (function() {
                    try {
                        function clean(text) {
                            if (!text) return '';
                            return text.replace(/\\s+/g, ' ').trim();
                        }
                        function unique(arr) {
                            const seen = new Set();
                            return arr.filter(s => {
                                const k = s.toLowerCase();
                                if (seen.has(k) || s.length < 2) return false;
                                seen.add(k);
                                return true;
                            });
                        }
                        
                        let skills = [];
                        const selectors = [
                            '[class*="skill"]', '[class*="tag"]', '[class*="badge"]', '[class*="chip"]', '[class*="pill"]',
                            'button[class*="skill"]', 'span[class*="skill"]', 'a[class*="skill"]',
                            '[data-testid*="skill"]', '[data-testid*="tag"]'
                        ];
                        for (const sel of selectors) {
                            try {
                                document.querySelectorAll(sel).forEach(el => {
                                    const t = clean(el.textContent);
                                    if (t.length >= 2 && t.length < 50 && !/^\\d+$/.test(t))
                                        skills.push(t);
                                });
                            } catch (_) {}
                        }
                        skills = unique(skills).slice(0, 25);
                        
                        const fullText = document.body.textContent || '';
                        const full_description = clean(fullText.substring(0, 3000));
                        
                        if (skills.length === 0 && full_description) {
                            const skillsMatch = fullText.match(/(?:skills?|required|qualifications?|experience with)[:\\s]+([^.\\n]{10,500})/i);
                            if (skillsMatch) {
                                const block = skillsMatch[1].replace(/[,;|]|\\band\\b/gi, ',').split(',')
                                    .map(s => clean(s)).filter(s => s.length >= 2 && s.length < 40);
                                skills = unique(skills.concat(block)).slice(0, 25);
                            }
                        }
                        
                        return {
                            skills: skills,
                            full_description: full_description,
                            page_title: document.title
                        };
                    } catch (e) {
                        return {skills: [], full_description: '', error: e.toString()};
                    }
                })();
                """
                
                details = self.sb.execute_script(script)
                
                if details:
                    job['job_details'] = details
                    job['detailed_scraped'] = True
                    detailed_count += 1
                    details_stream = f"\t Details:\t{len(details.get('skills', []))} skills, {len(details.get('full_description', ''))} chars"
                    logger.info(details_stream)
                time.sleep(random.uniform(DEFAULT_DELAY_MIN, DEFAULT_DELAY_MAX))
                
            except Exception as e:
                logger.error(f"  ✗ Error: {str(e)[:80]}")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Phase 2 complete: {detailed_count}/{len(jobs)} jobs detailed")
        logger.info(f"{'='*80}\n")
        
        return jobs

    def close(self):
        if self._context_manager:
            try:
                self._context_manager.__exit__(None, None, None)
                logger.info("Browser closed")
            except Exception:
                pass

if __name__ == "__main__":
    pass
    