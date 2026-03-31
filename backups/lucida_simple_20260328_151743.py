#!/usr/bin/env python3
"""Lucida Flow - Music Downloader for Tidal, Qobuz, Spotify & more"""

import os, sys, time, re, json
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict

# Colors
C, G, Y, R, B, D, M, W, N = '\033[96m', '\033[92m', '\033[93m', '\033[91m', '\033[1m', '\033[2m', '\033[95m', '\033[97m', '\033[0m'

BANNER = f"""
{C}{B}
   __               _     __            ________             
  / /   __  _______(_)___/ /___ _      / ____/ /___ _      __
 / /   / / / / ___/ / __  / __ `/_____/ /_  / / __ \\ | /| / /
/ /___/ /_/ / /__/ / /_/ / /_/ /_____/ __/ / / /_/ / |/ |/ / 
/_____/\\__,_/\\___/_/\\__,_/\\__,_/     /_/   /_/\\____/|__/|__/ 
{N}{D}                        Music Downloader for Streaming Services{N}
"""

def p(msg, s="i"):
    icons = {"i": f"{C}*{N}", "s": f"{G}+{N}", "w": f"{Y}!{N}", "e": f"{R}x{N}", "d": f"{M}>{N}"}
    print(f"  {icons.get(s, icons['i'])} {msg}")

def pbox(info):
    if not info.title: return
    w = 50
    print(f"\n  {C}+{'-'*w}+{N}")
    if info.title: print(f"  {C}|{N}{B}{info.title[:w]:^{w}}{C}|{N}")
    if info.artist: print(f"  {C}|{N}{D}by {info.artist[:w-5]:.<{w-5}}{C}|{N}")
    if info.quality or info.format: print(f"  {C}|{N}{D}{(info.quality or info.format):^{w}}{C}|{N}")
    print(f"  {C}+{'-'*w}+{N}\n")

def pprogress(i=0, n=10):
    w = 30
    pct = min(100, (i/n)*100)
    bar = '='*int(w*pct/100) + '-'*(w-int(w*pct/100))
    print(f"\r  {C}[{bar}]{N} {pct:.0f}% ", end='', flush=True)

@dataclass
class TrackInfo:
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: str = ""
    quality: str = ""
    format: str = ""

@dataclass
class DownloadResult:
    success: bool = False
    filepath: str = ""
    size: int = 0
    track_info: Optional[TrackInfo] = None
    error: str = ""
    quality: str = ""
    format: str = ""
    duration: str = ""

def extract_url(url):
    m = re.search(r'tidal\.com/album/\d+/track/(\d+)', url)
    if m: return f"https://tidal.com/track/{m.group(1)}"
    m = re.search(r'tidal\.com/track/(\d+)', url)
    if m: return url
    return url

def get_track_info(page):
    info = TrackInfo()
    try:
        title = page.title()
        if '|' in title:
            parts = title.split('|')[0].strip().split(' by ')
            if len(parts) >= 2: info.title, info.artist = parts[0].strip(), parts[1].strip()
            else: info.title = parts[0].strip()
        pt = page.content()
        q = re.search(r'(FLAC|MP3|M4A|ALAC)[^<]*', pt, re.I)
        if q: info.quality = q.group(1).upper()
        info.format = "FLAC" if 'flac' in pt.lower() else "M4A/AAC" if 'm4a' in pt.lower() else "MP3" if 'mp3' in pt.lower() else "Audio"
    except: pass
    return info

