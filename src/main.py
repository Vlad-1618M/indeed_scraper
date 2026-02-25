#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Indeed Job Scraper - Main Entry Point
    Cookie-based authentication with SeleniumBase UC Mode: """

import sys
import subprocess
from pathlib import Path
from datetime import datetime

# ___ auto-handle PYTHONPATH imports:
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modules import ui
from modules.args_parser import parse_args
from modules import cookies_age as cookies
from modules.file_utils import save_jobs_json, save_log


def prompt_cookie_setup():
    """Guide user through cookie setup if cookies don't exist:
        Returns: bool: True if setup completed or user wants to continue, False otherwise: """
    
    print("\n\t\t*** AUTHENTICATION REQUIRED ***\n", end="=" * 80 + "\n")
    print("Indeed requires authentication to view multiple pages of job listings.")
    print("\nThis scraper uses COOKIES instead of traditional login for better reliability:\n", end="=" * 80 + "\n")
    print("\nWhat are cookies ?")
    print("  - Saved login sessions that keep you logged in:")
    print("  - Login ONCE manually, cookies saved for 30 days:")
    print("  - No email/password needed on future runs:\n", end="=" * 80 + "\n")
    print("\nCookie setup steps:")
    print("  1. Run cookie setup script:")
    print("  2. Login manually in browser that opens:")
    print("  3. Cookies saved automatically:")
    print("  4. Use scraper normally for 30 days:\n", end="=" * 80 + "\n")
    setup_now = input("\nRun cookie setup now? (y/n): ").lower()
    
    if setup_now == 'y':
        print("\n[*] Starting cookie setup...")
        print("[*] Browser will open - login when prompted:\n", end="=" * 80 + "\n")
        
        try:
            # __ get_cookies.py call:
            result = subprocess.run([sys.executable, "modules/get_cookies.py", "--auto"], check=False)
            
            if result.returncode == 0:
                print("\n" + "="*80)
                print("COOKIE SETUP COMPLETE !\n", end="=" * 80 + "\n")
                print("You can now use the scraper without logging in:")
                print("Cookies will last for 30 days:\n", end="=" * 80 + "\n")
                return True
            else:
                print("\n" + "="*80)
                print("\tCOOKIE SETUP FAILED !\n", end="=" * 80 + "\n")
                print("Try running manually:\t--> python3 modules/get_cookies.py --auto\n", end="=" * 80 + "\n")
                return False
        
        except FileNotFoundError:
            print("\n" + "="*80)
            print("COOKIE SCRIPT NOT FOUND:\n", end="=" * 80 + "\n")
            print("Run manually:\t--> python3 modules/get_cookies.py --auto\n", end="=" * 80 + "\n")
            return False
    else:
        print("\nSETUP SKIPPED\n", end="=" * 80 + "\n")
        print("Setup cookies later:\t--> python3 modules/get_cookies.py --auto")
        print("WARNING:\t--> Without cookies Indeed blocks multi-page scraping:\n", end="=" * 80 + "\n")
        continue_anyway = input("\nContinue without cookies? (y/n): ").lower()
        return continue_anyway == 'y'


def get_scraper(board="indeed", headless=False, incognito=False, window_size="maximized", proxy=None, screenshots=False, artifacts_dir=None, cookie_file=None):
    """ Initialize SeleniumBase UC Mode scraper for specified job board:
        Args:
            board (str):        Job board to scrape ("indeed", "glassdoor", or "dice")
            headless (bool):    Run in headless mode
            incognito (bool):   Use incognito mode
            window_size (str):  Window size ("maximized" or "WIDTHxHEIGHT")
            proxy (dict):       Proxy config {'server': '...', 'username': '...', 'password': '...'}
            screenshots (bool): Enable screenshot capture
            artifacts_dir (str): Artifacts directory path
            cookie_file (str):  Path to cookie file
        Returns: Scraper instance (Indeed, Glassdoor, or Dice)
        Raises:
            ImportError: If SeleniumBase not installed
            RuntimeError: If scraper initialization fails
            ValueError: If invalid board specified """
    
    try:
        # __ lazy import based on board selection:
        if board.lower() == "indeed":
            from modules.scraper_indeed import SeleniumBaseIndeedScraper
            print("[*]\tInitializing Indeed SeleniumBase UC Mode:")
            return SeleniumBaseIndeedScraper(
                headless=headless,
                incognito=incognito,
                window_size=window_size,
                proxy=proxy,
                screenshots=screenshots,
                artifacts_dir=artifacts_dir,
                cookie_file=cookie_file
            )
        
        elif board.lower() == "glassdoor":
            from modules.scraper_glassdoor import GlassdoorScraper
            print("[*]\tInitializing Glassdoor SeleniumBase UC Mode:")
            print("[*]\tNote: Glassdoor scraper runs without cookies:")
            return GlassdoorScraper(
                headless=headless,
                incognito=incognito,
                window_size=window_size,
                proxy=proxy,
                screenshots=screenshots,
                artifacts_dir=artifacts_dir
                # cookie_file=cookie_file
            )
        
        elif board.lower() == "dice":
            from modules.scraper_dice import DiceScraper
            print("[*]\tInitializing Dice SeleniumBase UC Mode:")
            print("[*]\tNote: Dice scraper runs without cookies:")
            return DiceScraper(
                headless=headless,
                incognito=incognito,
                window_size=window_size,
                proxy=proxy,
                screenshots=screenshots,
                artifacts_dir=artifacts_dir
            )
        
        else:
            raise ValueError(f"Unsupported job board: {board}. Use 'indeed', 'glassdoor', or 'dice'")
    
    except ImportError as module_import_error:
        print(f"[!] SeleniumBase not available: {module_import_error}")
        print("\nInstall with: pip install seleniumbase")
        raise RuntimeError("SeleniumBase not installed") from module_import_error


def run_interactive_mode():
    """Run scraper in interactive mode with user prompts."""
    ui.print_header("Indeed Job Scraper - Interactive Mode")
    
    # ___ job board selection FIRST to know if cookies needed:
    job_board_selector = ui.job_board_portal()
    
    # ___ cookies check | show status (only for Indeed):
    has_cookies = False
    if job_board_selector == "indeed":
        has_cookies = cookies.print_cookie_file_info()
        
        if has_cookies:
            print("\tAuthenticated - no login needed!")
        else:
            if not prompt_cookie_setup():
                print("\nCannot continue without authentication\n")
                return
            has_cookies = cookies.print_cookie_file_info()
            if not has_cookies:
                print("\n\tCookie setup failed - exiting")
                return
        
        # ___ confirm cookies used for auth:
        if has_cookies:
            print("\n" + "="*80)
            print("AUTHENTICATION: Using saved cookies:")
            print("="*80)
            print("Your saved login session will be used automatically:")
            print("No email/password needed:")
            print("="*80)
    elif job_board_selector == "glassdoor":
        print("\n" + "="*80)
        print("GLASSDOOR: --> without cookies:")
        print("="*80)
        print("Attempting to scrape without authentication:")
        print("Note: May be limited to ~10-20 jobs before login wall or next page:")
        print("="*80)
    elif job_board_selector == "dice":
        print("\n" + "="*80)
        print("DICE: --> without cookies:")
        print("="*80)
        print("Attempting to scrape without authentication:")
        print("Note: Pagination support enabled - will scrape multiple pages:")
        print("="*80)
    
    # ___ browser configuration:
    use_incognito = input("\nRun in incognito mode? (y/n): ").lower() == 'y'
    
    print("\nWindow size:")
    print("  1. Maximized")
    print("  2. Custom (e.g., 1280x720)")
    size_choice = input("Choice (1 or 2, default=1): ").strip() or "1"
    
    if size_choice == "2":
        window_size = input("Size (WIDTHxHEIGHT): ").strip() or "1280x720"
    else:
        window_size = "maximized"
    
    use_screenshots = input("Capture screenshots? (y/n): ").lower() == 'y'
    
    # ___ proxy configuration:
    use_proxy = input("Use proxy? (y/n): ").lower() == 'y'
    proxy = None
    if use_proxy:
        proxy_server = input("Proxy server (e.g., http://proxy.com:8080): ").strip()
        proxy_user = input("Username (or empty): ").strip()
        proxy_pass = input("Password (or empty): ").strip()
        proxy = {'server': proxy_server}
        if proxy_user:
            proxy['username'] = proxy_user
            proxy['password'] = proxy_pass
    
    # ___  scraper init:
    scraper = get_scraper(
        board=job_board_selector,
        headless=False,
        incognito=use_incognito,
        window_size=window_size,
        proxy=proxy,
        screenshots=use_screenshots,
        cookie_file=cookies.cookie_artifact if (job_board_selector == "indeed" and has_cookies) else None
    )
    
    try:
        # ___ get search configuration:
        config = ui.prompt_interactive_config()
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
            # __ Dice-specific: ask if detailed scraping is needed:
            if job_board_selector == "dice":
                scrape_details = input("\nScrape detailed job information? (y/n): ").lower() == 'y'
                if scrape_details:
                    print("\n" + "="*80)
                    print("Starting Phase 2: Detailed job scraping...")
                    print("="*80)
                    jobs = scraper.scrape_job_details(jobs)
            
            ui.print_summary(1, len(jobs), start_time, end_time)
            filename = config['query'].replace(' ', '_').lower()
            
            filepath = save_jobs_json(jobs, filename=filename, jb_board=job_board_selector)
            
            print(f"\n[+] Results saved to: {filepath}")
            
            if use_screenshots:
                print("[+] Screenshots: artifacts/screenshots/")
            save_log(f"Interactive: {len(jobs)} jobs for '{config['query']}'")
            
            browse = input("\nBrowse jobs interactively? (y/n): ").lower() == 'y'
            if browse:
                ui.display_jobs_interactive(jobs)
        else:
            print("\nNo jobs found\n")
            save_log(f"Interactive: no jobs for '{config['query']}'", log_type="error")
            
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        save_log("Interactive mode interrupted", log_type="info")
    except Exception as e:
        print(f"\nError: {e}")
        save_log(f"Interactive error: {e}", log_type="error")
        import traceback
        traceback.print_exc()
    finally:
        input("\nPress Enter to close browser ...")
        scraper.close()


def run_auto_mode(args):
    """ Run scraper in automated mode with CLI arguments:
        Args: args (argparse.Namespace): Parsed command-line arguments: """
    ui.print_header("Indeed Job Scraper - Automated Mode")
    start_time = datetime.now()
    print(f"Started: {start_time.strftime('%B %d, %Y at %I:%M %p')}")
    
    # ___ job board selection from args (needed before cookie check):
    job_board_selector = getattr(args, 'board', 'indeed')
    
    # ___ cookies exist check (Indeed only):
    cookie_status = cookies.cookie_info()
    if job_board_selector == "indeed" and not cookie_status:
        print("\n" + "="*80)
        print("NO COOKIES FOUND\n", end="=" * 80 + "\n")
        print("Indeed requires authentication for multi-page scraping.")
        print("\nSetup cookies first:\t--> python3 modules/get_cookies.py --auto\n", end="=" * 80 + "\n")
        print("\nOne-time setup (2 minutes). Lasts 30 days:\n", end="=" * 80 + "\n")
        return
    
    if job_board_selector == "indeed" and cookie_status:
        print(f"\n✓ Using cookies: {cookies.cookie_artifact}")
        print(f"  Age: {cookie_status['age']} (updated {cookie_status['modified']})")
        if cookie_status['is_expired']:
            print(f"\tWARNING: Cookies may be expired ({cookie_status['age_days']} days)")
            print("\tRefresh if scraping fails: python3 modules/get_cookies.py --auto")
    
    # ___ build proxy config:
    proxy = None
    if hasattr(args, 'proxy') and args.proxy:
        proxy = {'server': args.proxy}
        if hasattr(args, 'proxy_user') and args.proxy_user:
            proxy['username'] = args.proxy_user
            proxy['password'] = getattr(args, 'proxy_pass', '')
    
    screenshots = getattr(args, 'screenshots', False)
    screenshots_dir = getattr(args, 'screenshots_dir', 'artifacts/screenshots')
    
    # ___ scraper init:
    scraper = get_scraper(
        board=job_board_selector,
        headless=args.headless,
        incognito=args.incognito,
        window_size=args.window_size,
        proxy=proxy,
        screenshots=screenshots,
        artifacts_dir=Path(screenshots_dir).parent if screenshots_dir else None,
        cookie_file=cookies.cookie_artifact if job_board_selector == "indeed" else None
    )
    
    try:
        # ___ parse queries:
        queries = []
        if args.queries:
            queries = [q.strip() for q in args.queries.split(',')]
        elif args.query:
            queries = [args.query]
        else:
            print("[X] No query specified. Use --query or --queries")
            save_log("Auto: no query specified", log_type="error")
            return
        
        all_jobs = []
        
        # ___ execute searches:
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
                
                filename = query.replace(' ', '_').lower()
                save_jobs_json(jobs, filename=filename, output_dir=args.output_dir, jb_board=job_board_selector)
                
                save_log(f"Auto: {len(jobs)} jobs for '{query}'")
                all_jobs.extend(jobs)
            else:
                print(f"[X] No jobs for '{query}'")
                save_log(f"Auto: no jobs for '{query}'", log_type="error")
        
        end_time = datetime.now()
        
        ui.print_summary(len(queries), len(all_jobs), start_time, end_time)
        
        if screenshots:
            print(f"[+] Screenshots: {screenshots_dir}/")
        
        # ___ save combined results if multiple queries:
        if len(queries) > 1 and all_jobs:
            combined = f"combined_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            save_jobs_json(all_jobs, filename=combined, output_dir=args.output_dir, jb_board=job_board_selector)
            save_log(f"Auto: combined {len(all_jobs)} jobs")
        
    except Exception as e:
        print(f"\n[X] Error: {e}")
        save_log(f"Auto error: {e}", log_type="error")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()
        print("\n[+] Browser closed")


def main():
    args = parse_args()
    if args.auto:
        run_auto_mode(args)
    else:
        run_interactive_mode()


if __name__ == "__main__":
    main()
