#!/usr/bin/env python3
"""
Downloader for lucida.to - Wait for download URL then download via Playwright
"""

import os
import sys
import time
import asyncio
import re
from pathlib import Path


def lucida_download_async(url, output_dir, timeout=300):
    """Download by intercepting the download URL"""
    from playwright.async_api import async_playwright
    
    os.makedirs(output_dir, exist_ok=True)
    
    async def _download():
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                ]
            )
            
            context = await browser.new_context(
                accept_downloads=True,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
            )
            
            page = await context.new_page()
            
            # Track download URL
            download_url = None
            download_filename = None
            
            # Intercept responses to find the actual download
            async def handle_response(response):
                nonlocal download_url, download_filename
                url = response.url
                
                # Check for download response
                if '/download' in url and 'katze.lucida.to' in url:
                    headers = response.headers
                    content_type = headers.get('content-type', '')
                    content_disp = headers.get('content-disposition', '')
                    
                    print(f"[FOUND] Download URL: {url[:80]}...")
                    print(f"  Content-Type: {content_type}")
                    print(f"  Content-Disposition: {content_disp}")
                    
                    download_url = url
                    
                    # Extract filename
                    if 'filename=' in content_disp:
                        match = re.search(r'filename\*?=["\']?([^"\';\n]+)', content_disp)
                        if match:
                            import urllib.parse
                            download_filename = urllib.parse.unquote(match.group(1))
                    else:
                        download_filename = url.split('/')[-1].split('?')[0] + '.flac'
            
            page.on('response', handle_response)
            
            # Build URL
            lucida_url = f"https://lucida.to/?url={url}"
            print(f"Loading {lucida_url}...")
            
            try:
                await page.goto(lucida_url, wait_until='domcontentloaded', timeout=60000)
            except Exception as e:
                print(f"Navigation error: {e}")
                return {"success": False, "error": str(e)}
            
            print("Waiting for Cloudflare challenge...")
            await asyncio.sleep(5)
            
            # Check page state
            title = await page.title()
            print(f"Page title: {title}")
            
            # Find download button
            buttons = await page.query_selector_all('button')
            print(f"Found {len(buttons)} buttons")
            
            download_btn = None
            for btn in buttons:
                try:
                    txt = (await btn.inner_text()).lower()
                    vis = await btn.is_visible()
                    if vis and 'download' in txt:
                        download_btn = btn
                        print(f"Found download button: {await btn.inner_text()}")
                        break
                except:
                    pass
            
            if download_btn:
                print("Clicking download button...")
                
                try:
                    await download_btn.click(force=True)
                except:
                    await download_btn.evaluate("el => el.click()")
                
                # Wait for download URL to be intercepted
                print("Waiting for download URL...")
                waited = 0
                while download_url is None and waited < timeout:
                    await asyncio.sleep(1)
                    waited += 1
                    
                    # Also check page content
                    if waited % 10 == 0:
                        print(f"  Waiting... {waited}s")
                        
                        # Check if there's a download link in the page
                        links = await page.query_selector_all('a[href]')
                        for link in links:
                            href = await link.get_attribute('href') or ''
                            if 'katze.lucida.to' in href and '/download' in href:
                                print(f"[PAGE] Found download link: {href[:80]}...")
                                download_url = href
                                break
                
                if download_url:
                    print(f"\nDownload URL found: {download_url[:80]}...")
                    
                    # Now trigger download via page
                    try:
                        async with page.expect_download(timeout=60000) as download_info:
                            await page.evaluate(f"window.location.href = '{download_url}'")
                        
                        download = await download_info.value
                        filename = download.suggested_filename
                        filepath = Path(output_dir) / filename
                        
                        print(f"Saving to {filepath}...")
                        await download.save_as(str(filepath))
                        
                        print(f"[SUCCESS] Downloaded: {filepath}")
                        await browser.close()
                        return {"success": True, "filepath": str(filepath)}
                    except Exception as e:
                        print(f"Download error: {e}")
                        return {"success": False, "error": str(e)}
            
            await browser.close()
            return {"success": False, "error": "Download URL not found"}
    
    return asyncio.run(_download())


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Download music from lucida.to")
    parser.add_argument("url", help="Track URL")
    parser.add_argument("-o", "--output", default="./downloads", help="Output directory")
    parser.add_argument("-t", "--timeout", type=int, default=300, help="Timeout")
    
    args = parser.parse_args()
    
    result = lucida_download_async(args.url, args.output, args.timeout)
    
    if result.get("success"):
        print(f"Success! File: {result['filepath']}")
        return 0
    print(f"Failed: {result.get('error', 'Unknown error')}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
