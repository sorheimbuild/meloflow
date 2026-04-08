#!/usr/bin/env python3
"""Meloflow CLI"""

import os, sys

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import click
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from melo_simple import lucida_download, lucida_download_album, load_history, BANNER, C, G, Y, R, B, D, N, parse_quality_options, check_alternate_services, verify_audio_file, get_existing_files

DEFAULT_OUTPUT = os.getenv("DOWNLOAD_DIR", "./downloads")


def p(msg, color=""):
    if color: print(f"{color}{msg}{N}")
    else: print(msg)


@click.group(invoke_without_command=True)
@click.version_option(version="2.0.0", prog_name="meloflow")
def cli():
    """Meloflow - Download music from Tidal, Qobuz & more"""
    print(BANNER)
    print(f"  {D}Download albums & tracks from streaming services{N}\n")
    print(f"  {C}Quick Start:{N}\n")
    print(f"    {G}meloflow download{N} <url>                    Download an album")
    print(f"    {G}meloflow download{N} <url> {D}-o ~/Music{R}        Download to folder")
    print(f"    {G}meloflow search{N} <query>                      Search for music")
    print(f"    {G}meloflow sort{N} <folder> {D}--prefix{R}            Sort tracks with numbers\n")
    print(f"  {C}For all commands:{N} {D}meloflow --help{N}\n")


