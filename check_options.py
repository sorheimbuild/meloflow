#!/usr/bin/env python3
"""Check all download options on album page"""

import os, sys, time
from pathlib import Path

def check_options():
    from playwright.sync_api import sync_playwright
    
    url = "https://tidal.com/album/467306935"
    
    print("Checking download options...\n")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage', '--no-sandbox']
        )
        
        context = browser.new_context(
            accept_downloads=True,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        )
        
        page = context.new_page()
        
        # Load page
        page.goto(f"https://lucida.to/?url={url}", wait_until='domcontentloaded', timeout=60000)
        time.sleep(5)
        
        print(f"Title: {page.title()}\n")
        
        # Find ALL buttons
        print("=== ALL BUTTONS ===")
        buttons = page.query_selector_all('button')
        for btn in buttons:
            try:
                txt = btn.inner_text().strip()
                vis = btn.is_visible()
                if txt:
                    print(f"  [{vis}] BUTTON: {txt}")
            except: pass
        
        # Find ALL links
        print("\n=== ALL LINKS ===")
        links = page.query_selector_all('a')
        for link in links:
            try:
                href = link.get_attribute('href') or ''
                txt = link.inner_text().strip()
                vis = link.is_visible()
                if href and vis:
                    print(f"  LINK: {txt[:50]} -> {href[:80]}")
            except: pass
        
        # Find download-related elements
        print("\n=== DOWNLOAD ELEMENTS ===")
        for selector in [
            "[class*='download']",
            "[data-download]",
            "[download]",
            "a[href*='download']",
            "button:has-text('download')",
            "button:has-text('Download')",
            "button:has-text('zip')",
            "button:has-text('ZIP')",
            "button:has-text('track')",
            "button:has-text('Track')",
        ]:
            try:
                elems = page.query_selector_all(selector)
                for elem in elems:
                    try:
                        txt = elem.inner_text().strip()
                        vis = elem.is_visible()
                        if txt and vis:
                            print(f"  [{selector}] {txt}")
                    except: pass
            except: pass
        
        browser.close()

if __name__ == "__main__":
    check_options()
