#!/usr/bin/env python3
"""
Headless Cloudflare Cookie Extractor for lucida.to
Uses Playwright to extract cookie in the same browser context
"""

import os
import sys
import time
import argparse
from pathlib import Path

CONFIG_DIR = Path.home() / ".lucida-flow"
COOKIE_FILE = CONFIG_DIR / "cookies.txt"


def extract_cookie(headless=True, timeout=120, url="https://lucida.to"):
    """Extract Cloudflare clearance cookie using Playwright"""
    from playwright.sync_api import sync_playwright
    
    print("Starting headless browser...")
    
    context = None
    browser = None
    
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1920,1080",
                "--disable-blink-features=AutomationControlled",
                "--disable-extensions",
                "--disable-popup-blocking",
            ]
        )
        
        # Create context with realistic browser fingerprint
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        
        # Block automation-related JavaScript
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        """)
        
        page = context.new_page()
        
        print(f"Navigating to {url}...")
        page.goto(url, timeout=timeout * 1000)
        
        print("Waiting for Cloudflare challenge to complete...")
        
        # Wait for either Cloudflare to clear or page to load
        max_wait = timeout
        start_time = time.time()
        cookies_obtained = False
        
        while time.time() - start_time < max_wait:
            cookies = context.cookies()
            cf_cookie = next((c for c in cookies if c["name"] == "cf_clearance"), None)
            
            if cf_cookie:
                print("Cloudflare challenge completed!")
                return cf_cookie["value"]
            
            # Check if page loaded successfully (Cloudflare passed)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=1000)
            except:
                pass
            
            # Check for Cloudflare challenge elements
            try:
                page.query_selector("#cf-challenge-running")
                time.sleep(0.5)
            except:
                pass
            
            time.sleep(0.5)
        
        print("Timeout waiting for Cloudflare clearance")
        return None
        
    except Exception as e:
        print(f"Error: {e}")
        return None
    
    finally:
        if context:
            context.close()
        if browser:
            browser.close()
        try:
            playwright.stop()
        except:
            pass


def save_cookie(cookie, output_file=None):
    """Save cookie to config file"""
    if output_file is None:
        output_file = COOKIE_FILE
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        f.write(cookie)
    print(f"Cookie saved to {output_file}")
    return output_file


def main():
    parser = argparse.ArgumentParser(description="Headless Cloudflare cookie extractor for lucida.to")
    parser.add_argument("-o", "--output", default=None, help="Output file path")
    parser.add_argument("-t", "--timeout", type=int, default=120, help="Timeout in seconds")
    parser.add_argument("--visible", action="store_true", help="Show browser window")
    parser.add_argument("-u", "--url", default="https://lucida.to", help="URL to visit")
    
    args = parser.parse_args()
    
    output_file = Path(args.output) if args.output else COOKIE_FILE
    
    cookie = extract_cookie(
        headless=not args.visible,
        timeout=args.timeout,
        url=args.url
    )
    
    if cookie:
        save_cookie(cookie, output_file)
        return 0
    
    return 1


if __name__ == "__main__":
    sys.exit(main())