@cli.command()
@click.argument("url", required=False)
@click.option("-o", "--output", default=DEFAULT_OUTPUT, help="Where to save downloads (default: ./downloads)")
@click.option("-t", "--timeout", default=300, help="Max time per track in seconds")
@click.option("-q", "--quality", default="best", type=click.Choice(["best","flac","mp3","aac"]), help="Audio quality (best=highest available)")
@click.option("-f", "--file", "file_path", help="File with multiple URLs to download")
@click.option("-p", "--parallel", default=4, type=int, help="How many tracks to download at once (default: 4)")
@click.option("-r", "--retries", default=3, type=int, help="How many times to retry failed tracks")
@click.option("--no-info", is_flag=True, help="Skip track info display")
@click.option("--zip", "create_zip", is_flag=True, help="Compress album into ZIP file after download")
@click.option("--check-alternates", is_flag=True, help="Check other services for better quality")
@click.option("--format", "prefer_format", default=None, type=click.Choice(["flac","m4a","mp3","alac"]), help="Force specific audio format")
@click.option("--verify", is_flag=True, help="Check files for corruption, re-download bad ones")
@click.option("--no-auto-retry", is_flag=True, help="Don't keep retrying - only try once")
@click.option("--pause", default=10, type=int, help="Seconds to wait between auto-retries")
@click.option("--embed-metadata", is_flag=True, help="Add track numbers to audio file tags")
@click.option("--sort", is_flag=True, help="Sort tracks in album order after download")
@click.option("--lyrics", is_flag=True, help="Try to download lyrics (if available)")
@click.option("--fix-order", is_flag=True, help="Fix track order if it was wrong before")
@click.option("--discs", default=None, type=int, help="Number of CDs/discs in album (for multi-disc albums)")
def download(url, output, timeout, quality, file_path, parallel, retries, no_info, create_zip, check_alternates, prefer_format, verify, no_auto_retry, pause, embed_metadata, sort, lyrics, fix_order, discs):
    """Download tracks or albums from Tidal, Qobuz & more"""
    if not url and not file_path:
        print(f"\n  {R}Error: URL or --file required{N}\n")
        return
    
    # Detect single album URL
    if url and '/album/' in url and not url.endswith('/track/'):
        out = os.path.expanduser(output)
        os.makedirs(out, exist_ok=True)
        
        if verify:
            print(f"\n  {C}--- Verifying Album Files ---{N}")
            from melo_simple import scan_album_folder, get_album_manifest
            import json
            
            # Try to find album folder
            existing_dirs = [d for d in Path(out).iterdir() if d.is_dir() and not d.name.startswith('.')]
            if not existing_dirs:
                print(f"  {Y}No album folders found in {out}{N}")
                return
            
            print(f"  {D}Found {len(existing_dirs)} folders:{N}")
            for d in existing_dirs:
                print(f"    - {d.name}")
            
            album_dir = existing_dirs[0]
            print(f"\n  Verifying: {album_dir.name}")
            
            files = scan_album_folder(album_dir)
            valid, invalid, missing = 0, 0, 0
            
            for name, info in files.items():
                fp = info['path']
                if verify_audio_file(fp):
                    valid += 1
                    print(f"  {G}✓{N} {name[:50]}")
                else:
                    invalid += 1
                    print(f"  {R}✗{N} {name[:50]} - CORRUPTED")
            
            print(f"\n  {C}Results:{N}")
            print(f"    {G}Valid: {valid}{N}")
            print(f"    {R}Corrupted: {invalid}{N}")
            
            if invalid > 0:
                print(f"\n  {Y}Run without --verify to re-download corrupted files{N}")
            return
        
        print(f"\n  {C}--- Album Download Mode ---{N}")
        out = os.path.expanduser(output)
        os.makedirs(out, exist_ok=True)
        
        if not create_zip:
            try:
                resp = input(f"\n  {Y}Create ZIP archive after download? [y/N]: {N}").strip().lower()
                create_zip = resp in ['y', 'yes']
            except:
                create_zip = False
        
        print(f"  {C}|{N} Output:   {out}")
        print(f"  {C}|{N} Parallel: {parallel}")
        print(f"  {C}|{N} Retries:  {retries}")
        print(f"  {C}|{N} ZIP:      {'Yes' if create_zip else 'No'}")
        print(f"  {C}|{N} Check:    {'Alternate services' if check_alternates else 'No'}")
        print(f"  {C}|{N} AutoRetry: {'No' if no_auto_retry else 'Yes (' + str(pause) + 's pause)'}\n")
        
        if fix_order:
            from melo_simple import fix_album_track_order
            album_path = Path(out)
            existing_dirs = [d for d in album_path.iterdir() if d.is_dir() and not d.name.startswith('.')]
            if existing_dirs:
                print(f"\n  {C}Fixing track order...{N}")
                count, msg = fix_album_track_order(existing_dirs[0], url, discs)
                print(f"  {G}{msg}{N}\n")
        
        attempt = 0
        while True:
            attempt += 1
            if not no_auto_retry and attempt > 1:
                print(f"\n  {C}--- Auto-Retry Attempt {attempt} (pausing {pause}s) ---{N}")
                import time
                time.sleep(pause)
            
            r = lucida_download_album(url, out, quality, timeout, parallel, retries, create_zip, check_alternates, discs)
            
            if no_auto_retry:
                break
            
            if r.success and r.failed == 0:
                print(f"\n  {G}All tracks downloaded successfully!{N}")
                break
            
            failed_count = getattr(r, 'failed', 0)
            if failed_count is None:
                failed_count = 0
            print(f"\n  {Y}{failed_count} tracks failed, will retry...{N}")
        
        if embed_metadata and r.success:
            from melo_simple import embed_album_track_numbers
            album_path = Path(r.filepath) if r.filepath else Path(out)
            print(f"\n  {C}Embedding track numbers in metadata...{N}")
            count = embed_album_track_numbers(album_path)
            print(f"  {G}Updated {count} files with track numbers{N}")
        
        if lyrics and r.success:
            from melo_simple import fetch_album_lyrics
            album_path = Path(r.filepath) if r.filepath else Path(out)
            print(f"\n  {C}Fetching lyrics from lyrics.ovh...{N}")
            count = fetch_album_lyrics(album_path)
            print(f"  {G}Got lyrics for {count} tracks{N}")
        
        return
    
    urls = []
    if url: urls.append(url)
    if file_path:
        print(f"  {C}*{N} Reading URLs from: {file_path}")
        with open(file_path, 'r') as f:
            urls.extend([l.strip() for l in f if l.strip() and not l.startswith('#')])
        print(f"  {C}*{N} Found {len(urls)} URLs\n")
    
    if not urls: return
    
    out = os.path.expanduser(output)
    os.makedirs(out, exist_ok=True)
    
    print(f"\n  {C}--- Settings ---{N}")
    print(f"  {C}|{N} Output:   {out}")
    print(f"  {C}|{N} URLs:     {len(urls)}")
    print(f"  {C}|{N} Parallel: {parallel}")
    print(f"  {C}|{N} Retries:  {retries}")
    print(f"  {C}|{N} Format:   {prefer_format or quality}")
    print(f"  {C}|{N} Check:    {'Alternate services' if check_alternates else 'No'}\n")
    
    completed, failed, total_size = 0, 0, 0
    
    if parallel == 1:
        for i, u in enumerate(urls, 1):
            if len(urls) > 1: print(f"\n  {B}[{i}/{len(urls)}] Downloading:{N}")
            r = lucida_download(u, out, quality, timeout, not no_info, retries, prefer_format=prefer_format, check_alternates=check_alternates)
            
            if r.success:
                completed += 1
                total_size += r.size
                fn = Path(r.filepath).name
                print(f"\n  {G}+{N} {fn}")
                print(f"  {D}  {r.size/(1024*1024):.1f} MB | {r.format} | {r.duration}{N}")
            else:
                failed += 1
                print(f"\n  {R}x{N} Failed")
                print(f"  {D}  URL: {u}{N}")
                print(f"  {R}  Error: {r.error}{N}")
    else:
        with ThreadPoolExecutor(max_workers=parallel) as ex:
            futures = {ex.submit(lucida_download, u, out, quality, timeout, False, retries, prefer_format=prefer_format, check_alternates=check_alternates): u for u in urls}
            for i, f in enumerate(as_completed(futures), 1):
                u = futures[f]
                try:
                    r = f.result()
                    if r.success:
                        completed += 1
                        total_size += r.size
                        print(f"  {G}+{N} [{i}/{len(urls)}] {Path(r.filepath).name}")
                    else:
                        failed += 1
                        print(f"  {R}x{N} [{i}/{len(urls)}] {u}")
                except Exception as e:
                    failed += 1
                    print(f"  {R}x{N} [{i}/{len(urls)}] {e}")
    
    print(f"\n  {C}========================================{N}")
    if completed: print(f"  {G}+ Completed: {completed}{N} ({total_size/(1024*1024):.1f} MB)")
    if failed: print(f"  {R}x Failed: {failed}{N}")
    print()


