#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Argument Parser Module:
    Handles command-line argument parsing logic for Indeed scraper: """

import argparse

def parse_args():
    """ Parse command line arguments for auto and interactive modes:
        Returns:
            argparse.Namespace: Parsed arguments """
    parser = argparse.ArgumentParser(description='Indeed Job Scraper - Automated or Interactive Mode', 
                                     formatter_class=argparse.RawDescriptionHelpFormatter, 
                                     epilog='''
======================================================================================================
                            *** CLI Examples Refes ***
======================================================================================================

    python main.py                                                                                                          <-- INTERACTIVE MODE:
    python main.py --auto --query "DevOps Engineer"                                                                         <-- AUTO MODE - Basic:
    python main.py --auto --scraper seleniumbase --query "DevOps Engineer" --location "Remote" --remote                     <-- AUTO MODE - With SeleniumBase UC Mode (default, best for Cloudflare):
    python main.py --auto --scraper seleniumbase --query "DevOps Engineer" --location "Remote" --remote --days 7 --max 25
    python main.py --auto --scraper seleniumbase --query "SDET" --remote --screenshots --max 25                             <-- AUTO MODE - With screenshots (for cross-referencing with JSON):
    python main.py --auto --scraper camoufox --query "Software Engineer" --location "New York"                              <-- AUTO MODE - With Camoufox (experimental):
    python main.py --auto --scraper playwright --query "Software Engineer" --location "New York"                            <-- AUTO MODE - With Playwright fallback:
    
    python main.py --auto --scraper camoufox --query "Software Engineer" --location "Remote" \\                              <-- AUTO MODE - With proxy <-- Camoufox:
                   --proxy "http://user:pass@proxy.example.com:8080" --days 7 --max 25
    
    python main.py --auto --query "Software Engineer" --location "Remote" --remote \\                                         <-- AUTO MODE - With salary filters:
                   --min-salary 150000 --max-salary 200000 --days 14 --max 50 --headless
    
    python main.py --auto --queries "DevOps Engineer,SDET,Site Reliability Engineer" \\                                      <-- AUTO MODE - With multiple searches:
                   --location "Remote" --remote --days 7
    python main.py --auto --query "SDET" --proxy "http://user:pass@proxy.example.com:8080"                                  <-- AUTO MODE - With proxy (recommended for production):
    python main.py --auto --query "DevOps" --remote --headless                                                              <-- AUTO MODE - Headless (for servers/cron):
    python main.py --auto --query "Software Engineer" --min-salary 150000 --max-salary 200000                               <-- AUTO MODE - With salary filter:
    python main.py --auto --query "DevOps" --days 7                                                                         <-- AUTO MODE - Posted within last N days:
    python main.py --auto --queries "DevOps,SRE,Platform Engineer" --remote --days 7                                        <-- AUTO MODE - Multiple queries:
    python main.py --auto --query "DevOps" --max 50                                                                         <-- AUTO MODE - Max results:
    python main.py --auto --query "DevOps" --output-dir "./results"                                                         <-- AUTO MODE - Custom output directory:
    python main.py --auto --query "DevOps" --incognito                                                                      <-- AUTO MODE - Incognito (fresh session):
    python main.py --auto --query "DevOps" --window-size "1280x720"                                                         <-- AUTO MODE - Custom window size:
 ---------------------------------------------------------------------------------------------------------------------------
    python main.py --auto --scraper seleniumbase --query "DevOps Engineer" --location "Remote" --remote --days 7 \\ 
                   --max 50 --screenshots --output-dir "./artifacts/json"                                                   <-- AUTO MODE - Full example with screenshots:
   
    ----- if cronjob is needed ---- 
   CRON JOB (daily at 9am) - Example:  
   0 9 * * * cd /app && python main.py --auto --scraper camoufox --query "DevOps" --remote --days 1 --headless

======================================================================================================
    '''
    )
    
    # __ Auto mode flag:
    parser.add_argument(
        '--auto',
        action='store_true',
        help='Run in automated mode (no interactive prompts)'
    )
    
    # __ Scraper selection:
    parser.add_argument(
        '--scraper',
        type=str,
        choices=['seleniumbase', 'camoufox', 'playwright', 'selenium'],
        default='seleniumbase',
        help='Scraper backend to use (default: seleniumbase - best for Cloudflare bypass)'
    )
    
    # __ Authentication:
    parser.add_argument(
        '--email',
        type=str,
        help='Indeed account email for login'
    )
    parser.add_argument(
        '--password',
        type=str,
        help='Indeed account password for login'
    )
    
    # __ Search parameters:
    parser.add_argument(
        '--query',
        type=str,
        help='Job search query (e.g., "DevOps Engineer")'
    )
    parser.add_argument(
        '--queries',
        type=str,
        help='Multiple queries comma-separated (e.g., "DevOps,SDET,SRE")'
    )
    parser.add_argument(
        '--location',
        type=str,
        default='Remote',
        help='Job location (default: Remote)'
    )
    parser.add_argument(
        '--remote',
        action='store_true',
        help='Filter for remote jobs only'
    )
    
    # __ Salary filters:
    parser.add_argument(
        '--min-salary',
        type=int,
        dest='min_salary',
        help='Minimum salary (e.g., 150000)'
    )
    parser.add_argument(
        '--max-salary',
        type=int,
        dest='max_salary',
        help='Maximum salary (e.g., 200000)'
    )
    
    # __ Date filters:
    parser.add_argument(
        '--days',
        type=int,
        choices=[1, 3, 7, 14],
        help='Posted within last N days (1, 3, 7, or 14)'
    )
    
    # __ Results:
    parser.add_argument(
        '--max',
        type=int,
        default=25,
        help='Maximum results per search (default: 25)'
    )
    
    # __ Browser options:
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode (no GUI)'
    )
    
    parser.add_argument(
        '--incognito',
        action='store_true',
        help='Run browser in incognito/private mode (fresh session, no cookies)'
    )
    
    parser.add_argument(
        '--window-size',
        type=str,
        default='maximized',
        dest='window_size',
        help='Window size: "maximized" or "WIDTHxHEIGHT" (e.g., "1280x720", "1920x1080")'
    )
    
    # __ Proxy options | <-- primarily for Camoufox:
    parser.add_argument(
        '--proxy',
        type=str,
        help='Proxy server URL (e.g., "http://user:pass@proxy.example.com:8080")'
    )
    parser.add_argument(
        '--proxy-user',
        type=str,
        dest='proxy_user',
        help='Proxy username (if not included in proxy URL)'
    )
    parser.add_argument(
        '--proxy-pass',
        type=str,
        dest='proxy_pass',
        help='Proxy password (if not included in proxy URL)'
    )
    
    # __ Output:
    parser.add_argument(
        '--output-dir',
        type=str,
        default='artifacts/json',
        dest='output_dir',
        help='Output directory for JSON files (default: artifacts/json)'
    )
    
    # __ Screenshots:
    parser.add_argument(
        '--screenshots',
        action='store_true',
        help='Capture screenshots of each job card (saved to artifacts/screenshots/)'
    )
    parser.add_argument(
        '--screenshots-dir',
        type=str,
        default='artifacts/screenshots',
        dest='screenshots_dir',
        help='Directory for screenshots (default: artifacts/screenshots)'
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    pass