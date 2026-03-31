#!/usr/bin/env python3
"""Debug album ZIP download"""

import os, sys, time, json
from pathlib import Path

def debug_album():
    from playwright.sync_api import sync_playwright
    
    url = "https://tidal.com/album/467306935"  # Genshin OST
    output_dir = "C:/Users/jodya/downloads_debug_zip"
    os.makedirs(output_dir, exist_ok=True)
    
    print("Starting debug...\n")
    
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
        
        # Track ALL network
        requests = []
        responses = []
        
        def on_request(req):
            url = req.url
            if any(x in url.lower() for x in ['zip', 'download', 'katze', 'api', 'cdn', 'fetch']):
                requests.append({'url': url, 'method': req.method})
                print(f"[REQ] {req.method} {url[:100]}...")
        
        def on_response(resp):
            url = resp.url
            if any(x in url.lower() for x in ['zip', 'download', 'katze', 'api', 'cdn', 'fetch']):
                headers = resp.headers
                print(f"[RES] {resp.status} {url[:80]}...")
                if 'content-type' in headers: print(f"  Content-Type: {headers['content-type']}")
                if 'content-length' in headers: print(f"  Content-Length: {headers['content-length']}")
                if 'content-disposition' in headers: print(f"  Content-Disposition: {headers['content-disposition']}")
                responses.append({'url': url, 'status': resp.status, 'headers': headers})
        
        def on_download(download):
            print(f"\n[DOWNLOAD EVENT] {download.suggested_filename}")
            print(f"  URL: {download.url[:100]}...")
            
        page.on('request', on_request)
        page.on('response', on_response)
        page.on('download', on_download)
        
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
        
        # Find ZIP button
        zip_btn = None
        for selector in ["text=Download ZIP", "text=ZIP as is"]:
            try:
                elem = page.locator(selector).first
                if elem.is_visible(timeout=2000):
                    zip_btn = elem
                    print(f"Found ZIP option: '{elem.inner_text()}'")
                    break
            except: pass
        
        if zip_btn:
            print("\nClicking ZIP button...")
            
            # Wait for download with extended timeout
            print("Waiting for download (this may take a while for server processing)...\n")
            
            try:
                with page.expect_download(timeout=300000) as download_info:
                    zip_btn.click(force=True)
                
                download = download_info.value
                filename = download.suggested_filename
                filepath = Path(output_dir) / filename
                
                print(f"Download complete! Saving to {filepath}...")
                download.save_as(str(filepath))
                
                if filepath.exists():
                    size = filepath.stat().st_size
                    print(f"File size: {size} bytes")
                    
                    # Check content
                    with open(filepath, 'rb') as f:
                        header = f.read(100)
                        print(f"First bytes: {header[:20].hex()}")
                        
                        if size < 1000:
                            print("WARNING: File is very small (likely empty/incomplete)")
            
            except Exception as e:
                print(f"Error: {e}")
        
        # Save full log
        log = {'requests': requests, 'responses': responses}
        with open(Path(output_dir) / 'network_log.json', 'w') as f:
            json.dump(log, f, indent=2)
        print(f"\nNetwork log saved to {output_dir}/network_log.json")
        
        browser.close()

if __name__ == "__main__":
    debug_album()