def verify_file(fp):
    r = {"valid": False, "format": "", "duration": "", "bitrate": "", "sample_rate": "", "error": ""}
    try:
        import subprocess
        d = json.loads(subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', fp], capture_output=True, text=True).stdout)
        if 'format' in d and 'duration' in d['format']:
            t = float(d['format']['duration'])
            r['duration'] = f"{int(t//60)}:{int(t%60):02d}"
        for s in d.get('streams', []):
            if s.get('codec_type') == 'audio':
                r['format'] = s.get('codec_name', '').upper()
                if 'bit_rate' in s: r['bitrate'] = f"{int(s['bit_rate'])//1000}kbps"
                if 'sample_rate' in s: r['sample_rate'] = f"{int(s['sample_rate'])//1000}kHz"
                break
        r['valid'] = True
    except: pass
    return r

def load_history():
    f = Path.home()/".lucida-flow"/"history.json"
    if f.exists():
        try: return json.load(open(f))
        except: pass
    return []

def save_history(h):
    f = Path.home()/".lucida-flow"/"history.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    json.dump(h[-100:], open(f, 'w'), indent=2)

def add_history(r):
    h = load_history()
    h.append({"timestamp": datetime.now().isoformat(), "success": r.success, "filepath": r.filepath, "size": r.size, "format": r.format, "quality": r.quality, "duration": r.duration, "error": r.error})
    save_history(h)

def show_history(n=10):
    h = load_history()
    if not h:
        print(f"\n  {D}No download history yet.{N}\n")
        return
    print(f"\n  {B}{C}Recent Downloads:{N}\n")
    for e in reversed(h[-n:]):
        icon = f"{G}+{N}" if e['success'] else f"{R}x{N}"
        ts = datetime.fromisoformat(e['timestamp']).strftime("%b %d %H:%M")
        fn = Path(e['filepath']).name if e['filepath'] else "Unknown"
        sz = f" ({e['size']/(1024*1024):.1f} MB)" if e.get('size') else ""
        fmt = f" [{e.get('format', '?')}]" if e.get('format') else ""
        print(f"  {D}{ts}{N} {icon} {fn}{fmt}{sz}")
    print()

def wait_page(page, mx=60):
    for i in range(mx):
        time.sleep(1)
        pt, pc = page.title().lower(), page.content().lower()
        if 'cloudflare' in pt or 'checking your browser' in pt: continue
        if 'cf-challenge' in pc and 'checking your browser' in pc: continue
        if 'access denied' in pc or pt == 'access denied': return False
        if 'lucida' in pt and 'music at internet speed' not in pt: time.sleep(2); return True
        if 'music at internet speed' in pt: return False
    return False

def find_btn(page, mx=5):
    for _ in range(mx):
        try:
            for b in page.query_selector_all('button'):
                try:
                    t, v = b.inner_text().lower().strip(), b.is_visible()
                    if v and ('download' in t or 'download track' in t) and b.is_enabled(): return b
                except: pass
            time.sleep(2)
        except: time.sleep(2)
    return None

def lucida_download(url, out, quality="best", timeout=300, info=True, retries=3):
    from playwright.sync_api import sync_playwright
    os.makedirs(out, exist_ok=True)
    orig, url = url, extract_url(url)
    r = DownloadResult()
    print(f"\n  {C}->{N} URL: {D}{orig}{N}\n")
    
    for attempt in range(1, retries + 1):
        if retries > 1: p(f"Attempt {attempt}/{retries}...", "i")
        
        try:
            with sync_playwright() as pwr:
                br = pwr.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage', '--no-sandbox'])
                ctx = br.new_context(accept_downloads=True, user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', viewport={'width': 1920, 'height': 1080})
                pg = ctx.new_page()
                
                p(f"Loading...", "i")
                pg.goto(f"https://lucida.to/?url={url}", wait_until='domcontentloaded', timeout=60000)
                
                if not wait_page(pg):
                    pt = pg.title().lower()
                    if 'music at internet speed' in pt: r.error = "URL not supported"
                    else: r.error = "Cloudflare blocked"
                    p(f"{r.error}, retrying...", "w")
                    br.close()
                    time.sleep(5 * attempt)
                    continue
                
                time.sleep(2)
                p(f"Page loaded: {pg.title()[:50]}", "i")
                
                ti = get_track_info(pg)
                r.track_info = ti
                if info and ti.title: pbox(ti)
                
                p("Finding download button...", "i")
                btn = find_btn(pg)
                
                if not btn:
                    r.error = "Download button not found"
                    p("Button not found, retrying...", "w")
                    br.close()
                    time.sleep(3 * attempt)
                    continue
                
                is_album = 'album' in orig.lower() and 'track' not in orig.lower()
                
                if is_album:
                    p("Album detected - looking for ZIP...", "i")
                    btn.click(force=True)
                    time.sleep(2)
                    zbtn = None
                    for s in ["text=Download ZIP", "button:has-text('ZIP')"]:
                        try:
                            e = pg.locator(s).first
                            if e.is_visible(timeout=2000): zbtn = e; break
                        except: pass
                    
                    if zbtn:
                        p("Starting album download...", "d")
                        try:
                            with pg.expect_download(timeout=600000) as di:
                                zbtn.click(force=True)
                            dn, fn, fp = di.value, di.value.suggested_filename, Path(out)/di.value.suggested_filename
                            p(f"Downloading {fn}...", "d")
                            dn.save_as(str(fp))
                            if fp.exists():
                                r.success, r.filepath, r.size, r.format = True, str(fp), fp.stat().st_size, "ZIP"
                                p(f"Downloaded! ({r.size/(1024*1024):.1f} MB)", "s")
                        except Exception as e: r.error = str(e)
                    else: r.error = "ZIP option not found"
                else:
                    p("Starting download...", "d")
                    try:
                        with pg.expect_download(timeout=timeout*1000) as di:
                            btn.click(force=True)
                        dn, fn, fp = di.value, di.value.suggested_filename, Path(out)/di.value.suggested_filename
                        p(f"Downloading {fn}...", "d")
                        for i in range(10): time.sleep(0.5); pprogress(i)
                        dn.save_as(str(fp)); print()
                        if fp.exists():
                            r.success, r.filepath, r.size, r.format = True, str(fp), fp.stat().st_size, fp.suffix.upper().replace('.','')
                            p("Verifying file...", "i")
                            v = verify_file(str(fp))
                            if v['valid']:
                                r.quality, r.duration = v.get('bitrate', 'N/A'), v.get('duration', 'N/A')
                                p(f"+ {v['format']} | {v.get('sample_rate','N/A')} | {v.get('duration','N/A')}", "s")
                            p(f"Downloaded! ({r.size/(1024*1024):.1f} MB)", "s")
                    except Exception as e: r.error = str(e)
                
                br.close()
                
                if r.success: break
                else: p(f"Failed: {r.error}", "e"); time.sleep(3 * attempt)
        except Exception as e:
            r.error = str(e)
            p(f"Error: {e}", "e")
            if attempt < retries: time.sleep(3 * attempt)
    
    add_history(r)
    return r

def main():
    import argparse
    ap = argparse.ArgumentParser(description=f"{C}Lucida Flow{N} - Music Downloader", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=f"""
Examples:
  {D}lucida-flow download "https://tidal.com/track/12345"{N}
  {D}lucida-flow download "https://tidal.com/album/123" -o ~/Music{N}
  {D}lucida-flow history{N}
    """)
    ap.add_argument("url", nargs="?", help="Track or album URL")
    ap.add_argument("-o", "--output", default="./downloads", help="Output directory")
    ap.add_argument("-t", "--timeout", type=int, default=300, help="Timeout (sec)")
    ap.add_argument("-q", "--quality", default="best", choices=["best","flac","mp3","aac"], help="Quality")
    ap.add_argument("-r", "--retries", type=int, default=3, help="Max retries")
    ap.add_argument("--no-info", action="store_true", help="Skip track info")
    ap.add_argument("--history", action="store_true", help="Show history")
    ap.add_argument("--clear", action="store_true", help="Clear history")
    a = ap.parse_args()
    
    print(BANNER)
    
    if a.clear:
        f = Path.home()/".lucida-flow"/"history.json"
        if f.exists(): f.unlink()
        p("History cleared", "s")
        return 0
    
    if a.history:
        show_history()
        return 0
    
    if a.url:
        r = lucida_download(a.url, os.path.expanduser(a.output), a.quality, a.timeout, not a.no_info, a.retries)
        if r.success:
            print(f"\n  {G}{B}+ Success!{N}\n  {D}Saved to: {r.filepath}{N}\n")
            return 0
        print(f"\n  {R}{B}x Failed:{N} {r.error}\n")
        return 1
    
    print(f"\n  {D}Run with a URL or --help for options{N}\n")
    return 0

if __name__ == "__main__": sys.exit(main())
