from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    page = context.new_page()
    
    page.goto("https://lucida.to/?url=https://tidal.com/track/75571617", wait_until="domcontentloaded", timeout=15000)
    time.sleep(3)
    
    print("Clicking download button via JS...")
    page.evaluate("document.querySelector('button.download-track').click()")
    time.sleep(3)
    
    page.screenshot(path="/downloads/after_js_click.png")
    
    content = page.content()
    
    links = page.query_selector_all("a")
    print("All links:")
    for link in links:
        try:
            href = link.get_attribute("href")
            if href and any(x in href for x in ['.flac', '.m4a', '.mp3', 'download', 'file', 'media']):
                print(f"  {href[:80]}")
        except:
            pass
    
    browser.close()