@cli.command()
@click.argument("query", required=False)
@click.option("-s", "--service", default="tidal", help="Music service to search")
@click.option("-o", "--output", default=DEFAULT_OUTPUT, help="Download folder")
@click.option("-p", "--parallel", default=4, help="Parallel downloads")
def search(query, service, output, parallel):
    """Search for music and download selected results
    
    Example:
        meloflow search "Daft Punk"
        meloflow search "Get Lucky" -s tidal
    """
    from melo_simple import search_lucida, SERVICES, lucida_download, lucida_download_album
    
    print(f"\n  {C}Search Music{N}")
    print(f"  {C}================{N}\n")
    
    if not query:
        query = input(f"  {G}Enter search query:{N} ").strip()
        if not query:
            print(f"\n  {Y}No query entered{N}\n")
            return
    
    print(f"  {D}Services:{N}")
    service_list = list(SERVICES.items())
    for i, (key, name) in enumerate(service_list, 1):
        marker = " {D}(default){N}" if key == service else ""
        print(f"    {G}{i}.{N} {name}{marker}")
    
    if service not in SERVICES:
        try:
            choice = input(f"\n  {G}Select service (1-{len(service_list)}): {N}").strip()
            if choice:
                idx = int(choice) - 1
                if 0 <= idx < len(service_list):
                    service = service_list[idx][0]
        except ValueError:
            pass
    
    print(f"\n  {C}Searching for: {B}{query}{N} on {SERVICES.get(service, service)}...")
    
    results = search_lucida(query, service=service)
    
    if not results:
        print(f"\n  {Y}No results found{N}\n")
        return
    
    print(f"\n  {G}Found {len(results)} results:{N}\n")
    
    albums = [r for r in results if r['type'] == 'Album']
    tracks = [r for r in results if r['type'] == 'Track']
    
    print(f"  {C}Albums ({len(albums)}):{N}")
    for i, r in enumerate(albums, 1):
        print(f"    {G}{i}.{N} {B}{r['title']}{N}")
    
    print(f"\n  {C}Tracks ({len(tracks)}):{N}")
    start_idx = len(albums)
    for i, r in enumerate(tracks, start_idx + 1):
        print(f"    {G}{i}.{N} {r['title']}")
    
    print(f"\n  {D}Enter numbers to download (e.g., 1,3,5 or 1-3 or 'a' for all albums, 't' for all tracks){N}")
    choice = input(f"  {G}Your selection:{N} ").strip()
    
    if not choice:
        return
    
    to_download = []
    
    if choice.lower() == 'a':
        to_download = albums
    elif choice.lower() == 't':
        to_download = tracks
    else:
        all_results = albums + tracks
        parts = choice.replace(',', ' ').split()
        for part in parts:
            if '-' in part:
                start, end = part.split('-')
                try:
                    to_download.extend(all_results[int(start)-1:int(end)])
                except: pass
            else:
                try:
                    to_download.append(all_results[int(part)-1])
                except: pass
    
    if not to_download:
        print(f"\n  {Y}No valid selection{N}\n")
        return
    
    print(f"\n  {C}Downloading {len(to_download)} items...{N}\n")
    
    os.makedirs(output, exist_ok=True)
    completed, failed = 0, 0
    
    for item in to_download:
        url = item['url']
        is_album = item['type'] == 'Album'
        
        print(f"  {G}->{N} {item['title']} ({item['type']})")
        
        try:
            if is_album:
                result = lucida_download_album(url, output, parallel=parallel, create_zip=False)
            else:
                result = lucida_download(url, output)
            
            if result.success:
                completed += 1
                print(f"    {G}+ Downloaded{N}")
            else:
                failed += 1
                print(f"    {R}x Failed{N}")
        except Exception as e:
            failed += 1
            print(f"    {R}x Error: {e}{N}")
    
    print(f"\n  {C}========================================{N}")
    print(f"  {G}+ Completed: {completed}{N}")
    if failed: print(f"  {R}x Failed: {failed}{N}")
    print()


