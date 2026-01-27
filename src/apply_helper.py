#!/usr/bin/env python
# # -*- coding: utf-8 -*-

import json
import webbrowser
import subprocess
from time import sleep
from pathlib import Path

def data_check():
    get_files = Path(__file__).parent.parent / "artifacts/json" 
    job_filter = []
    
    for json_file in get_files.glob("*.json"):
        with json_file.open("r") as f:
            infile = json.load(f)
            
            if isinstance(infile, dict) and "jobs" in infile:
                for job in infile["jobs"]:
                    salary = job.get("salary", "N/A")
                    
                    if salary not in ["Not Available", "N/A", "Pay information not provided", None, ""]:
                        job_filter.append({
                            "company": job.get("company", "N/A"),
                            "salary": salary,
                            "url": job.get("url", "N/A"),
                            "title": job.get("title", "N/A")})
    return job_filter

# def filter():
#     # url_tracker = 0
#     jobs = data_check()
#     for idx, job in enumerate(jobs, start=1):
#         print(f"\nJob: #{idx}:"
#                 f"\n\tTitle: {job['title']}"
#                 f"\n\tOrg Name: {job['company']}"
#                 f"\n\tPay Rate: {job['salary']}"
#                 f"\n\tApplication Url:{job['url']}"
#                 f"Total {len(jobs)} pay reate jobs found:")
#     print(f"\nTotal {len(jobs)} pay reate jobs found:")


def main(delay:int):
    url_tracker = 0
    firefox = "/Applications/Firefox.app/Contents/MacOS/firefox"
    jobs = data_check()
    for idx, job in enumerate(jobs, start=1):
        print(f"\nJob: #{idx}:"
                f"\n\tTitle: {job['title']}"
                f"\n\tOrg Name: {job['company']}"
                # f"\n\tPay Rate: {job['salary']}"
                f"\n\tApplication Url:{job['url']}"
                f"Total {len(jobs)} pay reate jobs found:")
    print(f"\nTotal {len(jobs)} pay reate jobs found:")

    for url_idx, job in enumerate(jobs, start=1):
        # webbrowser.open(url=job['url'])
        subprocess.run([firefox, "-new-tab", f"{job['url']}"])
        
        url_tracker += 1
        print(f"Opened ({url_tracker}/{len(jobs)}): {job.get('company')}")    
        if url_tracker % 3 == 0 and url_idx < len(jobs):
            print(f"\n... {delay} seconds delay: opened {url_tracker}")
            sleep(delay)
    
    print(f"\nDone! --> Went through {url_tracker} urls out of {len(jobs)}")

if __name__ == "__main__":
    # filter()
    main(delay=120)
    

# ____________________________________________________________________________________________________________________________________________________________________________________
# def data_check():
#     get_files = Path(__file__).parent.parent / "artifacts/json" 
#     for json_data in get_files.glob("*.json"):
#         with json_data.open("r") as read_from:
#             infile = json.load(read_from)
            
#             # if isinstance(infile, dict) and "jobs" in infile:
#             #     return [job.get("url", "no url found for this one") for job in infile["jobs"]]
            
#             if isinstance(infile, dict) and "jobs" in infile:
#                 # return [job.get("salary", "N/A") for job in infile["jobs"] if job.get("salary") != "Not Available"]
#                 return [job.get("salary", "N/A") for job in infile["jobs"] if job.get("salary") != "Not Available"  and job.get("salary") !="Pay information not provided"]

    
# if __name__ == "__main__":
#     data_check()
#     # [print(f"urls: {indx:>6}\t{jobs}") for indx, jobs in enumerate(data_check(), start=1)]
#     [print(f"pay rate: {indx:>6}\t{jobs}") for indx, jobs in enumerate(data_check(), start=1)]

# chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        # yandex ="/Applications/Yandex.app/Contents/MacOS/Yandex"
        # safari = "/Applications/Safari.app/Contents/MacOS/Safari"
        # firefox_path = "/Applications/Firefox.app/Contents/MacOS/firefox"
        # subprocess.run([default, "--start-fullscreen", f"{urls}"])
# "-new-window"
# "-new-tab"
# "--start-fullscreen"