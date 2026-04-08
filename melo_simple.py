#!/usr/bin/env python3
"""Meloflow - Music Downloader for Tidal, Qobuz, Spotify & more"""

import os, sys, time, re, json, unicodedata, threading
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict


def normalize_text(s):
    """Normalize text for filename matching - removes special chars and normalizes unicode"""
    s = s.lower()
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.replace(' ', '').replace('-', '').replace('_', '').replace("'", '')
    s = s.replace('&', '').replace('.', '').replace(',', '').replace('(', '').replace(')', '')
    s = s.replace('!', '').replace('?', '').replace('#', '').replace('@', '').replace('$', '')
    return s


STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.navigator.chrome = { runtime: {} };
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
chrome.runtime && chrome.runtime.connect && chrome.runtime.connect();
"""

def apply_stealth(context):
    """Inject stealth scripts to avoid detection"""
    context.add_init_script(STEALTH_SCRIPT)


SERVICES = {
    'tidal': 'Tidal',
    'qobuz': 'Qobuz', 
    'soundcloud': 'Soundcloud',
    'deezer': 'Deezer',
    'amazon': 'Amazon Music',
    'yandex': 'Yandex Music',
}

def search_lucida(query, service='tidal', country='US'):
    """Search lucida.to for tracks and albums"""
    from playwright.sync_api import sync_playwright
    
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True, args=BROWSER_ARGS)
    ctx = browser.new_context(
        accept_downloads=True,
        user_agent=USER_AGENT,
    )
    apply_stealth(ctx)
    page = ctx.new_page()
    
    page.goto('https://lucida.to', wait_until='domcontentloaded', timeout=30000)
    time.sleep(3)
    
    select = page.query_selector('select')
    if select:
        select.select_option(service)
        time.sleep(1)
    
    search_input = page.query_selector('input[placeholder*="Search"]')
    if not search_input:
        browser.close()
        pw.stop()
        return []
    
    search_input.fill(query)
    page.keyboard.press('Enter')
    time.sleep(8)
    
    results = []
    links = page.query_selector_all('a')
    seen_urls = set()
    
    for link in links:
        try:
            href = link.get_attribute('href')
            if not href or '/?' not in href:
                continue
            
            text = link.inner_text().strip()
            if not text or len(text) < 2:
                continue
            
            if href in seen_urls:
                continue
            seen_urls.add(href)
            
            full_url = 'https://lucida.to' + href
            
            is_album = '/album/' in href or '%2Falbum%2F' in href or '/browse/album/' in href
            is_track = '/track/' in href or '%2Ftrack%2F' in href
            
            if is_album or is_track:
                results.append({
                    'type': 'Album' if is_album else 'Track',
                    'title': text,
                    'url': full_url,
                    'href': href,
                })
        except:
            continue
    
    browser.close()
    pw.stop()
    
    return results

try:
    from tqdm import tqdm
    HAS_TQDM = True
except:
    HAS_TQDM = False

# Colors - Pink & White Theme
C = '\033[95m'   # Pink
G = '\033[92m'   # Green  
Y = '\033[93m'   # Yellow
R = '\033[91m'   # Red
B = '\033[1m'    # Bold
D = '\033[2m'    # Dim
M = '\033[35m'   # Magenta
W = '\033[97m'   # White
P = '\033[38;5;206m'  # Light pink
N = '\033[0m'    # Reset

BANNER = f"""
{B}{P}
   ╔══════════════════════════════════════════════╗
   ║  ♪  ♫  ♪  ♫  ♪  ♫  ♪  ♫  ♪  ♫  ♪  ♫  ♪  ║
   ║                                              ║
   ║   {W}  __               _     __            {P}  ║
   ║   {W} / /   __  _______(_)___/ /___ _      {P}  ║
   ║   {W}/ /   / / / / ___/ / __  / __ `/_____ {P}  ║
   ║   {W}/ /___/ /_/ / /__/ / /_/ / /_/ /_____ {P}  ║
   ║   {W}/_____/\\__,_/\\___/_/\\__,_/\\__,_/      {P}  ║
   ║                                              ║
   ║   {W}♥  Music Downloader  ♥{P}                 ║
   ║   {D}Tidal • Qobuz • Spotify • More{P}        ║
   ║  ♪  ♫  ♪  ♫  ♪  ♫  ♪  ♫  ♪  ♫  ♪  ♫  ♪  ║
    ╚══════════════════════════════════════════════╝
{N}"""

BROWSER_ARGS = ['--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage', '--no-sandbox']
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

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
    completed: int = 0
    failed: int = 0
    skipped: int = 0

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

def verify_file(fp, min_duration=5):
    """Verify file integrity using ffprobe. Returns dict with file info or error."""
    r = {"valid": False, "format": "", "duration": 0, "bitrate": "", "sample_rate": "", "error": ""}
    try:
        import subprocess
        result = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', fp], 
                            capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            r['error'] = 'ffprobe failed'
            return r
        
        d = json.loads(result.stdout)
        if 'format' in d and 'duration' in d['format']:
            r['duration'] = float(d['format']['duration'])
            if r['duration'] < min_duration:
                r['error'] = f'Too short ({r["duration"]:.1f}s)'
                return r
        
        for s in d.get('streams', []):
            if s.get('codec_type') == 'audio':
                r['format'] = s.get('codec_name', '').upper()
                if 'bit_rate' in s: r['bitrate'] = f"{int(s['bit_rate'])//1000}kbps"
                if 'sample_rate' in s: r['sample_rate'] = f"{int(s['sample_rate'])//1000}kHz"
                break
        
        r['valid'] = True
    except subprocess.TimeoutExpired:
        r['error'] = 'ffprobe timeout'
    except Exception as e:
        r['error'] = str(e)
    return r


def embed_track_metadata(filepath, track_num, total_tracks=None):
    """Embed track number into audio file metadata using ffmpeg."""
    import subprocess
    try:
        ext = Path(filepath).suffix.lower()
        temp_file = str(filepath) + '.tmp'
        
        metadata_args = ['ffmpeg', '-y', '-i', filepath]
        
        if total_tracks:
            metadata_args.extend(['-metadata', f'track={track_num}/{total_tracks}'])
        else:
            metadata_args.extend(['-metadata', f'track={track_num}'])
        
        metadata_args.extend(['-c', 'copy', temp_file])
        
        result = subprocess.run(metadata_args, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            Path(temp_file).replace(filepath)
            return True
        else:
            if Path(temp_file).exists():
                Path(temp_file).unlink()
            return False
    except Exception:
        return False


def embed_album_track_numbers(album_dir):
    """Embed track numbers into all audio files in album based on manifest."""
    manifest = get_album_manifest(album_dir)
    if not manifest:
        return 0
    
    total = len(manifest)
    count = 0
    
    for track_url, data in manifest.items():
        filepath = album_dir / data['filename']
        if filepath.exists():
            track_num = data.get('track', 0)
            if track_num > 0:
                if embed_track_metadata(str(filepath), track_num, total):
                    count += 1
    
    return count


def verify_audio_file(filepath, min_duration=10):
    """Quick verification that audio file is valid and not corrupted."""
    result = verify_file(str(filepath), min_duration)
    return result.get('valid', False) and result.get('duration', 0) >= min_duration

class DownloadProgress:
    def __init__(self, tracks):
        self.tracks = tracks
        self.status = ['pending'] * len(tracks)
        self.sizes = [0] * len(tracks)
        self.total_size = 0
        self.completed = 0
        self.failed = 0
        self.current = None
    
    def update(self, idx, status, size=0):
        self.status[idx] = status
        if size:
            self.sizes[idx] = size
        if status == 'done':
            self.completed += 1
            self.total_size += size
        elif status == 'failed':
            self.failed += 1
        elif status == 'skipped':
            self.completed += 1
        self.display()
    
    def display(self):
        total = len(self.tracks)
        done = self.completed + self.failed
        pct = done / total * 100 if total else 0
        
        bar_len = 30
        filled = int(bar_len * done / total) if total else 0
        bar = '=' * filled + '-' * (bar_len - filled)
        
        current = self.current if self.current else ""
        print(f"\r  {C}[{bar}]{N} {pct:.0f}% ({done}/{total}) | {Y}{current}{N}    ", end='', flush=True)

def download_with_progress(url, filepath, headers=None, timeout=300):
    """Download file with progress bar using requests"""
    import requests
    
    try:
        req_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Encoding': 'identity',
        }
        if headers:
            req_headers.update(headers)
        
        response = requests.get(url, headers=req_headers, stream=True, timeout=timeout)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        filename = filepath
        
        if HAS_TQDM:
            with open(filepath, 'wb') as f, tqdm(
                desc=Path(filepath).name[:30],
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                initial=0,
                mininterval=0.5,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{rate_fmt}]'
            ) as bar:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        bar.update(len(chunk))
        else:
            downloaded = 0
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        pct = (downloaded / total_size * 100) if total_size else 0
                        print(f"\r  Downloading... {pct:.0f}% ", end='', flush=True)
            print()
        
        return downloaded
    except Exception as e:
        if Path(filepath).exists():
            Path(filepath).unlink()
        raise e

def create_zip_from_folder(folder_path, zip_name=None, delete_originals=False):
    """Create ZIP archive from folder contents"""
    import zipfile
    folder = Path(folder_path)
    if not folder.exists():
        return None
    
    if zip_name is None:
        zip_name = f"{folder.name}.zip"
    zip_path = folder.parent / zip_name
    
    p(f"Creating ZIP archive...", "i")
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(folder.rglob('*')):
                if f.is_file():
                    arcname = f.relative_to(folder)
                    zf.write(f, arcname)
                    print(f"  {D}+ {arcname}{N}")
        
        zip_size = zip_path.stat().st_size
        p(f"ZIP created: {zip_path.name} ({zip_size/(1024*1024):.1f} MB)", "s")
        
        if delete_originals:
            import shutil
            for f in folder.rglob('*'):
                if f.is_file():
                    f.unlink()
            folder.rmdir()
            p(f"Original folder removed", "i")
        
        return str(zip_path)
    except Exception as e:
        p(f"ZIP creation failed: {e}", "e")
        return None

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

def parse_quality_options(page):
    """Parse page for available quality/format options"""
    options = []
    try:
        content = page.content()
        
        formats = re.findall(r'(FLAC|ALAC|MP3|M4A|AAC|OGG|WAV|AIFF)[^\d]*?(\d{4,5}|Hi-Res|\d+-bit)?', content, re.I)
        for fmt, qual in formats:
            if qual:
                options.append({'format': fmt.upper(), 'quality': qual})
            else:
                options.append({'format': fmt.upper(), 'quality': 'Standard'})
        
        sample_rates = re.findall(r'(\d{4,5})\s*(kHz|KHz|MHz)?', content)
        for rate, _ in sample_rates:
            if int(rate) > 1000:
                options.append({'format': 'FLAC', 'quality': f'{rate} kHz'})
        
        bit_depths = re.findall(r'(\d{2,3})-bit|bitdepth[^\d]*(\d+)', content, re.I)
        for bd1, bd2 in bit_depths:
            bd = bd1 or bd2
            options.append({'format': 'FLAC', 'quality': f'{bd}-bit'})
        
        services = re.findall(r'(Tidal|Qobuz|Deezer|Amazon|Spotify|SoundCloud|Apple\s*Music)', content, re.I)
        for svc in set(services):
            options.append({'service': svc.title()})
        
        return options
    except:
        return []

def check_alternate_services(page, current_service="Tidal"):
    """Check if better quality is available from alternate services"""
    options = []
    try:
        content = page.content()
        
        service_blocks = re.findall(r'(Tidal|Qobuz|Deezer|Amazon|Spotify)[^\n]*(?:FLAC|ALAC|MP3|M4A)[^\n]*', content, re.I | re.DOTALL)
        for block in service_blocks[:10]:
            svc = re.search(r'(Tidal|Qobuz|Deezer|Amazon|Spotify)', block, re.I)
            flac = re.search(r'FLAC\s*(\d{4})\s*kHz|(\d{2})-bit', block, re.I)
            if svc and flac:
                rate = flac.group(1) or ""
                bit = flac.group(2) or ""
                options.append({
                    'service': svc.group(1).title(),
                    'format': 'FLAC',
                    'sample_rate': f'{rate} kHz' if rate else 'N/A',
                    'bit_depth': f'{bit}-bit' if bit else 'N/A'
                })
        
        quality_map = {'24-bit': 24000, '16-bit': 16000, '192': 192000, '96': 96000, '48': 48000, '44': 44100}
        for opt in options:
            sr = opt.get('sample_rate', '')
            if 'kHz' in sr:
                try:
                    opt['score'] = quality_map.get(sr.split()[0], 44100)
                except:
                    opt['score'] = 44100
            else:
                opt['score'] = 44100
            if opt.get('bit_depth') == '24-bit':
                opt['score'] += 1000
        
        options.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        if options and options[0]['service'].lower() != current_service.lower():
            return options[:3]
    except:
        pass
    return []

def ask_format_choice(options, current_format):
    """Ask user to choose format from available options"""
    if not options:
        return None
    
    import sys
    if sys.platform == 'win32':
        import msvcrt
        def getch():
            return msvcrt.getch()
    else:
        import tty, termios
        def getch():
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                return sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
    
    print(f"\n  {Y}Available formats:{N}")
    for i, opt in enumerate(options[:5], 1):
        if 'format' in opt:
            print(f"    {G}{i}{N} - {opt['format']} {opt.get('quality', '')}")
        elif 'service' in opt:
            print(f"    {G}{i}{N} - {opt['service']} ({opt.get('format', '?')} {opt.get('sample_rate', '')})")
    
    print(f"    {G}0{N} - Keep current ({current_format})")
    print(f"\n  {D}Press number to select:{N} ", end='', flush=True)
    
    try:
        ch = getch()
        print(ch)
        if ch.isdigit():
            idx = int(ch)
            if idx == 0:
                return None
            if 1 <= idx <= len(options):
                return options[idx - 1]
    except:
        pass
    
    return None

def lucida_download(url, out, quality="best", timeout=300, info=True, retries=3, prefer_format=None, check_alternates=False):
    from playwright.sync_api import sync_playwright
    os.makedirs(out, exist_ok=True)
    orig, url = url, extract_url(url)
    r = DownloadResult()
    print(f"\n  {C}->{N} URL: {D}{orig}{N}\n")
    
    for attempt in range(1, retries + 1):
        if retries > 1: p(f"Attempt {attempt}/{retries}...", "i")
        
        try:
            with sync_playwright() as pwr:
                br = pwr.chromium.launch(headless=True, args=BROWSER_ARGS)
                ctx = br.new_context(accept_downloads=True, user_agent=USER_AGENT, viewport={'width': 1920, 'height': 1080})
                apply_stealth(ctx)
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
                
                if check_alternates:
                    p("Checking for better quality...", "i")
                    alts = check_alternate_services(pg)
                    if alts:
                        print(f"  {C}*{N} Found alternate services with quality info:")
                        for alt in alts:
                            print(f"    {G}+{N} {alt['service']}: {alt['format']} {alt.get('sample_rate','N/A')} {alt.get('bit_depth','')}")
                        choice = ask_format_choice(alts, ti.format or 'FLAC')
                        if choice:
                            p(f"Selected: {choice['service']}", "s")
                    else:
                        p("No better quality found from other services", "i")
                
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


def parse_album_for_tracks(page, num_discs=None):
    """Parse album page to extract track URLs and titles in album order"""
    import re
    tracks = []
    seen_ids = []
    
    content = page.content()
    
    track_urls = re.findall(r'tidal\.com/track/(\d+)', content)
    
    track_containers = re.findall(r'<li[^>]*data-type="track"[^>]*data-id="(\d+)"', content)
    if len(track_containers) < 10:
        track_containers = re.findall(r'data-id="(\d+)"[^>]*data-type="track"', content)
    if len(track_containers) < 10:
        track_containers = re.findall(r'"id"\s*:\s*"?(\d+)"?', content)
    
    for tid in track_containers:
        if tid not in seen_ids:
            seen_ids.append(tid)
    
    for tid in track_urls:
        if tid not in seen_ids:
            seen_ids.append(tid)
    
    titles = []
    title_matches = re.findall(r'"title"\s*:\s*"([^"]+)"', content)
    if len(title_matches) >= len(seen_ids):
        titles = title_matches[:len(seen_ids)]
    
    disc_numbers = []
    disc_matches = re.findall(r'"discNumber"\s*:\s*"?(\d+)"?', content)
    if len(disc_matches) >= len(seen_ids):
        disc_numbers = [int(d) for d in disc_matches[:len(seen_ids)]]
    
    track_list = re.findall(r'<li[^>]*>.*?tidal\.com/track/(\d+).*?</li>', content, re.DOTALL)
    if len(track_list) < 10:
        track_list = re.findall(r'<a[^>]+href=["\'][^"\']*tidal\.com/track/(\d+)[^"\']*["\'][^>]*>([^<]+)</a>', content, re.DOTALL)
    
    total_tracks = len(seen_ids)
    
    if num_discs is None:
        num_discs = 1
        if disc_numbers:
            num_discs = max(disc_numbers)
        elif total_tracks > 80:
            num_discs = 3
        elif total_tracks > 50:
            num_discs = 2
    
    tracks_per_disc = total_tracks // num_discs if num_discs > 1 else total_tracks
    
    i = 0
    for tid in seen_ids:
        title = titles[i] if i < len(titles) and titles[i] else None
        if not title:
            for t_match in track_list:
                if isinstance(t_match, tuple) and t_match[0] == tid:
                    title = re.sub(r'<[^>]+>', '', t_match[1]).strip()
                    break
                elif t_match == tid:
                    title = None
                    break
        if not title:
            title = f'Track {i+1}'
        
        disc = disc_numbers[i] if i < len(disc_numbers) else ((i // tracks_per_disc) + 1 if num_discs > 1 else 1)
        
        tracks.append({'url': f"https://tidal.com/track/{tid}", 'title': title[:100], 'disc': disc})
        i += 1
    
    return tracks

def get_existing_files(album_dir):
    """Get list of existing audio files in album directory"""
    existing = {}
    if album_dir.exists():
        for f in album_dir.glob('*.flac'):
            existing[f.stem.lower()] = f
        for f in album_dir.glob('*.m4a'):
            existing[f.stem.lower()] = f
        for f in album_dir.glob('*.mp3'):
            existing[f.stem.lower()] = f
        for f in album_dir.glob('*.FLAC'):
            existing[f.stem.lower()] = f
    return existing

def get_album_manifest(album_dir):
    """Get manifest of downloaded filenames for this album"""
    manifest_path = album_dir / '.lucida_manifest.json'
    if manifest_path.exists():
        try:
            data = json.load(open(manifest_path))
            if '_meta' in data:
                return data
            return data
        except:
            pass
    return {}

def save_album_manifest(album_dir, manifest, album_url=None, album_name=None):
    """Save manifest of downloaded tracks with metadata"""
    manifest_path = album_dir / '.lucida_manifest.json'
    
    if album_url or album_name:
        meta = {'_meta': {}}
        if album_url:
            meta['_meta']['url'] = album_url
        if album_name:
            meta['_meta']['name'] = album_name
        existing = {}
        if manifest_path.exists():
            try:
                existing = json.load(open(manifest_path))
            except:
                pass
        manifest = {**meta, **manifest}
    
    try:
        json.dump(manifest, open(manifest_path, 'w'), indent=2)
    except:
        pass

def file_matches_track(existing_files, track_title, track_url, track_index=None):
    """Check if a track matches any existing file"""
    track_id = track_url.split('/')[-1]
    
    clean_title = normalize_text(track_title)
    
    for filename in existing_files:
        clean_file = normalize_text(filename)
        
        if track_id in filename or track_id in filename.replace('-', ''):
            return True
        
        if clean_title in clean_file or clean_file in clean_title:
            return True
        
        words_in_title = clean_title.split()
        if len(words_in_title) >= 2:
            matches = sum(1 for w in words_in_title if len(w) > 3 and w in clean_file)
            if matches >= len(words_in_title) - 1:
                return True
    
    return False


def build_manifest_from_files(album_dir, tracks):
    """Build manifest by matching existing files to tracks by filename similarity"""
    manifest = {}
    files = list(album_dir.glob('*.flac')) + list(album_dir.glob('*.m4a')) + list(album_dir.glob('*.mp3'))
    used_files = set()
    
    for idx, track in enumerate(tracks):
        track_url = track['url']
        track_title = track.get('title', '')
        best_match = None
        best_score = 0
        
        for f in files:
            if f.name in used_files:
                continue
            
            score = calculate_filename_similarity(f.stem, track_title)
            if score > best_score and score > 0.3:
                best_score = score
                best_match = f
        
        if best_match:
            manifest[track_url] = {'filename': best_match.name, 'size': best_match.stat().st_size, 'track': idx + 1}
            used_files.add(best_match.name)
    
    return manifest


def calculate_filename_similarity(filename, track_title):
    """Calculate similarity score between filename and track title"""
    clean_file = normalize_text(filename)
    clean_title = normalize_text(track_title)
    
    if not clean_title or clean_title == 'track' or 'track' in clean_title.lower():
        return 0
    
    if clean_title in clean_file or clean_file in clean_title:
        return 1.0
    
    words_in_title = [w for w in clean_title.split() if len(w) > 3]
    if not words_in_title:
        return 0
    
    matches = sum(1 for w in words_in_title if w in clean_file)
    return matches / len(words_in_title)


def sort_album_tracks(album_dir, prefix_with_number=False):
    """Sort tracks in album folder based on manifest track numbers and discs."""
    manifest = get_album_manifest(album_dir)
    if not manifest:
        return 0, "No manifest found"
    
    tracks_with_order = []
    for track_url, data in manifest.items():
        track_num = data.get('track', 0)
        disc_num = data.get('disc', 1)
        filename = data.get('filename', '')
        if track_num > 0 and filename:
            filepath = album_dir / filename
            if filepath.exists():
                sort_key = (disc_num, track_num)
                tracks_with_order.append((sort_key, track_num, disc_num, filepath))
    
    tracks_with_order.sort(key=lambda x: x[0])
    
    renamed = 0
    for sort_key, track_num, disc_num, filepath in tracks_with_order:
        ext = filepath.suffix
        if prefix_with_number:
            if disc_num > 1:
                new_name = f"{disc_num}-{track_num:02d} - {filepath.name}"
            else:
                new_name = f"{track_num:02d} - {filepath.name}"
        else:
            new_name = filepath.name
        
        if filepath.name != new_name:
            new_path = filepath.parent / new_name
            if not new_path.exists():
                filepath.rename(new_path)
                renamed += 1
    
    return renamed, f"Sorted {renamed} tracks by album order"


def fix_album_track_order(album_dir, album_url, num_discs=None):
    """Re-fetch track order from lucida.to and update manifest."""
    from playwright.sync_api import sync_playwright
    
    manifest = get_album_manifest(album_dir)
    if not manifest:
        return 0, "No manifest found"
    
    existing_urls = set(manifest.keys())
    
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True, args=BROWSER_ARGS)
    context = browser.new_context(
        accept_downloads=True,
        user_agent=USER_AGENT,
    )
    apply_stealth(context)
    page = context.new_page()
    
    try:
        lucida_url = f"https://lucida.to/?url={album_url}"
        page.goto(lucida_url, wait_until='domcontentloaded', timeout=60000)
        time.sleep(5)
        
        tracks = parse_album_for_tracks(page, num_discs)
        
        updated = 0
        for idx, track in enumerate(tracks):
            track_url = track['url']
            if track_url in manifest:
                manifest[track_url]['track'] = idx + 1
                if 'disc' in track:
                    manifest[track_url]['disc'] = track['disc']
                updated += 1
        
        save_album_manifest(album_dir, manifest)
        
        browser.close()
        pw.stop()
        
        return updated, f"Fixed order for {updated} tracks"
        
    except Exception as e:
        browser.close()
        pw.stop()
        return 0, f"Error: {str(e)}"


def fetch_lyrics_from_api(artist, title):
    """Fetch lyrics from lyrics.ovh API (free, no API key)"""
    try:
        import requests
        url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json().get('lyrics', '')
    except Exception:
        pass
    return None


def fetch_album_lyrics(album_dir, artist_name=None):
    """Fetch lyrics for all tracks in album folder"""
    import requests
    
    manifest = get_album_manifest(album_dir)
    if not manifest:
        return 0
    
    if artist_name is None:
        artist_name = album_dir.name.split(' - ')[0] if ' - ' in album_dir.name else "Unknown Artist"
    
    count = 0
    for track_url, data in manifest.items():
        filename = data.get('filename', '')
        if not filename:
            continue
        
        filepath = album_dir / filename
        if not filepath.exists():
            continue
        
        track_name = filepath.stem
        if track_name.startswith(f"{artist_name} - "):
            track_name = track_name.replace(f"{artist_name} - ", "").strip()
        
        lyrics = fetch_lyrics_from_api(artist_name, track_name)
        if lyrics:
            save_lrc_file(filepath, lyrics, track_name)
            embed_lrc_lyrics(str(filepath), lyrics)
            count += 1
    
    return count


def embed_lrc_lyrics(filepath, lyrics_text):
    """Embed LRC lyrics into audio file metadata."""
    import subprocess
    try:
        temp_file = str(filepath) + '.tmp'
        
        lrc_escaped = lyrics_text.replace('\\', '\\\\').replace("'", "'\\''").replace('"', '\\"')
        
        cmd = [
            'ffmpeg', '-y', '-i', filepath,
            '-metadata', f'lyrics={lyrics_text}',
            '-c', 'copy', temp_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            Path(temp_file).replace(filepath)
            return True
        else:
            if Path(temp_file).exists():
                Path(temp_file).unlink()
            return False
    except Exception:
        return False


def save_lrc_file(filepath, lyrics_text, track_title=""):
    """Save lyrics as .lrc file."""
    lrc_path = filepath.with_suffix('.lrc')
    try:
        if track_title:
            lines = [f"[ti:{track_title}]", ""]
            for line in lyrics_text.split('\n'):
                if line.strip():
                    lines.append(f"[00:00.00]{line}")
            lyrics_text = '\n'.join(lines)
        
        lrc_path.write_text(lyrics_text, encoding='utf-8')
        return True
    except Exception:
        return False


def scan_album_folder(album_dir):
    """Scan folder and return detailed info about existing files"""
    files_info = {}
    if album_dir.exists():
        for f in album_dir.glob('*.flac'):
            files_info[f.stem.lower()] = {'path': f, 'size': f.stat().st_size}
        for f in album_dir.glob('*.m4a'):
            files_info[f.stem.lower()] = {'path': f, 'size': f.stat().st_size}
        for f in album_dir.glob('*.mp3'):
            files_info[f.stem.lower()] = {'path': f, 'size': f.stat().st_size}
        for f in album_dir.glob('*.FLAC'):
            files_info[f.stem.lower()] = {'path': f, 'size': f.stat().st_size}
    return files_info


def lucida_download_album(url, out, quality="best", timeout=300, parallel=2, retries=3, create_zip=False, check_alternates=False, num_discs=None):
    """Download all tracks from an album - optimized for light resource usage"""
    from playwright.sync_api import sync_playwright
    
    os.makedirs(out, exist_ok=True)
    
    print(f"\n  {C}->{N} Album URL: {D}{url}{N}\n")
    
    # Phase 1: Parse album (lightweight)
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=True,
        args=BROWSER_ARGS
    )
    context = browser.new_context(
        accept_downloads=True,
        user_agent=USER_AGENT,
    )
    apply_stealth(context)
    page = context.new_page()
    
    p("Loading album page...", "i")
    page.goto(f"https://lucida.to/?url={url}", wait_until='domcontentloaded', timeout=60000)
    
    if not wait_page(page):
        browser.close()
        pw.stop()
        return DownloadResult(success=False, error="Failed to load album page")
    
    time.sleep(2)
    
    album_name = page.title().split('|')[0].strip() if '|' in page.title() else "Album"
    print(f"  {C}*{N} Album: {B}{album_name}{N}")
    
    p("Scanning for tracks...", "i")
    tracks = parse_album_for_tracks(page, num_discs)
    
    if not tracks:
        browser.close()
        pw.stop()
        return DownloadResult(success=False, error="No tracks found on album page")
    
    disc_info = ""
    if num_discs and num_discs > 1:
        disc_info = f" ({num_discs} discs)"
    
    print(f"  {C}*{N} Found {len(tracks)} tracks on lucida.to{disc_info}")
    
    album_dir = Path(out) / album_name
    album_dir.mkdir(parents=True, exist_ok=True)
    print(f"  {C}*{N} Saving to: {album_dir}")
    
    page.close()
    
    existing = get_existing_files(album_dir)
    existing_info = scan_album_folder(album_dir)
    manifest = get_album_manifest(album_dir)
    
    has_real_titles = any(not t.get('title', '').startswith('Track ') for t in tracks)
    if not manifest and existing and has_real_titles:
        manifest = build_manifest_from_files(album_dir, tracks)
    
    if not manifest and existing:
        print(f"  {Y}!{N} No manifest found - will re-download all {len(existing)} existing tracks")
        print(f"  {D}  (lucidato doesn't expose track names until download){N}")
        print()
    
    to_download = []
    skipped_count = 0
    
    for i, track in enumerate(tracks):
        track_url = track['url']
        
        matched = False
        
        if track_url in manifest:
            matched = True
        
        if not matched and file_matches_track(existing, track.get('title', ''), track_url):
            matched = True
        
        if matched:
            skipped_count += 1
        else:
            to_download.append((i, track))
    
    if skipped_count > 0:
        print(f"  {D}⊘ Found {skipped_count} existing files - will skip{N}")
        
        for i, track in enumerate(tracks):
            track_url = track['url']
            if track_url in manifest:
                continue
            matched_file = None
            for fname, fpath in existing.items():
                if file_matches_track({fname: fpath}, track.get('title', ''), track_url):
                    matched_file = fpath
                    break
            if matched_file:
                manifest[track_url] = {'filename': matched_file.name, 'size': matched_file.stat().st_size, 'track': i + 1}
        
        save_album_manifest(album_dir, manifest)
        print()
    
    if not to_download:
        print(f"  {G}All {len(tracks)} tracks already downloaded!{N}")
        browser.close()
        pw.stop()
        return DownloadResult(success=True, filepath=str(album_dir), size=0)
        browser.close()
        pw.stop()
        return DownloadResult(success=True, filepath=str(album_dir), size=0)
    
    print(f"  {C}[Downloading {len(to_download)} tracks with {parallel} workers]{N}\n")
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    progress = DownloadProgress(tracks)
    
    for i, track in enumerate(tracks):
        track_url = track['url']
        if track_url in manifest:
            progress.update(i, 'skipped', manifest[track_url]['size'])
    total_size = 0
    completed = 0
    failed = 0
    
    work_items = [(i, track, album_dir, timeout, retries, existing) for i, track in to_download]
    
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(download_single_track_worker, item): item for item in work_items}
        
        for future in as_completed(futures):
            result = future.result()
            idx = result['index']
            
            if result['success']:
                progress.update(idx, 'done', result['size'])
                completed += 1
                total_size += result['size']
                fn = result['filename']
                track_url = result.get('url', '')
                if fn and track_url:
                    disc_num = track.get('disc', 1)
                    manifest[track_url] = {'filename': fn, 'size': result['size'], 'track': idx + 1, 'disc': disc_num}
                    save_album_manifest(album_dir, manifest)
                    actual_name = fn.replace('.flac', '').replace('.m4a', '').replace('.mp3', '')
                    progress.tracks[idx]['title'] = actual_name
                    print(f"  {G}✓{N} {actual_name} ({result['size']/(1024*1024):.1f} MB)")
            else:
                progress.update(idx, 'failed')
                failed += 1
                track = tracks[idx]
                print(f"  {R}✗{N} {track.get('title', f'Track {idx+1}')} - {result['error']}")
    
    downloaded = sum(1 for s in progress.status if s == 'done')
    skipped = sum(1 for s in progress.status if s == 'skipped')
    
    result_path = str(album_dir)
    zip_path = None
    
    if create_zip and (completed > 0 or skipped_count > 0):
        print(f"\n  {C}Creating ZIP archive...{N}")
        zip_path = create_zip_from_folder(album_dir, delete_originals=False)
        if zip_path:
            result_path = zip_path
    
    save_album_manifest(album_dir, manifest)
    
    print(f"\n  {C}========================================{N}")
    if completed: print(f"  {G}+ Downloaded: {completed}{N} ({total_size/(1024*1024):.1f} MB)")
    if skipped_count: print(f"  {D}⊘ Skipped: {skipped_count}{N} (already downloaded)")
    if failed: print(f"  {R}x Failed: {failed}{N}")
    print(f"  {D}Saved to: {result_path}{N}")
    print(f"  {C}========================================{N}\n")
    
    return DownloadResult(success=completed > 0, filepath=result_path, size=total_size, completed=completed, failed=failed, skipped=skipped_count)


def download_single_track_worker(args):
    """Worker function for parallel track download"""
    i, track, album_dir, timeout, retries, existing_files = args
    
    track_url = track['url']
    track_name = track.get('title', f'Track {i+1}')
    result = {'index': i, 'success': False, 'filename': None, 'size': 0, 'error': None, 'url': track_url}
    
    track_id = track_url.split('/')[-1]
    for fname, fpath in existing_files.items():
        if track_id in fname or fname.replace('-', '').replace(' ', '') in track_name.replace('-', '').replace(' ', '').lower():
            if fpath.exists():
                v = verify_file(str(fpath), min_duration=5)
                if v.get('valid') and v.get('duration', 0) >= 5:
                    result['success'] = True
                    result['filename'] = fpath.name
                    result['size'] = fpath.stat().st_size
                    return result
                else:
                    print(f"\n  {Y}!{N} Corrupted existing: {fname} - will re-download")
    
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=True,
        args=BROWSER_ARGS
    )
    context = browser.new_context(
        accept_downloads=True,
        user_agent=USER_AGENT,
    )
    apply_stealth(context)
    
    for attempt in range(1, retries + 1):
        try:
            page = context.new_page()
            lucida_url = f"https://lucida.to/?url={track_url}"
            page.goto(lucida_url, wait_until='domcontentloaded', timeout=60000)
            
            if not wait_page(page):
                page.close()
                if attempt < retries:
                    time.sleep(2)
                    continue
                break
            
            time.sleep(1)
            
            btn = find_btn(page)
            if not btn:
                page.close()
                if attempt < retries:
                    time.sleep(1)
                    continue
                break
            
            with page.expect_download(timeout=timeout*1000) as di:
                btn.click(force=True)
            
            fn = di.value.suggested_filename or f"track_{i+1}.flac"
            fp = album_dir / fn
            
            counter = 1
            base_name = fn.rsplit('.', 1)
            while fp.exists():
                fn = f"{base_name[0]} ({counter}).{base_name[1]}"
                fp = album_dir / fn
                counter += 1
            
            di.value.save_as(str(fp))
            page.close()
            
            if fp.exists():
                size = fp.stat().st_size
                if size > 1000:
                    v = verify_file(str(fp), min_duration=5)
                    if v.get('valid') and v.get('duration', 0) >= 5:
                        result['success'] = True
                        result['filename'] = fn
                        result['size'] = size
                        result['duration'] = v.get('duration', 0)
                        browser.close()
                        pw.stop()
                        return result
                    else:
                        err = v.get('error', 'Invalid audio')
                        print(f"\n  {Y}!{N} Corrupted: {fn} ({err}) - re-downloading...")
                        fp.unlink()
                else:
                    fp.unlink()
            
            if attempt < retries:
                continue
            break
            
        except Exception as e:
            try:
                page.close()
            except: pass
            if attempt < retries:
                time.sleep(2)
    
    browser.close()
    pw.stop()
    result['error'] = f"Failed after {retries} attempts"
    return result


def download_single_track(url, out, quality, timeout, retries, context):
    """Download a single track using existing context"""
    from playwright.sync_api import sync_playwright
    
    result = DownloadResult()
    
    for attempt in range(1, retries + 1):
        try:
            page = context.new_page()
            
            lucida_url = f"https://lucida.to/?url={url}"
            page.goto(lucida_url, wait_until='domcontentloaded', timeout=60000)
            
            if not wait_page(page):
                page.close()
                time.sleep(3 * attempt)
                continue
            
            time.sleep(2)
            
            btn = find_btn(page)
            if not btn:
                page.close()
                continue
            
            with page.expect_download(timeout=timeout*1000) as di:
                btn.click(force=True)
            
            dn, fn, fp = di.value, di.value.suggested_filename, Path(out)/di.value.suggested_filename
            dn.save_as(str(fp))
            
            if fp.exists():
                result.success, result.filepath, result.size = True, str(fp), fp.stat().st_size
                page.close()
                return result
            
            page.close()
            
        except Exception as e:
            result.error = str(e)
            time.sleep(2 * attempt)
    
    return result
