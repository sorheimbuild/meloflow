#!/usr/bin/env python3
"""Debug album download - wait longer for all tracks"""

import os
import sys
import time
import re
from pathlib import Path


def debug_album_full(url, output_dir):
    from playwright.sync_api import sync_playwright
    
    os.makedirs(output_dir, exist_ok=True)
    
    print("Starting browser...")
    
    downloads = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        
        context = browser.new_context(
            accept_downloads=True,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
        )
        
        page = context.new_page()
        
        def handle_download(download):
            filename = download.suggested_filename
            print(f"[DOWNLOAD] {filename}")
            downloads.append({"filename": filename, "download": download})
        
        page.on('download', handle_download)
        
        lucida_url = f"https://lucida.to/?url={url}"
        print(f"Loading {lucida_url}...")
        
        page.goto(lucida_url, wait_until='domcontentloaded', timeout=60000)
        time.sleep(5)
        
        print(f"Title: {page.title()}")
        
        # Click main download button
        buttons = page.query_selector_all('button')
        for btn in buttons:
            try:
                txt = btn.inner_text().lower()
                if 'download' in txt and btn.is_visible():
                    print(f"Clicking: '{btn.inner_text()}'")
                    btn.click(force=True)
                    break
            except:
                pass
        
        time.sleep(2)
        
        # Look for ZIP download option
        zip_options = ["text=Download ZIP", "text=ZIP", "button:has-text('ZIP')"]
        
        zip_btn = None
        for selector in zip_options:
            try:
                elem = page.locator(selector).first
                if elem.is_visible(timeout=2000):
                    zip_btn = elem
                    print(f"Found ZIP option")
                    break
            except:
                pass
        
        if zip_btn:
            print("Clicking ZIP option...")
            zip_btn.click(force=True)
            
            # Wait for downloads
            print("Waiting for downloads...")
            waited = 0
            while waited < 300:  # 5 minutes max
                time.sleep(5)
                waited += 5
                
                count = len(downloads)
                if count > 0:
                    print(f"Downloads so far: {count}")
                
                # Check page state
                page_content = page.content().lower()
                if 'preparing' in page_content:
                    print(f"Still preparing... {waited}s")
                elif 'ready' in page_content and count == 0:
                    print(f"Ready but no downloads... {waited}s")
                
                if waited % 30 == 0:
                    print(f"Checking... {waited}s")
        
        print(f"\nTotal downloads: {len(downloads)}")
        
        # Save all downloads
        for d in downloads:
            filepath = Path(output_dir) / d["filename"]
            try:
                d["download"].save_as(str(filepath))
                if filepath.exists():
                    size = filepath.stat().st_size
                    print(f"[SAVED] {d['filename']} ({size:,} bytes)")
            except Exception as e:
                print(f"[ERROR] {d['filename']}: {e}")
        
        browser.close()
    
    return {"count": len(downloads), "files": [d["filename"] for d in downloads]}


if __name__ == "__main__":
    result = debug_album_full("https://tidal.com/album/467306935", "C:/Users/jodya/downloads_album_debug")
    print(f"\nResult: {result}")
