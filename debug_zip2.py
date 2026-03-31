#!/usr/bin/env python3
"""Debug album ZIP download - intercept actual download"""

import os, sys, time, json
from pathlib import Path

def debug_album_v2():
    from playwright.sync_api import sync_playwright
    
    url = "https://tidal.com/album/467306935"
    output_dir = "C:/Users/jodya/downloads_debug_zip"
    os.makedirs(output_dir, exist_ok=True)
    
    print("Starting debug v2...\n")
    
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
        
        # Track downloads
        download_info = {'url': None, 'data': []}
        
        def on_download(download):
            print(f"\n[DOWNLOAD] suggested: {download.suggested_filename}")
            print(f"URL: {download.url}")
            
            # Check if blob URL
            if download.url.startswith('blob:'):
                print("This is a BLOB URL - need to intercept the actual content!")
                download_info['url'] = download.url
        
        # Intercept route for the actual content
        download_url_found = {'url': None, 'content_length': None}
        
        def on_request(req):
            url = req.url
            # Look for the actual download endpoint
            if '/download' in url and ('katze' in url or 'hund' in url):
                print(f"\n[INTERCEPT] {req.method} {url[:100]}...")
        
        def on_response(resp):
            url = resp.url
            # Check for download responses
            if '/download' in url and ('katze' in url or 'hund' in url):
                headers = resp.headers
                ct = headers.get('content-type', '')
                cl = headers.get('content-length', '')
                cd = headers.get('content-disposition', '')
                print(f"\n[RESPONSE] {resp.status} - {url[:80]}...")
                print(f"  Content-Type: {ct}")
                print(f"  Content-Length: {cl}")
                print(f"  Content-Disposition: {cd[:80] if cd else 'None'}")
                download_url_found['url'] = url
                download_url_found['content_length'] = cl
                download_url_found['content_type'] = ct
        
        page.on('download', on_download)
        page.on('request', on_request)
        page.on('response', on_response)
        
        # Load page
        print(f"Loading: {url}")
        page.goto(f"https://lucida.to/?url={url}", wait_until='domcontentloaded', timeout=60000)
        time.sleep(5)
        
        print(f"\nTitle: {page.title()}\n")
        
        # Click main download button
        buttons = page.query_selector_all('button')
        for btn in buttons:
            try:
                txt = btn.inner_text().lower()
                if 'download' in txt and btn.is_visible():
                    print(f"Clicking: '{btn.inner_text().strip()}'")
                    btn.click(force=True)
                    break
            except: pass
        
        time.sleep(3)
        
        # Find ZIP button and click it
        for selector in ["text=Download ZIP as is", "text=Download ZIP", "button:has-text('ZIP')"]:
            try:
                elem = page.locator(selector).first
                if elem.is_visible(timeout=2000):
                    print(f"Found: '{elem.inner_text().strip()}'")
                    elem.click(force=True)
                    break
            except: pass
        
        print("\nWaiting for download response...")
        
        # Wait for the actual download response (not blob)
        waited = 0
        while download_url_found['url'] is None and waited < 60:
            time.sleep(1)
            waited += 1
            
            # Check page for any download links
            links = page.query_selector_all('a[href]')
            for link in links:
                href = link.get_attribute('href') or ''
                if 'katze' in href and 'download' in href:
                    print(f"\n[PAGE LINK] Found: {href[:100]}...")
            
            if waited % 10 == 0:
                print(f"Waiting... {waited}s")
        
        browser.close()
        
        print(f"\n--- Summary ---")
        print(f"Download URL found: {download_url_found['url'] is not None}")
        if download_url_found['url']:
            print(f"URL: {download_url_found['url'][:100]}...")
            print(f"Content-Length: {download_url_found['content_length']}")

if __name__ == "__main__":
    debug_album_v2()
