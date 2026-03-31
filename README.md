<div align="center">
  <img src="lucida_flow.png" alt="Lucida Flow Logo" width="600"/>
  
  # Lucida Flow
  
  A powerful CLI tool for downloading high-quality music from Tidal, Qobuz, and more via [Lucida.to](https://lucida.to).
  
  **No credentials required!** Uses Playwright to automate downloads through the web interface.
  
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
  
</div>

## Features

- 🎵 **Album Downloads**: Batch download entire albums with parallel workers
- 🔄 **Auto-Retry**: Automatically retries failed tracks until all succeed
- ⏭️ **Skip/Resume**: Detects existing files, skips already downloaded tracks
- 📋 **Manifest Tracking**: `.lucida_manifest.json` tracks all downloaded files
- 💾 **Integrity Verification**: Uses ffprobe to verify downloaded files aren't corrupted
- 📦 **ZIP Creation**: Package albums into ZIP archives
- 💿 **Multi-Disc Support**: Handles multi-disc albums with `--discs N` flag
- 🔢 **Track Sorting**: Sort files by album order with `--sort` command
- 🎨 **Track Prefixes**: Add disc/track prefixes (e.g., `1-01 - Artist - Track.flac`)
- 🏷️ **Metadata Embedding**: Embed track numbers in audio files via ffmpeg
- ⚙️ **Configurable**: Parallel workers, retry count, pause duration all adjustable

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Quick Start

1. **Install dependencies:**

```bash
pip install -r requirements.txt
```

2. **Install Playwright browsers (required for downloads):**

```bash
playwright install chromium
```

3. **Try the CLI:**

```bash
# Search uses Amazon Music by default
python cli.py search "hotel california"
python cli.py search "daft punk" --limit 5

# List available services
python cli.py services
```

4. **Start the API:**

```bash
python api_server.py
# Visit http://localhost:8000/docs for interactive API documentation
```

## CLI Usage

### Search for Music

```bash
# Search Amazon Music (default)
python cli.py search "hotel california"
python cli.py search "shape of you" --limit 5

# Search other services
python cli.py search "daft punk get lucky" --service tidal
python cli.py search "album name" -s qobuz
```

### Download Music

```bash
python cli.py download "https://tidal.com/browse/track/123456"
python cli.py download "https://open.qobuz.com/track/123456" -o ./my-music/song.flac
```

### Get Track Information

```bash
python cli.py info "https://tidal.com/browse/track/123456"
```

### List Available Services

```bash
python cli.py services
```

## API Usage

### Start Server

```bash
python api_server.py
```

API docs: `http://localhost:8000/docs`

### Example Requests

**Search:**

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "daft punk", "service": "tidal", "limit": 5}'
```

**Download:**

```bash
curl -X POST http://localhost:8000/download-file \
  -H "Content-Type: application/json" \
  -d '{"url": "https://tidal.com/browse/track/123456"}' \
  --output track.flac
```

See full documentation in [DOCUMENTATION.md](DOCUMENTATION.md)

## Project Structure

```
lucida_flow/
├── lucida_client.py        # Core web scraping client
├── cli.py                  # CLI application
├── api_server.py           # FastAPI server
├── requirements.txt        # Dependencies
├── .env                    # Configuration (optional)
└── downloads/              # Default download directory
```

## Configuration (Optional)

Create `.env` file:

```env
DOWNLOAD_DIR=./downloads
API_HOST=0.0.0.0
API_PORT=8000
LUCIDA_BASE_URL=https://lucida.to
REQUEST_TIMEOUT=30
```

## How It Works

This tool uses browser automation (Playwright) to interact with Lucida.to's web interface for downloads, and web scraping for search. No service credentials required!

**Technical Details:**

- **Search**: Uses HTTP requests + BeautifulSoup to parse Lucida.to search results
- **Downloads**: Uses Playwright to automate a headless Chrome browser that clicks the download button on Lucida.to
- **Rate Limiting**: Enterprise-grade sliding window algorithm (30 req/min, 500 req/hour, 2s min delay)

## Disclaimer

For educational and personal use only. Respect copyright laws and terms of service.

## Credits

- Built for [Lucida.to](https://lucida.to)
- Lucida library by [hazycora](https://hazy.gay/)

## License

MIT License

---

## Commands (Easy Guide)

### Download Albums & Tracks
```bash
# Download an album (simplest)
lucida-flow download https://tidal.com/album/123456

# Download to a specific folder
lucida-flow download https://tidal.com/album/123456 -o ~/Music

# Download with faster speed (4 tracks at once)
lucida-flow download https://tidal.com/album/123456 -p 4

# Multi-disc album (e.g., 2 CDs)
lucida-flow download https://tidal.com/album/123456 --discs 2

# Download with extra options
lucida-flow download URL --zip --embed-metadata --verify
```

### Sort & Organize
```bash
# Sort tracks in album order
lucida-flow sort "~/Music/Album Name"

# Sort with track numbers in filenames
lucida-flow sort "~/Music/Album Name" --prefix
# Result: "01 - Artist - Song.flac", "02 - Artist - Song.flac"

# Multi-disc: "1-01 - Song.flac", "2-01 - Song.flac"
```

### Fix & Verify
```bash
# Check all albums for corrupted files
lucida-flow verify

# Check specific folder
lucida-flow verify -o ~/Music

# Fix track order if downloaded wrong
lucida-flow fix-order https://tidal.com/album/123456

# Fix multi-disc album
lucida-flow fix-order https://tidal.com/album/123456 --discs 2
```

### Other Commands
```bash
lucida-flow history      # See what you've downloaded
lucida-flow services     # List supported streaming services
lucida-flow config       # Show current settings
lucida-flow --help       # Full help with all options
```

### Common Download Options
| Option | What it does |
|--------|--------------|
| `-o folder` | Save to folder |
| `-p 4` | Download 4 tracks at once |
| `-r 5` | Retry failed tracks 5 times |
| `--zip` | Make ZIP file after download |
| `--verify` | Check for corrupted files |
| `--no-auto-retry` | Don't keep retrying automatically |
| `--pause 30` | Wait 30 seconds between retries |

### How Skip/Resume Works

Lucida Flow remembers what you've downloaded. Run the same album URL again and it will skip tracks you already have, download only missing tracks, and check for corrupted files.

Tracks are tracked in `.lucida_manifest.json` inside each album folder:
```json
{
  "_meta": {
    "url": "https://tidal.com/album/...",
    "name": "Album Name"
  },
  "https://tidal.com/track/123456": {
    "filename": "Artist - Track Name.flac",
    "size": 23000000,
    "track": 1,
    "disc": 1
  }
}
```

### Project Architecture
```
lucida-flow/
├── lucida_simple.py    # Core download logic (~1300 lines)
│   ├── DownloadResult         # Result object with counts
│   ├── lucida_download()      # Single track download
│   ├── lucida_download_album()  # Album with parallel workers
│   ├── parse_album_for_tracks()  # Extract from lucida.to
│   ├── verify_file()          # ffprobe integrity check
│   ├── sort_album_tracks()   # Sort by manifest order
│   └── fix_album_track_order()  # Re-fetch order
├── cli.py             # Click CLI (~280 lines)
├── README.md           # This file
└── backups/           # Previous versions
```

### Known Limitations
1. **Track names** - lucida.to shows "Track 1", "Track 2" until download
2. **No disc info** - Use `--discs N` for multi-disc albums
3. **No lyrics** - lucida.to doesn't support; lyrics.ovh has limited coverage
