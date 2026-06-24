#!/usr/bin/env bash

# Clean up application temporary caches and code signing clones see bug in --> (https://github.com/teamcapybara/capybara/issues/2795) 
# Usage: sudo cleanup_temp_cache [OPTIONS]
# Compatible with Bash Version 3.2+

set -euo pipefail

# ____ colored output formatting:
gray='\033[1;90m'
white='\033[1;97m'
yellow='\033[1;93m'
green='\033[1;92m'
orange='\033[1;91m'
magenta='\033[1;95m'
cyan='\033[1;96m'
red="\033[1;31m"
off="\033[0m"

# ____ visual separation decorators:
decorator_init() { echo -e "${gray}$(printf '_%.0s' $(seq 1 111))${off}"; }
decorator_done() { echo -e "\n${white}$(printf '=%.0s' $(seq 1 111))${off}\n"; }

# ____ default log directory:
log_dir="${HOME}/Library/Logs/cleanup_cache"
log_file=""

# ____  show help:
show_help() {
    decorator_done
    printf "${cyan} $(basename $0)${off} - Clean up macOS application temporary caches\n\n"
    printf "${yellow}USAGE:${off}\n"
    printf "    ${green}sudo${orange} $(basename $0) ${yellow}[${magenta}OPTIONS${yellow}]${off}\n\n"
    printf "${yellow}OPTIONS:${off}\n"
    printf "    ${magenta}-h${off}, --help              Show this help message\n"
    printf "    ${magenta}-d${off}, --dry-run           Show what would be deleted without actually deleting\n"
    printf "    ${magenta}-y${off}, --yes               Skip confirmation prompts (use with care)\n"
    printf "    ${magenta}-a${off}, --app APP           Target specific app (chrome, docker, all)\n"
    printf "    ${magenta}-l${off}, --log-dir PATH      Directory to save logs (default: ~/Library/Logs/cleanup_cache)\n\n"
    printf "${yellow}DESCRIPTION:${off}\n"
    printf "    Scans /private/var/folders for large temporary caches created by applications,\n"
    printf "    Particularly ${red}Chrome code signing clones ${yellow}(${gray}default${yellow})${off}:\n"
    printf "    Creates a log of all cleanup actions:\n\n"
    printf "${yellow}EXAMPLES:${off}\n"
    printf "    ${green}sudo ${orange}$(basename $0)${off}                              # Interactive cleanup\n"
    printf "    ${green}sudo ${orange}$(basename $0)${magenta} -d${off}                           # Dry run\n"
    printf "    ${green}sudo ${orange}$(basename $0)${magenta} -a${off} chrome                    # Target only Chrome\n"
    printf "    ${green}sudo ${orange}$(basename $0)${magenta} -l${off} ~/logs --dry-run          # Custom log location + dry run\n\n"
    printf "${yellow}NOTE:${off}\n"
    printf "    This script requires ${green}sudo${off} privileges to access /private/var/folders\n"
    printf "    Logs are saved to: ${log_dir}\n"
    decorator_done
    exit 0
}

# ____ logger:
log_action() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$log_file"
}

# ____ sudo user root check:
check_sudo() {
    if [ $EUID -ne 0 ]; then
        decorator_init
        echo -e "${red}ERROR: This script must be run with sudo privileges${off}"
        echo -e "${yellow}Usage: sudo cleanup_temp_cache [OPTIONS]${off}"
        decorator_done
        exit 1
    fi
}

# ____ chrome process check:
check_chrome_running() {
    if pgrep -x "Google Chrome" > /dev/null 2>&1; then
        echo -e "${red}ERROR: Google Chrome is currently running${off}"
        echo -e "${yellow}Please close Chrome completely before running cleanup${off}"
        return 1
    fi
    return 0
}

