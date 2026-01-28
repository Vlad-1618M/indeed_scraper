#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UI Module
Handles interactive user interface and job browsing
"""

import time


def display_jobs_interactive(jobs):
    """
    Interactive job browser with pagination.
    
    Args:
        jobs (list): List of job dictionaries
    """
    if not jobs:
        return
    
    page_size = 5
    current_page = 0
    total_pages = (len(jobs) + page_size - 1) // page_size
    
    while True:
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(jobs))
        
        print(f"\n{'='*80}")
        print(f"Jobs {start_idx + 1}-{end_idx} of {len(jobs)} (Page {current_page + 1}/{total_pages})")
        print(f"{'='*80}\n")
        
        for i, job in enumerate(jobs[start_idx:end_idx], start=start_idx + 1):
            print(f"{i}. {job['title']}")
            print(f"   Company: {job['company']}")
            print(f"   Location: {job['location']}")
            if job['salary'] != "N/A":
                print(f"   Salary: {job['salary']}")
            print(f"   URL: {job['url']}")
            if job['snippet'] != "N/A":
                print(f"   Snippet: {job['snippet'][:100]}...")
            print(f"   {'-'*76}")
        
        print(f"\nNavigation:")
        print(f"  [n] Next page" + (f" ({current_page + 2}/{total_pages})" if current_page < total_pages - 1 else " (end)"))
        print(f"  [p] Previous page" + (f" ({current_page}/{total_pages})" if current_page > 0 else " (start)"))
        print(f"  [#] View job details (enter job number)")
        print(f"  [q] Quit and close browser")
        
        choice = input("\nEnter choice: ").strip().lower()
        
        if choice == 'n' and current_page < total_pages - 1:
            current_page += 1
        elif choice == 'p' and current_page > 0:
            current_page -= 1
        elif choice == 'q':
            break
        elif choice.isdigit():
            job_num = int(choice) - 1
            if 0 <= job_num < len(jobs):
                display_job_details(jobs[job_num])
            else:
                print(f"Invalid job number. Enter 1-{len(jobs)}")
                time.sleep(1)
        else:
            print("Invalid choice")
            time.sleep(1)


def display_job_details(job):
    """
    Display detailed information for a single job.
    
    Args:
        job (dict): Job dictionary
    """
    print(f"\n{'='*80}")
    print(f"Job Details: {job['title']}")
    print(f"{'='*80}")
    print(f"Company: {job['company']}")
    print(f"Location: {job['location']}")
    print(f"Salary: {job['salary']}")
    print(f"Posted: {job['posted']}")
    print(f"\nDescription Snippet:")
    print(f"{job['snippet']}")
    print(f"\nApply at: {job['url']}")
    print(f"{'='*80}")
    input("\nPress Enter to continue...")


def prompt_interactive_config():
    """
    Prompt user for search configuration in interactive mode.
    
    Returns:
        dict: Configuration dictionary
    """
    print("\n" + "="*80)
    print("Search Configuration")
    print("="*80)
    
    config = {}
    
    config['query'] = input("\nJob title (e.g., 'SDET'): ") or "Software Engineer"
    config['location'] = input("Location (empty for Remote): ") or "Remote"
    config['remote_only'] = input("Remote only? (y/n): ").lower() == 'y'
    
    use_salary = input("Salary filter? (y/n): ").lower() == 'y'
    if use_salary:
        config['min_salary'] = int(input("Min salary: "))
        config['max_salary'] = int(input("Max salary: "))
    else:
        config['min_salary'] = None
        config['max_salary'] = None
    
    print("\nDate: 1=24h, 3=3days, 7=7days, 14=14days")
    date_input = input("Days (empty for all): ")
    config['date_posted'] = int(date_input) if date_input else None
    
    config['max_results'] = int(input("Max results (default 25): ") or "25")
    
    return config


def prompt_login():
    """
    Prompt user for login credentials.
    
    Returns:
        tuple: (email, password) or (None, None) if no login
    """
    use_login = input("\nLogin? (y/n): ").lower() == 'y'
    
    if use_login:
        email = input("Indeed email: ")
        password = input("Indeed password: ")
        return email, password
    
    return None, None


def print_header(title):
    """
    Print formatted header.
    
    Args:
        title (str): Header title
    """
    print("="*80)
    print(title)
    print("="*80)


def print_summary(total_queries, total_jobs, start_time, end_time):
    """
    Print scraping summary.
    
    Args:
        total_queries (int): Number of queries executed
        total_jobs (int): Total jobs scraped
        start_time (datetime): Start time
        end_time (datetime): End time
    """
    from modules.file_utils import format_timestamp
    
    print(f"\n{'='*80}")
    print("Summary")
    print(f"{'='*80}")
    print(f"Total queries: {total_queries}")
    print(f"Total jobs scraped: {total_jobs}")
    print(f"Started: {format_timestamp(start_time)}")
    print(f"Completed: {format_timestamp(end_time)}")
    duration = (end_time - start_time).total_seconds()
    print(f"Duration: {int(duration // 60)}m {int(duration % 60)}s")
