#!/usr/bin/env python3
"""Check dropdown after clicking"""

import os, sys, time
from pathlib import Path

def check_dropdown():
    from playwright.sync_api import sync_playwright
    
    url = "https://tidal.com/album/467306935"
    
    print("Checking dropdown options...\n")
    
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
        
        # Click "download full album"
        buttons = page.query_selector_all('button')
        for btn in buttons:
            try:
                txt = btn.inner_text().lower()
                if 'download' in txt and 'album' in txt and btn.is_visible():
                    print(f"Clicking: '{btn.inner_text().strip()}'")
                    btn.click(force=True)
                    break
            except: pass
        
        time.sleep(2)
        
        # Now check what's visible
        print("\n=== VISIBLE ELEMENTS AFTER CLICK ===\n")
        
        buttons = page.query_selector_all('button')
        for btn in buttons:
            try:
                txt = btn.inner_text().strip()
                vis = btn.is_visible()
                if vis and txt:
                    print(f"  [{vis}] BUTTON: {txt}")
            except: pass
        
        # Check for any modal/dropdown
        print("\n=== CHECKING FOR MODALS ===")
        modals = page.query_selector_all('[class*="modal"], [class*="dropdown"], [class*="menu"], [class*="popup"], [class*="dialog"]')
        for m in modals:
            try:
                vis = m.is_visible()
                if vis:
                    txt = m.inner_text()[:200]
                    print(f"  MODAL: {txt}")
            except: pass
        
        # Check text content
        print("\n=== PAGE TEXT CONTAINING DOWNLOAD ===")
        body = page.inner_text('body')
        for line in body.split('\n'):
            if 'download' in line.lower() or 'zip' in line.lower():
                print(f"  {line.strip()}")
        
        browser.close()

if __name__ == "__main__":
    check_dropdown()