@cli.command()
def history():
    """Show download history"""
    from melo_simple import show_history
    show_history()


@cli.command()
def services():
    """List supported services"""
    print(f"\n  {B}{C}Supported Services:{N}\n")
    svcs = [("Tidal","High quality FLAC"), ("Qobuz","Hi-Res audio"), ("Deezer","Large catalog"), 
            ("Spotify","Music streaming"), ("Amazon","Prime music"), ("SoundCloud","Indie tracks")]
    for n, d in svcs:
        print(f"  {G}+{N} {B}{n}{N} - {D}{d}{N}\n")


@cli.command()
def config():
    """Show configuration"""
    print(f"\n  {B}{C}Configuration:{N}\n")
    cd = Path.home()/".meloflow"
    print(f"  {C}*{N} Config: {cd}")
    print(f"  {C}*{N} Output: {os.path.abspath(DEFAULT_OUTPUT)}")
    h = load_history()
    print(f"  {C}*{N} History: {len(h)} entries\n")


@cli.command()
@click.argument("folder", required=False)
@click.option("-p", "--prefix", is_flag=True, help="Add track numbers to filenames (e.g., 01 - Artist - Song.flac)")
def sort(folder, prefix):
    """Sort album tracks in correct order
    
    Example:
        meloflow sort "~/Music/My Album"
        meloflow sort "~/Music/My Album" --prefix
    """
    from melo_simple import sort_album_tracks
    
    if not folder:
        print(f"\n  {Y}Error: Folder path required{N}\n")
        return
    
    folder_path = Path(os.path.expanduser(folder))
    if not folder_path.exists():
        print(f"\n  {R}Error: Folder not found: {folder_path}{N}\n")
        return
    
    if not folder_path.is_dir():
        print(f"\n  {R}Error: Not a directory: {folder_path}{N}\n")
        return
    
    print(f"\n  {C}Sorting: {folder_path.name}{N}")
    
    count, msg = sort_album_tracks(folder_path, prefix_with_number=prefix)
    print(f"  {G}{msg}{N}\n")


@cli.command()
@click.argument("url")
@click.option("-o", "--output", default=DEFAULT_OUTPUT, help="Album folder location")
@click.option("--discs", default=None, type=int, help="Number of CDs/discs in album")
def fix_order(url, output, discs):
    """Fix track order for an already-downloaded album
    
    Use this if tracks were downloaded in wrong order.
    
    Example:
        meloflow fix-order https://tidal.com/album/123456
        meloflow fix-order https://tidal.com/album/123456 --discs 2
    """
    from melo_simple import fix_album_track_order
    
    out = os.path.expanduser(output)
    album_path = Path(out)
    
    existing_dirs = [d for d in album_path.iterdir() if d.is_dir() and not d.name.startswith('.')]
    
    if not existing_dirs:
        print(f"\n  {R}No album folders found in {out}{N}\n")
        return
    
    album_dir = existing_dirs[0]
    print(f"\n  {C}Fixing track order for: {album_dir.name}{N}")
    
    count, msg = fix_album_track_order(album_dir, url, discs)
    print(f"  {G}{msg}{N}\n")
    
    if count > 0:
        print(f"  {D}Now run: meloflow sort \"{album_dir}\" --prefix{N}\n")


@cli.command()
@click.option("-o", "--output", default=DEFAULT_OUTPUT, help="Folder to check")
def verify(output):
    """Check downloaded albums for corrupted files
    
    Example:
        meloflow verify
        meloflow verify -o ~/Music
    """
    from melo_simple import scan_album_folder, verify_audio_file
    
    out = os.path.expanduser(output)
    
    existing_dirs = [d for d in Path(out).iterdir() if d.is_dir() and not d.name.startswith('.')]
    
    if not existing_dirs:
        print(f"\n  {Y}No album folders found in {out}{N}\n")
        return
    
    print(f"\n  {C}Verifying {len(existing_dirs)} album(s)...{N}\n")
    
    total_valid, total_corrupt = 0, 0
    
    for album_dir in existing_dirs:
        files = scan_album_folder(album_dir)
        valid, corrupt = 0, 0
        
        print(f"  {B}{album_dir.name}:{N}")
        
        for name, info in files.items():
            fp = info['path']
            if verify_audio_file(fp):
                valid += 1
            else:
                corrupt += 1
                print(f"    {R}  x{N} {name[:50]}")
        
        print(f"    {G}Valid: {valid}{N}")
        if corrupt > 0:
            print(f"    {R}Corrupt: {corrupt}{N}")
        print()
        
        total_valid += valid
        total_corrupt += corrupt
    
    print(f"  {C}Total: {G}{total_valid} valid{N}, {R}{total_corrupt} corrupt{N}\n")


if __name__ == "__main__": cli()
