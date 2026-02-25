#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Indeed Job Scraper - Main Entry Point
Automated job scraping tool for Indeed.com

Supports multiple scraper backends:
- SeleniumBase UC Mode (recommended): Undetected ChromeDriver for Cloudflare bypass:
- Camoufox: Anti-detect Firefox browser (experimental):
- Playwright: Standard Playwright with stealth patches:
- Selenium: Legacy support
"""

import sys
from datetime import datetime
from pathlib import Path

# ___ auto handle PYTHONPATH imports:
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modules.args_parser import parse_args
from modules.file_utils import save_jobs_json, save_log
from modules.ui import (
    display_jobs_interactive,
    prompt_interactive_config,
    prompt_login,
    print_header,
    print_summary
)


def get_scraper(scraper_type, headless=False, incognito=False, window_size="maximized", proxy=None, screenshots=False, artifacts_dir=None):
    """ lazy imports to enable dynamic scraper instance:
        Args:
            scraper_type (str):     --> Type of scraper - 'seleniumbase', 'camoufox', 'playwright', or 'selenium'
            headless (bool):        --> Run in headless mode:
            incognito (bool):       --> Use incognito/fresh context:
            window_size (str):      --> Window size:
            proxy (dict):           --> Proxy configuration:
            screenshots (bool):     --> Enable screenshot capture:
            artifacts_dir (str):    --> Artifacts directory path:
        Returns: Scraper instance """
    
    scraper_type = scraper_type.lower()
    if scraper_type == 'seleniumbase':
        try:
            from modules.seleniumbase_scraper import SeleniumBaseIndeedScraper
            print("[*]\tAttempting to use SeleniumBase UC Mode:")
            return SeleniumBaseIndeedScraper(
                headless=headless,
                incognito=incognito,
                window_size=window_size,
                proxy=proxy,
                screenshots=screenshots,
                artifacts_dir=artifacts_dir
            )
        except ImportError as e:
            print(f"[!]\tSeleniumBase not available: {e}")
            print("\t\tInstall with: pip install seleniumbase")
            print("\t\tBack to Camoufox ...")
            scraper_type = 'camoufox'
    
    if scraper_type == 'camoufox':
        try:
            from modules.camoufox_scraper import CamoufoxIndeedScraper
            print("[*]\tAttempting to use Camoufox anti-detect browser:")
            return CamoufoxIndeedScraper(
                headless=headless,
                incognito=incognito,
                window_size=window_size,
                proxy=proxy
            )
        except ImportError as e:
            print(f"[!]\tCamoufox not available: {e}")
            print("\t\tInstall with: pip install -U camoufox[geoip] && camoufox fetch")
            print("\t\tBack to Playwright ...")
            scraper_type = 'playwright'
    
    if scraper_type == 'playwright':
        try:
            from modules.playwright_scraper import PlaywrightIndeedScraper
            print("[*]\tAttempting to use Playwright browser:")
            return PlaywrightIndeedScraper(
                headless=headless,
                incognito=incognito,
                window_size=window_size,
                proxy=proxy,
                screenshots=screenshots,
                artifacts_dir=artifacts_dir
            )
        except ImportError as e:
            print(f"[!]\tPlaywright not available: {e}")
            print("\t\tBack to Selenium ...")
            scraper_type = 'selenium'
    
    if scraper_type == 'selenium':
        try:
            from modules.selenium_scraper import IndeedJobScraper
            print("[*]\tAttempting to use Selenium browser:")
            return IndeedJobScraper(
                headless=headless,
                incognito=incognito,
                window_size=window_size
            )
        except ImportError as e:
            print(f"[X]\tSelenium not available: {e}")
            raise RuntimeError("No scraper backend available. Please install seleniumbase, camoufox, playwright, or selenium.")
    
    raise ValueError(f"Unknown scraper type: {scraper_type}")


def run_interactive_mode():
    """Run scraper in interactive mode | enable user prompts:"""
    
    print_header("Indeed Job Scraper - Interactive Mode:")
    
    # ___ scraper type prompt:
    print("\nScraper options:")
    print("  1. SeleniumBase UC Mode (recommended - best for Cloudflare bypass)")
    print("  2. Camoufox (experimental)")
    print("  3. Playwright")
    print("  4. Selenium")
    scraper_choice = input("Choice (1/2/3/4, default=1): ").strip() or "1"
    
    scraper_types = {'1': 'seleniumbase', '2': 'camoufox', '3': 'playwright', '4': 'selenium'}
    scraper_type = scraper_types.get(scraper_choice, 'seleniumbase')
    
    # ___ login prompt:
    email, password = prompt_login()
    
    # ___ ask for incognito:
    use_incognito = input("Run in incognito mode? (y/n): ").lower() == 'y'
    
    # ___ ask for window size:
    print("\nWindow size options:")
    print("  1. Maximized (full screen)")
    print("  2. Custom size (e.g., 1280x720)")
    size_choice = input("Choice (1 or 2, default=1): ").strip() or "1"
    
    if size_choice == "2":
        window_size = input("Enter size (WIDTHxHEIGHT, e.g., 1280x720): ").strip() or "1280x720"
    else:
        window_size = "maximized"
    
    # ___ ask for screenshots:
    use_screenshots = input("Capture screenshots? (y/n): ").lower() == 'y'
    
    # ___ ask for proxy |  Camoufox/SeleniumBase ONLY:
    proxy = None
    if scraper_type in ['camoufox', 'seleniumbase']:
        use_proxy = input("Use proxy? (y/n): ").lower() == 'y'
        if use_proxy:
            proxy_server = input("Proxy server (e.g., http://proxy.example.com:8080): ").strip()
            proxy_user = input("Proxy username (or empty): ").strip()
            proxy_pass = input("Proxy password (or empty): ").strip()
            proxy = {'server': proxy_server}
            if proxy_user:
                proxy['username'] = proxy_user
                proxy['password'] = proxy_pass
    
    # ___ get and configure scraper instance:
    scraper = get_scraper(
        scraper_type=scraper_type, headless=False, 
        incognito=use_incognito, window_size=window_size, 
        proxy=proxy,screenshots=use_screenshots
        )
    
    try:
        # ___ login if credentials provided and true:
        if email and password:
            if hasattr(scraper, 'login'):
                if not scraper.login(email, password):
                    print("\n[X] Login failed - continuing without login")
                    input("Press Enter to continue...")
        
        # ___ get search configuration:
        config = prompt_interactive_config()
        
        # ___ execute/run search params:
        print("\n" + "="*80)
        start_time = datetime.now()
        
        jobs = scraper.search_jobs(
            query=config['query'],
            location=config['location'],
            remote_only=config['remote_only'],
            min_salary=config['min_salary'],
            max_salary=config['max_salary'],
            date_posted=config['date_posted'],
            max_results=config['max_results']
        )
        
        end_time = datetime.now()
        
        if jobs:
            print_summary(1, len(jobs), start_time, end_time)
            
            # ___ save results:
            filename = config['query'].replace(' ', '_').lower()
            filepath = save_jobs_json(jobs, filename=filename)
            print(f"\n\t[+] Results saved to: {filepath}")
            print(f"\t[+] Use ursl in {filepath} <-- .json artifact to apply for a job:")
            
            if use_screenshots:
                print("[+] Screenshots saved to: artifacts/screenshots/")
            
            # ___ save logs:
            save_log(f"Interactive search completed: {len(jobs)} jobs for '{config['query']}'")
            
            # ___ interactive browser:
            browse = input("\nBrowse jobs interactively? (y/n): ").lower() == 'y'
            if browse:
                display_jobs_interactive(jobs)
        else:
            print("\n[X] No jobs extracted")
            save_log(f"Interactive search failed: no jobs for '{config['query']}'", log_type="error")
            
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        save_log("Interactive mode interrupted by user", log_type="info")
    except Exception as e:
        print(f"\n[X] Error: {e}")
        save_log(f"Interactive mode error: {e}", log_type="error")
        import traceback
        traceback.print_exc()
    finally:
        input("\nPress Enter to close auto-controlled browser...")
        scraper.close()


def run_auto_mode(args):
    """ Run scraper in automated mode | enable cli arguments:
        Args:
            args: Parsed command-line arguments: """
    print_header("Indeed Job Scraper - Automated Mode:")
    
    start_time = datetime.now()
    print(f"Started: {start_time.strftime('%B %d, %Y at %I:%M %p')}")
    
    # ___ build proxy config if provided and true:
    proxy = None
    if hasattr(args, 'proxy') and args.proxy:
        proxy = {'server': args.proxy}
        if hasattr(args, 'proxy_user') and args.proxy_user:
            proxy['username'] = args.proxy_user
            proxy['password'] = getattr(args, 'proxy_pass', '')
    
    # ___ get scraper type from args:
    scraper_type = getattr(args, 'scraper', 'seleniumbase')
    
    # ___ get screenshots setting:
    screenshots = getattr(args, 'screenshots', False)
    screenshots_dir = getattr(args, 'screenshots_dir', 'artifacts/screenshots')
    
    scraper = get_scraper(
        scraper_type=scraper_type,
        headless=args.headless,
        incognito=args.incognito,
        window_size=args.window_size,
        proxy=proxy,
        screenshots=screenshots,
        artifacts_dir=Path(screenshots_dir).parent if screenshots_dir else None
    )
    
    try:
        # ___ Login if credentials provided:
        if args.email and args.password:
            print("\nAttempting login...")
            if hasattr(scraper, 'login'):
                if not scraper.login(args.email, args.password):
                    print("[X] Login failed - continuing without login")
                    save_log("Auto mode: login failed", log_type="error")
        
        # ___ figureout queries:
        queries = []
        if args.queries:
            queries = [q.strip() for q in args.queries.split(',')]
        elif args.query:
            queries = [args.query]
        else:
            print("[X] Error: No query specified. Use --query or --queries")
            save_log("Auto mode: no query specified", log_type="error")
            return
        
        all_jobs = []
        
        # ___ run searches:
        for query in queries:
            print(f"\n{'='*80}")
            print(f"Searching: {query}")
            print(f"{'='*80}")
            
            jobs = scraper.search_jobs(
                query=query,
                location=args.location,
                remote_only=args.remote,
                min_salary=args.min_salary,
                max_salary=args.max_salary,
                date_posted=args.days,
                max_results=args.max
            )
            
            if jobs:
                print(f"[+] Found {len(jobs)} jobs for '{query}'")
                
                # ___ save individual search results:
                filename = query.replace(' ', '_').lower()
                save_jobs_json(jobs, filename=filename, output_dir=args.output_dir)
                # filepath = save_jobs_json(jobs, filename=filename, output_dir=args.output_dir)
                
                save_log(f"Auto mode: scraped {len(jobs)} jobs for '{query}'")
                all_jobs.extend(jobs)
            else:
                print(f"[X]\tNo jobs found for '{query}'")
                save_log(f"Auto mode: no jobs found for '{query}'", log_type="error")
        
        end_time = datetime.now()
        
        # ___ output summary read:
        print_summary(len(queries), len(all_jobs), start_time, end_time)
        
        if screenshots:
            print(f"[+] Screenshots saved to: {screenshots_dir}/")
        
        # ___ save combined results | if multiple queries:
        if len(queries) > 1 and all_jobs:
            combined_filename = f"combined_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            save_jobs_json(all_jobs, filename=combined_filename, output_dir=args.output_dir)
            save_log(f"Auto mode: saved combined results ({len(all_jobs)} jobs)")
        
    except Exception as e:
        print(f"\n[X] Error in auto mode: {e}")
        save_log(f"Auto mode error: {e}", log_type="error")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()
        print("\n[+] Browser closed")


def main():
    """main"""
    args = parse_args()
    
    if args.auto:
        run_auto_mode(args)
    else:
        run_interactive_mode()


if __name__ == "__main__":
    main()

# =========================================================================================================================================================================================================================
#                                                                  *** CLI Examples Refes ***
# =========================================================================================================================================================================================================================
#
# python main.py                                                                                       | <-- INTERACTIVE MODE:
# python main.py --auto --query "DevOps Engineer"                                                      | <-- AUTO MODE - Basic:
# python main.py --auto --scraper seleniumbase --query "DevOps Engineer" --location "Remote" --remote  | <-- AUTO MODE - With SeleniumBase UC Mode (default, best for Cloudflare):
# python main.py --auto --scraper seleniumbase --query "SDET" --remote --screenshots --max 25          | <-- AUTO MODE - With screenshots (for cross-referencing with JSON):
# python main.py --auto --scraper camoufox --query "Software Engineer" --location "New York"           | <-- AUTO MODE - With Camoufox (experimental):
# python main.py --auto --scraper playwright --query "Software Engineer" --location "New York"         | <-- AUTO MODE - With Playwright fallback:
# python main.py --auto --query "SDET" --proxy "http://user:pass@proxy.example.com:8080"               | <-- AUTO MODE - With proxy (recommended for production):
# python main.py --auto --query "DevOps" --remote --headless                                           | <-- AUTO MODE - Headless (for servers/cron):
# python main.py --auto --query "Software Engineer" --min-salary 150000 --max-salary 200000            | <-- AUTO MODE - With salary filter:
# python main.py --auto --query "DevOps" --days 7                                                      | <-- AUTO MODE - Posted within last N days:
# python main.py --auto --queries "DevOps,SRE,Platform Engineer" --remote --days 7                     | <-- AUTO MODE - Multiple queries:
# python main.py --auto --query "DevOps" --max 50                                                      | <-- AUTO MODE - Max results:
# python main.py --auto --query "DevOps" --output-dir "./results"                                      | <-- AUTO MODE - Custom output directory:
# python main.py --auto --query "DevOps" --incognito                                                   | <-- AUTO MODE - Incognito (fresh session):
# python main.py --auto --query "DevOps" --window-size "1280x720"                                      | <-- AUTO MODE - Custom window size:
# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#  python main.py --auto --scraper seleniumbase --query "DevOps Engineer" --location "Remote" --remote --days 7 --max 50 --screenshots --output-dir "./artifacts/json" | <-- AUTO MODE - Full example with screenshots:
#   
# ----- if cronjob is needed ---- 
#   CRON JOB (daily at 9am) - Example:  
#   0 9 * * * cd /path/to/scraper && python main.py --auto --query "DevOps" --remote --days 1 --headless
#
# =========================================================================================================================================================================================================================
