#!/usr/bin/env python3
"""Lucida Flow CLI"""

import os, sys

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import click
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from lucida_simple import lucida_download, load_history, BANNER, C, G, Y, R, B, D, N

DEFAULT_OUTPUT = os.getenv("DOWNLOAD_DIR", "./downloads")


def p(msg, color=""):
    if color: print(f"{color}{msg}{N}")
    else: print(msg)


@click.group(invoke_without_command=True)
@click.version_option(version="1.1.0", prog_name="lucida-flow")
def cli():
    """Lucida Flow - Download music from Tidal, Qobuz, Spotify & more"""
    print(BANNER)
    print(f"  {D}Download music from streaming services{N}\n")
    print(f"  {C}Commands:{N}\n")
    print(f"    {G}download{N} <url>          Download a track or album")
    print(f"    {G}download{N} <url> {D}-o ~/Music{R}  Download to folder")
    print(f"    {G}download{N} <url> {D}-p 4{R}        Download with 4 parallel")
    print(f"    {G}history{N}                  Show download history")
    print(f"    {G}services{N}                 List supported services\n")


@cli.command()
@click.argument("url", required=False)
@click.option("-o", "--output", default=DEFAULT_OUTPUT)
@click.option("-t", "--timeout", default=300, help="Timeout in seconds")
@click.option("-q", "--quality", default="best", type=click.Choice(["best","flac","mp3","aac"]))
@click.option("-f", "--file", "file_path", help="File with URLs")
@click.option("-p", "--parallel", default=1, type=int)
@click.option("-r", "--retries", default=3, type=int)
@click.option("--no-info", is_flag=True)
def download(url, output, timeout, quality, file_path, parallel, retries, no_info):
    """Download tracks from streaming services"""
    if not url and not file_path:
        print(f"\n  {R}Error: URL or --file required{N}\n")
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
    print(f"  {C}|{N} Retries:  {retries}\n")
    
    completed, failed, total_size = 0, 0, 0
    
    if parallel == 1:
        for i, u in enumerate(urls, 1):
            if len(urls) > 1: print(f"\n  {B}[{i}/{len(urls)}] Downloading:{N}")
            r = lucida_download(u, out, quality, timeout, not no_info, retries)
            
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
            futures = {ex.submit(lucida_download, u, out, quality, timeout, False, retries): u for u in urls}
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
def history():
    """Show download history"""
    from lucida_simple import show_history
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
    cd = Path.home()/".lucida-flow"
    print(f"  {C}*{N} Config: {cd}")
    print(f"  {C}*{N} Output: {os.path.abspath(DEFAULT_OUTPUT)}")
    h = load_history()
    print(f"  {C}*{N} History: {len(h)} entries\n")


if __name__ == "__main__": cli()
