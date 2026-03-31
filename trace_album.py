#!/usr/bin/env python3
"""Trace all requests to find download URLs"""

import os, sys, time
from pathlib import Path

def trace_album():
    from playwright.sync_api import sync_playwright
    
    url = "https://tidal.com/album/467306935"
    output_dir = "C:/Users/jodya/downloads_trace"
    os.makedirs(output_dir, exist_ok=True)
    
    print("Tracing all requests...\n")
    
    all_requests = []
    download_responses = []
    
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
        
        def on_request(req):
            req_url = req.url
            # Track all katze/hund requests
            if 'katze' in req_url or 'hund' in req_url:
                all_requests.append(req_url)
                if '/download' in req_url:
                    print(f"[REQ-DOWNLOAD] {req_url[:100]}...")
        
        def on_response(resp):
            resp_url = resp.url
            if 'katze' in resp_url or 'hund' in resp_url:
                if '/download' in resp_url:
                    try:
                        headers = resp.headers
                        ct = headers.get('content-type', '')
                        cl = headers.get('content-length', '')
                        print(f"[RES-DOWNLOAD] {resp.status} | {ct} | {int(cl or 0)/(1024*1024):.1f}MB | {resp_url[:80]}...")
                        download_responses.append({'url': resp_url, 'type': ct, 'size': cl})
                    except: pass
        
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
        
        # Find ZIP button
        for selector in ["text=Download ZIP as is", "text=Download ZIP"]:
            try:
                elem = page.locator(selector).first
                if elem.is_visible(timeout=2000):
                    print(f"Found: '{elem.inner_text().strip()}'")
                    elem.click(force=True)
                    break
            except: pass
        
        # Wait and trace
        print("\nWaiting 60s for downloads...")
        for i in range(60):
            time.sleep(1)
            
            # Check page content for any download links
            links = page.query_selector_all('a[href]')
            for link in links:
                href = link.get_attribute('href') or ''
                if 'katze' in href and '/download' in href:
                    text = link.inner_text().strip()
                    if text and text != href[:50]:
                        print(f"[PAGE-DOWNLOAD] {text}: {href[:60]}...")
                        if href not in [d['url'] for d in download_responses]:
                            download_responses.append({'url': href, 'type': 'from_page', 'size': 'unknown'})
            
            if i % 15 == 0:
                print(f"  {i}s elapsed...")
        
        browser.close()
        
        print(f"\n--- Summary ---")
        print(f"Download requests: {len([r for r in all_requests if '/download' in r])}")
        print(f"Download responses: {len(download_responses)}")
        
        if download_responses:
            print("\nDownload URLs found:")
            for d in download_responses:
                print(f"  {d}")

if __name__ == "__main__":
    trace_album()
