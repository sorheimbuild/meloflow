#!/usr/bin/env python3
"""Capture all track downloads from album"""

import os, sys, time
from pathlib import Path

def capture_all_tracks():
    from playwright.sync_api import sync_playwright
    import requests
    
    url = "https://tidal.com/album/467306935"
    output_dir = "C:/Users/jodya/downloads_album_full"
    os.makedirs(output_dir, exist_ok=True)
    
    print("Capturing ALL track downloads from album...\n")
    
    all_downloads = []
    
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
        
        # Track download responses
        def on_response(resp):
            resp_url = resp.url
            if '/download' in resp_url and ('katze' in resp_url or 'hund' in resp_url) and resp.status == 200:
                try:
                    headers = resp.headers
                    ct = headers.get('content-type', '')
                    cl = headers.get('content-length', '')
                    cd = headers.get('content-disposition', '')
                    
                    if 'audio' in ct or 'octet-stream' in ct:
                        # Extract filename
                        if 'filename' in cd:
                            import re
                            match = re.search(r"filename\*?=.*?'([^']+)'", cd)
                            if match:
                                filename = match.group(1).replace('%20', ' ')
                            else:
                                filename = cd.split('filename=')[-1].strip('"\'')
                        else:
                            filename = resp_url.split('/')[-1].split('?')[0] + '.flac'
                        
                        if filename not in [d['filename'] for d in all_downloads]:
                            print(f"[FOUND] {filename} ({int(cl or 0)/(1024*1024):.1f} MB)")
                            all_downloads.append({
                                'url': resp_url,
                                'filename': filename,
                                'size': int(cl or 0)
                            })
                except Exception as e:
                    print(f"[ERROR] {e}")
        
        page.on('response', on_response)
        
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
        
        # Click "Download ZIP as is"
        for selector in ["text=Download ZIP as is"]:
            try:
                elem = page.locator(selector).first
                if elem.is_visible(timeout=2000):
                    print(f"Clicking: '{elem.inner_text().strip()}'")
                    elem.click(force=True)
                    break
            except: pass
        
        # Wait and capture ALL downloads
        print("\nWaiting for downloads (this may take a while)...\n")
        
        last_count = 0
        no_new = 0
        cookies = None  # Get cookies before closing
        
        for i in range(300):  # 5 minutes max
            time.sleep(1)
            
            if i % 30 == 0:
                count = len(all_downloads)
                print(f"  {i}s - {count} tracks captured")
                
                # Get cookies periodically (before context closes)
                try:
                    cookies = {c['name']: c['value'] for c in context.cookies()}
                except:
                    pass
            
            # Check if new downloads stopped
            if len(all_downloads) == last_count:
                no_new += 1
            else:
                no_new = 0
                last_count = len(all_downloads)
            
            # If no new downloads for 30 seconds, likely done
            if no_new > 30 and len(all_downloads) > 0:
                print(f"\nNo new downloads for 30s - assuming done")
                break
        
        browser.close()
        
        # Get final cookies
        if not cookies:
            cookies = {c['name']: c['value'] for c in context.cookies()}
        
        # Summary
        print(f"\n{'='*50}")
        print(f"Captured {len(all_downloads)} tracks!")
        
        if all_downloads:
            # Try to get cookies from the captured request URLs (they have auth embedded)
            
            print(f"\nDownloading {len(all_downloads)} tracks...\n")
            
            for i, dl in enumerate(all_downloads, 1):
                print(f"[{i}/{len(all_downloads)}] {dl['filename']}...")
                try:
                    resp = requests.get(dl['url'], cookies=cookies, timeout=300, stream=True)
                    if resp.status_code == 200:
                        filepath = Path(output_dir) / dl['filename']
                        size = 0
                        with open(filepath, 'wb') as f:
                            for chunk in resp.iter_content(8192):
                                f.write(chunk)
                                size += len(chunk)
                        print(f"  [OK] {size/(1024*1024):.1f} MB")
                    else:
                        print(f"  [FAILED] HTTP {resp.status_code}")
                except Exception as e:
                    print(f"  [ERROR] {e}")
            
            print(f"\n{'='*50}")
            print(f"Download complete!")
            print(f"Saved to: {output_dir}")
        else:
            print("No downloads captured!")

if __name__ == "__main__":
    capture_all_tracks()