# ____ log file init:
init_log() {
    local dir="$1"
    
    # ____ create log dir if its not threre:
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir" 2>/dev/null || {
            echo -e "${red}ERROR: Cannot create log directory: $dir${off}"
            echo -e "${yellow}Falling back to /tmp${off}"
            dir="/tmp"
        }
    fi
    
    log_file="$dir/cleanup_$(date +%Y%m%d_%H%M%S).log"
    
    # ____ test write permissions:
    if ! touch "$log_file" 2>/dev/null; then
        echo -e "${red}ERROR: Cannot write to log directory: $dir${off}"
        log_file="/tmp/cleanup_$(date +%Y%m%d_%H%M%S).log"
        echo -e "${yellow}Using fallback log: $log_file${off}"
    fi
}

# ____ find primary user temp folder:
find_user_temp_folder() {
    local base_path="/private/var/folders"
    local largest_folder
    largest_folder=$(sudo du -sh "$base_path"/*/* 2>/dev/null | sort -hr | head -n 1 | awk '{print $2}')
    echo "$largest_folder"
}

# ____ validate chrome path safety:
validate_chrome_path() {
    local path="$1"
    
    # ____ check step #1: Path must not be empty:
    if [ -z "$path" ]; then
        echo -e "${red}ERROR: Chrome path is empty${off}" >&2
        return 1
    fi
    
    # ____ check step #2: Path must exist and be a directory:
    if [ ! -d "$path" ]; then
        echo -e "${red}ERROR: Chrome path does not exist or is not a directory${off}" >&2
        return 1
    fi
    
    # ____ check step #3: Path must not be a symlink:
    if [ -L "$path" ]; then
        echo -e "${red}ERROR: Chrome path is a symlink (security risk), refusing to delete${off}" >&2
        log_action "ERROR: Chrome path is a symlink: $path"
        return 1
    fi
    
    # ____ check step #4: Path must match expected pattern:
    if [[ ! "$path" =~ ^/private/var/folders/.*/X/com\.google\.Chrome\.code_sign_clone$ ]]; then
        echo -e "${red}ERROR: Path doesn't match expected Chrome cache pattern${off}" >&2
        echo -e "${gray}Expected: /private/var/folders/.../X/com.google.Chrome.code_sign_clone${off}" >&2
        echo -e "${gray}Got: $path${off}" >&2
        log_action "ERROR: Invalid path pattern: $path"
        return 1
    fi
    
    # ____ check step #5: Path must be within /private/var/folders/:
    if [[ ! "$path" =~ ^/private/var/folders/ ]]; then
        echo -e "${red}ERROR: Path is not within /private/var/folders/${off}" >&2
        log_action "ERROR: Path outside safe directory: $path"
        return 1
    fi
    
    # ____ check step #6: Path must end with exact name (no wildcards):
    if [[ ! "$path" =~ com\.google\.Chrome\.code_sign_clone$ ]]; then
        echo -e "${red}ERROR: Path doesn't end with expected Chrome cache name${off}" >&2
        return 1
    fi
    
    return 0
}

