#!/usr/bin/env python3
"""Parse album page for track URLs"""

import os, sys, time, re
from pathlib import Path

def parse_album():
    from playwright.sync_api import sync_playwright
    
    url = "https://tidal.com/album/467306935"
    
    print("Parsing album page for track URLs...\n")
    
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
        page.goto(f"https://lucida.to/?url={url}", wait_until='domcontentloaded', timeout=60000)
        time.sleep(5)
        
        print(f"Title: {page.title()}\n")
        
        # Look for track links
        print("=== TRACK LINKS ===")
        links = page.query_selector_all('a[href]')
        
        track_urls = []
        for link in links:
            try:
                href = link.get_attribute('href') or ''
                txt = link.inner_text().strip()
                
                # Look for tidal track URLs
                if 'tidal.com/track' in href:
                    # Extract track ID
                    match = re.search(r'tidal\.com/[a-z]+/(\d+)', href)
                    if match:
                        tid = match.group(1)
                        track_url = f"https://tidal.com/track/{tid}"
                        if track_url not in [t['url'] for t in track_urls]:
                            print(f"  Track: {txt[:40]} -> {track_url}")
                            track_urls.append({'title': txt, 'url': track_url})
            except: pass
        
        # Also check for data attributes
        print("\n=== TRACK DATA ===")
        scripts = page.query_selector_all('script')
        for script in scripts:
            try:
                txt = script.inner_text()
                # Look for track patterns
                matches = re.findall(r'"id":\s*(\d+)[^}]*"title":\s*"([^"]+)"', txt)
                for tid, title in matches:
                    track_url = f"https://tidal.com/track/{tid}"
                    if track_url not in [t['url'] for t in track_urls]:
                        print(f"  Script Track: {title[:40]} -> {track_url}")
                        track_urls.append({'title': title, 'url': track_url})
            except: pass
        
        print(f"\n--- Found {len(track_urls)} unique tracks ---")
        
        browser.close()
        
        return track_urls

if __name__ == "__main__":
    tracks = parse_album()
    print(f"\nTotal tracks: {len(tracks)}")
    if tracks:
        print(f"\nFirst 5 tracks:")
        for t in tracks[:5]:
            print(f"  {t}")
