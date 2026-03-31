#!/usr/bin/env python3
"""Album download - intercept network requests"""

import os, sys, time, json
from pathlib import Path

def download_album(url=None, output_dir=None, timeout=600):
    from playwright.sync_api import sync_playwright
    import requests
    
    url = url or "https://tidal.com/album/467306935"
    output_dir = output_dir or "C:/Users/jodya/downloads_album_test"
    os.makedirs(output_dir, exist_ok=True)
    
    print("Starting album download (intercept approach)...\n")
    
    # Track download URLs
    download_urls = []
    
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
        
        # Intercept responses to find download URLs
        def on_response(resp):
            resp_url = resp.url
            # Look for actual download responses (not blobs)
            if '/download' in resp_url and ('katze' in resp_url or 'hund' in url) and resp.status == 200:
                headers = resp.headers
                ct = headers.get('content-type', '')
                
                if 'audio' in ct or 'zip' in ct or 'octet-stream' in ct:
                    cd = headers.get('content-disposition', '')
                    filename = cd.split("filename*=")[-1].split("'")[-1] if cd else resp_url.split('/')[-1].split('?')[0]
                    filename = filename.replace('%20', ' ')
                    
                    print(f"[FOUND] {filename}")
                    print(f"  URL: {resp_url[:80]}...")
                    print(f"  Size: {int(headers.get('content-length', 0))/(1024*1024):.1f} MB")
                    
                    download_urls.append({'url': resp_url, 'filename': filename})
        
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
        
        # Find ZIP button and click
        for selector in ["text=Download ZIP as is", "text=Download ZIP"]:
            try:
                elem = page.locator(selector).first
                if elem.is_visible(timeout=2000):
                    print(f"Found: '{elem.inner_text().strip()}'")
                    elem.click(force=True)
                    break
            except: pass
        
        # Wait and intercept downloads
        print("\nWaiting for downloads...")
        for i in range(60):  # Wait up to 60 seconds
            time.sleep(1)
            if i % 10 == 0 and download_urls:
                print(f"  {i}s - Found {len(download_urls)} downloads so far...")
        
        browser.close()
        
        # Now download each captured URL
        print(f"\n--- Found {len(download_urls)} downloads ---")
        
        if download_urls:
            # Get cookies for requests
            cookies = {c['name']: c['value'] for c in context.cookies()}
            
            for i, dl in enumerate(download_urls, 1):
                print(f"\n[{i}/{len(download_urls)}] Downloading {dl['filename']}...")
                try:
                    resp = requests.get(dl['url'], cookies=cookies, timeout=300, stream=True)
                    if resp.status_code == 200:
                        filepath = Path(output_dir) / dl['filename']
                        size = 0
                        with open(filepath, 'wb') as f:
                            for chunk in resp.iter_content(8192):
                                f.write(chunk)
                                size += len(chunk)
                        print(f"  [OK] {size/(1024*1024):.1f} MB saved")
                    else:
                        print(f"  [FAILED] HTTP {resp.status_code}")
                except Exception as e:
                    print(f"  [ERROR] {e}")
        else:
            print("No downloads found!")

if __name__ == "__main__":
    download_album()