# ____ check for Chrome code signing clones:
# ____ Redirect display output to stderr (>&2) so it's shown but not captured:
scan_chrome_clones() {
    local temp_folder="$1"
    local chrome_path="$temp_folder/X/com.google.Chrome.code_sign_clone"
    
    if [ -d "$chrome_path" ]; then
        local total_size
        local clone_count
        total_size=$(sudo du -sh "$chrome_path" 2>/dev/null | awk '{print $1}')
        clone_count=$(sudo ls -1 "$chrome_path" 2>/dev/null | wc -l | tr -d ' ')
        
        # ____ output to stderr so it displays but isn't captured by command substitution:
        echo -e "${cyan}Chrome Code Signing Clones:${off}" >&2
        echo -e "  Path: ${gray}$chrome_path${off}" >&2
        echo -e "  Total Size: ${yellow}$total_size${off}" >&2
        echo -e "  Clone Count: ${yellow}$clone_count${off}" >&2
        
        # ____ show top 5 largest clones | head -n 5 can be changed to any num value if needed:
        echo -e "\n${magenta}Top 5 largest clones:${off}" >&2
        sudo du -sh "$chrome_path"/* 2>/dev/null | sort -hr | head -n 5 | while read size path; do
            echo -e "  ${gray}$size${off}  $(basename "$path")" >&2
        done
        
        # ____ return the actual path to stdout:
        echo "$chrome_path"
    else
        echo ""
    fi
}

# ____ check for any other known cached data:
scan_other_caches() {
    local temp_folder="$1"
    local x_path="$temp_folder/X"
    
    if [ ! -d "$x_path" ]; then
        return
    fi
    
    echo -e "\n${cyan}Other Application Caches:${off}"
    
    # ____ known cache folders to check:
    local apps="com.docker com.jetbrains com.microsoft com.apple org.chromium"
    local found_any=false
    
    for app_pattern in $apps; do
        local found_paths
        found_paths=$(sudo find "$x_path" -maxdepth 1 -name "${app_pattern}*" 2>/dev/null)
        
        if [ -n "$found_paths" ]; then
            found_any=true
            echo "$found_paths" | while IFS= read -r path; do
                local size
                local name
                size=$(sudo du -sh "$path" 2>/dev/null | awk '{print $1}')
                name=$(basename "$path")
                echo -e "  ${yellow}$size${off}  ${gray}$name${off}"
            done
        fi
    done
    
    if [ "$found_any" = "false" ]; then
        echo -e "  ${green}No other large caches found${off}"
    fi
}

# ____ confirm Chrome cleanup:
confirm_chrome_cleanup() {
    local chrome_path="$1"
    local auto_yes="${2:-false}"
    local confirm1
    local confirm2
    
    decorator_init
    echo -e "${orange}WARNING: You are about to delete Chrome temporary caches${off}"
    echo -e "${gray}Path: $chrome_path${off}"
    echo -e "\n${yellow}This will NOT delete:${off}"
    echo -e "  - Bookmarks"
    echo -e "  - Passwords"
    echo -e "  - History"
    echo -e "  - Extensions"
    echo -e "  - User profiles"
    echo -e "\n${yellow}Chrome must be closed before cleanup.${off}"
    decorator_done

    if [ "$auto_yes" = "true" ]; then
        log_action "Auto-confirmed Chrome cache deletion (--yes)"
        return 0
    fi
    
    # ____ first confirmation:
    read -p "$(echo -e ${cyan}Are you sure you want to proceed? ${white}[yes/no]:${off} )" confirm1
    if [ "$confirm1" != "yes" ]; then
        echo -e "${red}Cleanup cancelled${off}"
        return 1
    fi
    
    # ____ second confirmation | just to be sure:
    read -p "$(echo -e ${orange}Please confirm again. Delete Chrome cache? ${white}[yes/no]:${off} )" confirm2
    if [ "$confirm2" != "yes" ]; then
        echo -e "${red}Cleanup cancelled${off}"
        return 1
    fi
    
    return 0
}

# ___ is Chrome running:
cleanup_chrome() {
    local chrome_path="$1"
    local dry_run="$2"
    local size_before

    # ____ SAFETY CHECK: Validate path before any deletion attempt:
    if ! validate_chrome_path "$chrome_path"; then
        echo -e "${red}✗ Path validation failed, refusing to delete${off}"
        log_action "FAILED: Path validation failed: $chrome_path"
        return 1
    fi

    if [ "$dry_run" = "true" ]; then
        echo -e "\n${yellow}[DRY RUN] Would delete:${off} $chrome_path"
        log_action "[DRY RUN] Would delete Chrome cache: $chrome_path"
        return 0
    fi

    # ____ check if Chrome is running:
    if ! check_chrome_running; then
        log_action "FAILED: Chrome is running, cannot cleanup"
        return 1
    fi

    echo -e "\n${green}Cleaning up Chrome cache...${off}"

    size_before=$(sudo du -sh "$chrome_path" 2>/dev/null | awk '{print $1}')

    # ____ final safety check before deletion:
    echo -e "${yellow}Final safety check...${off}"
    echo -e "  Path: ${gray}$chrome_path${off}"
    echo -e "  Size: ${yellow}$size_before${off}"
    
    if sudo rm -rf "$chrome_path" 2>/dev/null; then
        # ____ verify deletion succeeded:
        if [ ! -d "$chrome_path" ]; then
            echo -e "${green}✓ Successfully deleted Chrome cache${off}"
            echo -e "  Freed: ${yellow}$size_before${off}"
            log_action "SUCCESS: Deleted Chrome cache ($size_before): $chrome_path"
            return 0
        else
            echo -e "${red}✗ Deletion command succeeded but directory still exists${off}"
            log_action "FAILED: Directory still exists after deletion: $chrome_path"
            return 1
        fi
    else
        echo -e "${red}✗ Failed to delete Chrome cache${off}"
        log_action "FAILED: Could not delete Chrome cache: $chrome_path"
        return 1
    fi
}


main() {
    local dry_run=false
    local auto_yes=false
    local target_app="chrome"
    local temp_folder
    local chrome_path
    local cleanup_performed=false

    # ____ parse arguments:
    while [ $# -gt 0 ]; do
        case $1 in
            -h|--help)
                show_help
                ;;
            -d|--dry-run)
                dry_run=true
                shift
                ;;
            -y|--yes)
                auto_yes=true
                shift
                ;;
              -a|--app)
                if [ -z "${2:-}" ]; then
                    echo -e "${red}Error: -a/--app requires an argument${off}"
                    echo "Valid options: chrome, all"
                    exit 1
                fi
                target_app="$2"
                shift 2
                ;;
            -l|--log-dir)
                log_dir="$2"
                shift 2
                ;;
            *)
                echo -e "${red}Unknown option: $1${off}"
                echo "Use -h or --help for usage information"
                exit 1
                ;;
        esac
    done

    # ____ check sudo:
    check_sudo

    # ____ logging init:
    init_log "$log_dir"

    decorator_init
    echo -e "${cyan}macOS Temporary Cache Cleanup Tool ${magenta}[EXTRA SAFE MODE]${off}"
    echo -e "${gray}Log file: $log_file${off}"
    if [ "$dry_run" = "true" ]; then
        echo -e "${yellow}Mode: DRY RUN (no files will be deleted)${off}"
    fi
    decorator_done

    log_action "Cleanup script started (dry_run=$dry_run, target=$target_app)"

    # ____ get user temp folder:
    echo -e "${cyan}Scanning temporary folders...${off}\n"
    temp_folder=$(find_user_temp_folder)

    if [ -z "$temp_folder" ]; then
        echo -e "${red}Could not locate user temp folder${off}"
        log_action "ERROR: Could not locate user temp folder"
        exit 1
    fi

    echo -e "${gray}Using temp folder: $temp_folder${off}\n"
    log_action "Temp folder: $temp_folder"

    # ____ chrome:
    if [ "$target_app" = "all" ] || [ "$target_app" = "chrome" ]; then
        chrome_path=$(scan_chrome_clones "$temp_folder")

        if [ -n "$chrome_path" ]; then
            echo ""
            if [ "$dry_run" = "true" ]; then
                cleanup_chrome "$chrome_path" "$dry_run"
            else
                if confirm_chrome_cleanup "$chrome_path" "$auto_yes"; then
                    if cleanup_chrome "$chrome_path" "$dry_run"; then
                        cleanup_performed=true
                    fi
                fi
            fi
        else
            echo -e "${green}No Chrome cache found${off}"
            log_action "No Chrome cache found"
        fi
    fi

    # ____ other apps:
    if [ "$target_app" = "all" ]; then
        scan_other_caches "$temp_folder"
    fi

    # ____ show disk space after cleanup:
    decorator_init
    echo -e "${cyan}Current Disk Usage:${off}"
    df -h / | grep -E "Filesystem|disk"
    decorator_done

    decorator_init
    if [ "$cleanup_performed" = "true" ]; then
        echo -e "${green}Cleanup complete${off}"
        log_action "Cleanup script completed successfully"
    else
        echo -e "${yellow}No cleanup performed${off}"
        log_action "Cleanup script completed - no changes made"
    fi
    echo -e "${gray}Log saved to: $log_file${off}"
    decorator_done
}

main "$@"
