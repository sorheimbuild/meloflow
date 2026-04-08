#!/usr/bin/env python3
"""
Downloader for lucida.to
Handles Cloudflare protection and downloads music
"""

import os
import sys
import time
import random
from pathlib import Path


def lucida_download(url, output_dir, timeout=120, max_retries=3):
    """Download from lucida.to, handling Cloudflare protection"""
    from playwright.sync_api import sync_playwright
    
    os.makedirs(output_dir, exist_ok=True)
    
    print("Starting browser...")
    
    for attempt in range(1, max_retries + 1):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-infobars',
                        '--disable-notifications',
                        '--disable-extensions',
                        '--disable-popup-blocking',
                        '--disable-sync',
                        '--mute-audio',
                        '--disable-web-security',
                    ]
                )
                
                context = browser.new_context(
                    accept_downloads=True,
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    locale='en-US',
                )
                
                # Inject stealth scripts
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.navigator.chrome = { runtime: {} };
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                    chrome.runtime && chrome.runtime.connect && chrome.runtime.connect();
                """)
                
                page = context.new_page()
                
                print(f"[Attempt {attempt}/{max_retries}] Loading {url}...")
                
                # Build the lucida URL
                if 'lucida.to' in url:
                    lucida_url = f"https://lucida.to/?url={url}"
                else:
                    lucida_url = f"https://lucida.to/?url={url}"
                
                try:
                    page.goto(lucida_url, wait_until='domcontentloaded', timeout=timeout * 1000)
                except Exception as e:
                    print(f"Navigation error: {e}")
                    continue
                
                # Wait for content
                time.sleep(3)
                
                title = page.title()
                print(f"Page title: {title}")
                
                # Check if page loaded
                if '404' in title or 'not found' in title.lower():
                    print("Track not found")
                    continue
                
                # Find download button
                download_btn = None
                buttons = page.query_selector_all('button')
                print(f"Found {len(buttons)} buttons")
                for btn in buttons:
                    try:
                        txt = btn.inner_text().lower()
                        vis = btn.is_visible()
                        if vis:
                            print(f"  Visible button: {btn.inner_text()}")
                        if 'download' in txt:
                            download_btn = btn
                            break
                    except:
                        pass
                
                if download_btn:
                    print("Found download button, clicking...")
                    try:
                        download_btn.click(force=True, timeout=5000)
                        print("Waiting for download link to appear...")
                        
                        # Wait for download processing
                        download_url = None
                        for i in range(120):
                            time.sleep(1)
                            
                            # Check page content for CDN links
                            page_content = page.content()
                            
                            # Find CDN links in page content
                            import re
                            cdn_matches = re.findall(r'https://lucida\.to/cdn-cgi/content\?id=[^\s"\']+', page_content)
                            if cdn_matches:
                                download_url = cdn_matches[0]
                                print(f"Found CDN download link!")
                                break
                            
                            # Also check links
                            links = page.query_selector_all('a[href]')
                            for link in links:
                                try:
                                    href = link.get_attribute('href')
                                    if href and 'cdn-cgi' in href:
                                        download_url = href
                                        break
                                except:
                                    pass
                            
                            if download_url:
                                break
                            
                            if i % 15 == 0 and i > 0:
                                print(f"Still waiting... {i}s")
                        
                        if download_url:
                            print(f"Downloading from: {download_url[:80]}...")
                            import requests
                            cookies = {c["name"]: c["value"] for c in context.cookies()}
                            response = requests.get(download_url, cookies=cookies, stream=True, timeout=300, allow_redirects=True)
                            
                            if response.status_code == 200:
                                content_disp = response.headers.get('content-disposition', '')
                                if 'filename=' in content_disp:
                                    filename = content_disp.split('filename=')[1].strip('"\'')
                                else:
                                    filename = f"album_{int(time.time())}.zip"
                                filepath = Path(output_dir) / filename
                                print(f"Downloading {filename} ({response.headers.get('content-length', 'unknown')} bytes)...")
                                downloaded = 0
                                with open(filepath, 'wb') as f:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        f.write(chunk)
                                        downloaded += len(chunk)
                                print(f"Downloaded {downloaded} bytes to {filepath}")
                                return {"success": True, "filepath": str(filepath)}
                            else:
                                print(f"Download failed: {response.status_code}")
                                
                    except Exception as e:
                        print(f"Error: {e}")
                        import traceback
                        traceback.print_exc()
                
                # Look for CDN links
                links = page.query_selector_all('a[href]')
                cdn_link = None
                for link in links:
                    try:
                        href = link.get_attribute('href')
                        if href and 'cdn-cgi' in href:
                            cdn_link = href
                            break
                    except:
                        pass
                
                if cdn_link:
                    print(f"Found CDN link: {cdn_link[:60]}...")
                    
                    # Download the file
                    import requests
                    cookies = {c["name"]: c["value"] for c in context.cookies()}
                    
                    response = requests.get(cdn_link, cookies=cookies, stream=True, timeout=60)
                    
                    if response.status_code == 200:
                        # Get filename
                        content_disp = response.headers.get('content-disposition', '')
                        if 'filename=' in content_disp:
                            filename = content_disp.split('filename=')[1].strip('"\'')
                        else:
                            filename = Path(cdn_link.split('?')[0].split('/')[-1]).name
                        
                        if not filename or '.' not in filename:
                            filename = f"track_{int(time.time())}.mp3"
                        
                        filepath = Path(output_dir) / filename
                        
                        print(f"Downloading to {filepath}...")
                        downloaded = 0
                        with open(filepath, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                                downloaded += len(chunk)
                        
                        print(f"Downloaded {downloaded} bytes")
                        return {"success": True, "filepath": str(filepath)}
                
                # Try clicking MORE button if visible
                more_btn = None
                for btn in buttons:
                    try:
                        txt = btn.inner_text().lower()
                        if 'more' in txt:
                            more_btn = btn
                            break
                    except:
                        pass
                
                if more_btn:
                    try:
                        more_btn.click(force=True, timeout=3000)
                        time.sleep(2)
                        
                        # Look for quality/download options
                        quality_btns = page.query_selector_all('button')
                        for qbtn in quality_btns:
                            try:
                                txt = qbtn.inner_text()
                                if any(x in txt.lower() for x in ['flac', 'hi-res', 'download', 'm4a']):
                                    print(f"Found quality option: {txt}")
                                    qbtn.click(force=True)
                                    time.sleep(2)
                            except:
                                pass
                    except:
                        pass
                
                # Save screenshot for debugging
                screenshot_path = Path(output_dir) / f"debug_{int(time.time())}.png"
                try:
                    page.screenshot(path=str(screenshot_path))
                    print(f"Debug screenshot: {screenshot_path}")
                except:
                    pass
                
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
    
    return {"success": False, "error": "Failed after all retries"}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Download music from lucida.to")
    parser.add_argument("url", help="Track URL (tidal, qobuz, etc.)")
    parser.add_argument("-o", "--output", default="/downloads", help="Output directory")
    parser.add_argument("-t", "--timeout", type=int, default=120, help="Timeout")
    
    args = parser.parse_args()
    
    result = lucida_download(args.url, args.output, args.timeout)
    
    if result.get("success"):
        print(f"Success! File: {result['filepath']}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
