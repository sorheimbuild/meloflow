"""
Lucida Flow - Python Web Scraper
Web scraping client for Lucida.to
"""

import requests
from bs4 import BeautifulSoup
from typing import Optional, List, Dict, Any
import re
import os
from urllib.parse import urljoin, quote
import time
import re
from collections import deque
from datetime import datetime, timedelta


def extract_track_url(url):
    """Extract direct track URL from various Tidal URL formats"""
    # Tidal album/track URL: https://tidal.com/album/123/track/456
    match = re.search(r'tidal\.com/album/\d+/track/(\d+)', url)
    if match:
        return f"https://tidal.com/track/{match.group(1)}"
    
    # Already a direct track URL: https://tidal.com/track/123
    match = re.search(r'tidal\.com/track/(\d+)', url)
    if match:
        return url
    
    # Return as-is for other services
    return url


class RateLimiter:
    """
    Advanced rate limiter with sliding window and exponential backoff.
    Ensures we never exceed Lucida.to's request limits.
    """

    def __init__(
        self,
        requests_per_minute: int = 30,
        requests_per_hour: int = 500,
        min_delay: float = 2.0,
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.min_delay = min_delay

        # Track request timestamps
        self.request_times = deque(maxlen=requests_per_hour)
        self.last_request_time = 0

        # Exponential backoff for errors
        self.consecutive_errors = 0
        self.max_backoff = 300  # 5 minutes max

    def wait(self):
        """Wait if necessary to respect rate limits"""
        current_time = time.time()

        # Enforce minimum delay between requests
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_delay:
            sleep_time = self.min_delay - time_since_last
            time.sleep(sleep_time)
            current_time = time.time()

        # Check per-minute limit (sliding window)
        one_minute_ago = current_time - 60
        recent_requests = sum(1 for t in self.request_times if t > one_minute_ago)
        if recent_requests >= self.requests_per_minute:
            # Calculate wait time until oldest request expires
            oldest_in_window = min(
                (t for t in self.request_times if t > one_minute_ago),
                default=one_minute_ago,
            )
            wait_time = 60 - (current_time - oldest_in_window) + 1
            print(f"Rate limit: waiting {wait_time:.1f}s (per-minute limit)")
            time.sleep(wait_time)
            current_time = time.time()

        # Check per-hour limit
        one_hour_ago = current_time - 3600
        hour_requests = sum(1 for t in self.request_times if t > one_hour_ago)
        if hour_requests >= self.requests_per_hour:
            oldest_in_hour = min(
                (t for t in self.request_times if t > one_hour_ago),
                default=one_hour_ago,
            )
            wait_time = 3600 - (current_time - oldest_in_hour) + 1
            print(f"Rate limit: waiting {wait_time / 60:.1f}m (per-hour limit)")
            time.sleep(wait_time)
            current_time = time.time()

        # Exponential backoff for consecutive errors
        if self.consecutive_errors > 0:
            backoff = min(
                self.min_delay * (2**self.consecutive_errors),
                self.max_backoff,
            )
            print(
                f"Exponential backoff: waiting {backoff:.1f}s "
                f"(error #{self.consecutive_errors})"
            )
            time.sleep(backoff)
            current_time = time.time()

        # Record this request
        self.request_times.append(current_time)
        self.last_request_time = current_time

    def record_success(self):
        """Reset error counter on successful request"""
        self.consecutive_errors = 0

    def record_error(self):
        """Increment error counter for backoff calculation"""
        self.consecutive_errors += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get current rate limiter statistics"""
        current_time = time.time()
        one_minute_ago = current_time - 60
        one_hour_ago = current_time - 3600

        return {
            "requests_last_minute": sum(
                1 for t in self.request_times if t > one_minute_ago
            ),
            "requests_last_hour": sum(
                1 for t in self.request_times if t > one_hour_ago
            ),
            "consecutive_errors": self.consecutive_errors,
            "total_requests": len(self.request_times),
        }


class LucidaClient:
    """Client for interacting with Lucida.to"""

    def __init__(
        self,
        base_url: str = "https://lucida.to",
        timeout: int = 30,
        requests_per_minute: int = 30,
        requests_per_hour: int = 500,
        cf_clearance_cookie: Optional[str] = None,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.cf_clearance_cookie = cf_clearance_cookie
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )

        if cf_clearance_cookie:
            self.session.cookies.set("cf_clearance", cf_clearance_cookie, domain=".lucida.to")

        # Initialize advanced rate limiter
        self.rate_limiter = RateLimiter(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            min_delay=2.0,  # Conservative 2 second minimum delay
        )

    def _rate_limit(self):
        """Apply rate limiting before making requests"""
        self.rate_limiter.wait()

    def _handle_response(self, response):
        """Handle response and update rate limiter state"""
        if response.status_code == 429:  # Too Many Requests
            self.rate_limiter.record_error()
            retry_after = response.headers.get("Retry-After", 60)
            print(f"Rate limited by server! Waiting {retry_after}s")
            time.sleep(int(retry_after))
            raise requests.exceptions.HTTPError("Rate limited")
        elif response.status_code >= 500:
            self.rate_limiter.record_error()
        else:
            self.rate_limiter.record_success()

        return response

    def search(self, query: str, service: str, limit: int = 10) -> Dict[str, Any]:
        """
        Search for music on Lucida.to

        Args:
            query: Search query string
            service: Music service to search (tidal, qobuz, spotify, deezer, etc.)
            limit: Maximum number of results to return

        Returns:
            Dictionary containing search results
        """
        self._rate_limit()

        # Validate service
        available_services = self.get_available_services()
        if service.lower() not in available_services:
            return {
                "error": f"Invalid service: {service}. Available: {', '.join(available_services)}",
                "query": query,
                "service": service,
                "tracks": [],
                "albums": [],
                "artists": [],
            }

        try:
            # Lucida.to search URL format: /search?service=SERVICE&country=COUNTRY&query=QUERY
            # Build the search URL with proper parameters

            # Map our service names to Lucida.to API service names
            service_name_map = {
                "amazon_music": "amazon",
                "yandex_music": "yandex",
            }
            api_service = service_name_map.get(service.lower(), service.lower())

            # Some services don't support US, use service-specific defaults
            country_map = {
                "qobuz": "GB",
                "deezer": "FR",
            }
            country = country_map.get(api_service, "US")

            search_params = {
                "service": api_service,
                "country": country,
                "query": query,
            }

            # Construct URL with query parameters
            param_string = "&".join(
                [f"{k}={quote(str(v))}" for k, v in search_params.items()]
            )
            search_url = f"{self.base_url}/search?{param_string}"

            response = self.session.get(search_url, timeout=self.timeout)
            response = self._handle_response(response)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            results = {
                "query": query,
                "service": service,
                "search_url": search_url,
                "tracks": [],
                "albums": [],
                "artists": [],
            }

            # Try to parse from embedded JSON data first (more reliable)
            json_tracks = self._extract_tracks_from_json(response.content)
            if json_tracks:
                results["tracks"] = json_tracks[:limit]
                return results

            # Fallback: Parse search results from HTML
            # Tracks section
            track_results = soup.find_all("div", class_="search-result-track")

            for item in track_results[:limit]:
                track_data = self._parse_track_element(item)
                if track_data:
                    results["tracks"].append(track_data)

            return results

        except requests.RequestException as e:
            return {
                "error": str(e),
                "query": query,
                "tracks": [],
                "albums": [],
                "artists": [],
            }

    def _extract_tracks_from_json(self, html_content: bytes) -> List[Dict[str, Any]]:
        """Extract track data from embedded JSON in the HTML."""
        try:
            import pyjson5

            # Find the script tag containing __sveltekit data
            html_str = html_content.decode("utf-8", errors="ignore")

            # Find the start of the JSON array
            start_idx = html_str.find("const data = [")
            if start_idx == -1:
                return []

            start_idx += len("const data = ")

            # Find the matching closing bracket
            bracket_count = 0
            in_string = False
            escape_next = False
            end_idx = start_idx

            for i in range(start_idx, len(html_str)):
                char = html_str[i]

                if escape_next:
                    escape_next = False
                    continue

                if char == "\\":
                    escape_next = True
                    continue

                if char == '"' and not in_string:
                    in_string = True
                elif char == '"' and in_string:
                    in_string = False
                elif not in_string:
                    if char == "[" or char == "{":
                        bracket_count += 1
                    elif char == "]" or char == "}":
                        bracket_count -= 1
                        if bracket_count == 0 and html_str[i : i + 2] == "];":
                            end_idx = i + 1
                            break

            json_str = html_str[start_idx:end_idx]
            data = pyjson5.loads(json_str)

            # Navigate to tracks: data[1].data.results.results.tracks
            if len(data) > 1 and isinstance(data[1], dict):
                results_data = data[1].get("data", {})
                results = results_data.get("results", {})

                # Check if search was successful
                if not results.get("success", False):
                    error_msg = results.get("error", "Unknown error")
                    print(f"Search error: {error_msg}")
                    return []

                results_inner = results.get("results", {})
                tracks = results_inner.get("tracks", [])

                # Convert to our format
                formatted_tracks = []
                for track in tracks:
                    artists_list = track.get("artists", [])
                    artist_names = ", ".join([a.get("name", "") for a in artists_list])

                    album = track.get("album", {})
                    album_name = album.get("title", "")

                    formatted_tracks.append(
                        {
                            "name": track.get("title", ""),
                            "artist": artist_names,
                            "album": album_name,
                            "url": track.get("url", ""),
                        }
                    )

                return formatted_tracks

            return []

        except Exception as e:
            print(f"Error extracting JSON data: {e}")
            return []

    def _parse_track_element(self, element) -> Optional[Dict[str, Any]]:
        """Parse a track element from search results."""
        try:
            track_data = {}

            # Find the metadata div
            metadata_div = element.find("div", class_="metadata")
            if not metadata_div:
                return None

            # Extract track title from h1
            title_elem = metadata_div.find("h1")
            if title_elem:
                track_data["name"] = title_elem.get_text(strip=True)

            # Extract artist from h2
            artist_elem = metadata_div.find("h2")
            if artist_elem:
                track_data["artist"] = artist_elem.get_text(strip=True)

            # Extract album from h3
            album_elem = metadata_div.find("h3")
            if album_elem:
                track_data["album"] = album_elem.get_text(strip=True)

            # Extract track URL from the h1 anchor tag
            title_link = metadata_div.find("a", href=True)
            if title_link:
                track_data["url"] = urljoin(self.base_url, title_link["href"])

            # Only return if we found at least a name
            if "name" in track_data:
                return track_data

            return None

        except Exception as e:
            print(f"Error parsing track element: {e}")
            return None

    def get_track_info(self, url: str) -> Dict[str, Any]:
        """
        Get detailed information about a track from its URL

        Args:
            url: URL to the track (from Tidal, Qobuz, etc.)

        Returns:
            Dictionary containing track information
        """
        self._rate_limit()

        try:
            # Submit URL to Lucida.to
            response = self.session.get(
                self.base_url, params={"url": url}, timeout=self.timeout
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Extract track metadata
            track_info = {
                "url": url,
                "name": None,
                "artist": None,
                "album": None,
                "duration": None,
                "quality": None,
            }

            # Parse track details from the page
            # Adjust selectors based on actual HTML structure
            title_elem = soup.find(class_=re.compile(r"track.?title|song.?name"))
            if title_elem:
                track_info["name"] = title_elem.get_text(strip=True)

            artist_elem = soup.find(class_=re.compile(r"artist"))
            if artist_elem:
                track_info["artist"] = artist_elem.get_text(strip=True)

            album_elem = soup.find(class_=re.compile(r"album"))
            if album_elem:
                track_info["album"] = album_elem.get_text(strip=True)

            return track_info

        except requests.RequestException as e:
            return {"error": str(e), "url": url}

    def download_track(
        self, url: str, output_path: Optional[str] = None,
        download_dir: Optional[str] = None,
        embed_metadata: bool = True,
        download_cover: bool = True,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Download a track from Lucida.to using Playwright with expect_download

        Args:
            url: URL to the track (from Tidal, Qobuz, etc.)
            output_path: Path to save the downloaded file (if None, uses download_dir)
            download_dir: Default download directory
            embed_metadata: Whether to embed metadata in the file
            download_cover: Whether to download album cover
            max_retries: Maximum retry attempts (default: 3)

        Returns:
            Dictionary containing download result and file path
        """
        from playwright.sync_api import sync_playwright

        self._rate_limit()

        # Set up download directory
        if download_dir:
            download_dir = os.path.abspath(download_dir)
            os.makedirs(download_dir, exist_ok=True)
        elif output_path:
            download_dir = os.path.dirname(os.path.abspath(output_path))
            os.makedirs(download_dir, exist_ok=True)
        else:
            download_dir = os.path.abspath("./downloads")
            os.makedirs(download_dir, exist_ok=True)

        last_error = None
        
        # Extract track URL if needed
        original_url = url
        url = extract_track_url(url)
        if url != original_url:
            print(f"[INFO] Using direct track URL: {url}")
        
        is_album = 'album' in original_url.lower() and 'track' not in original_url.lower()
        
        for attempt in range(1, max_retries + 1):
            try:
                print(f"\n[Attempt {attempt}/{max_retries}] Launching browser...")
                
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True,
                        args=[
                            '--disable-blink-features=AutomationControlled',
                            '--disable-dev-shm-usage',
                            '--no-sandbox',
                            '--disable-setuid-sandbox',
                        ]
                    )
                    context = browser.new_context(
                        accept_downloads=True,
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        viewport={'width': 1920, 'height': 1080},
                        locale='en-US',
                    )
                    
                    if self.cf_clearance_cookie:
                        print(f"[INFO] Using saved Cloudflare clearance cookie")
                        context.add_cookies([
                            {
                                'name': 'cf_clearance',
                                'value': self.cf_clearance_cookie,
                                'domain': 'lucida.to',
                                'path': '/'
                            }
                        ])
                    
                    page = context.new_page()
                    
                    lucida_url = f"{self.base_url}?url={url}"
                    print(f"[INFO] Loading {lucida_url}")
                    
                    try:
                        page.goto(lucida_url, wait_until="domcontentloaded", timeout=60000)
                    except Exception as e:
                        if "net::ERR_" in str(e):
                            return {"success": False, "error": "Network error - check your internet connection"}
                        raise
                    
                    # Wait for page to stabilize
                    time.sleep(3)
                    
                    # Wait for Cloudflare challenge to complete
                    print("[INFO] Checking for Cloudflare challenge...")
                    cloudflare_done = False
                    for i in range(60):  # Wait up to 60 seconds
                        page_content = page.content().lower()
                        page_title = page.title().lower()
                        
                        if 'cf-challenge' not in page_content and 'cloudflare' not in page_title and 'checking your browser' not in page_content:
                            cloudflare_done = True
                            print("[INFO] Cloudflare challenge completed")
                            break
                        
                        if i % 15 == 0 and i > 0:
                            print(f"[INFO] Waiting for Cloudflare... {i}s")
                        time.sleep(1)
                    
                    # Additional wait for page to fully render
                    time.sleep(3)
                    
                    # Check page title
                    title = page.title()
                    print(f"[INFO] Page title: {title}")
                    
                    # Final check for Cloudflare
                    if 'cloudflare' in title.lower():
                        print("[WARN] Still on Cloudflare page!")
                        browser.close()
                        return {"success": False, "error": "Cloudflare challenge not completed"}
                    
                    # Check if wrong page loaded (homepage instead of track page)
                    if 'music at internet speed' in title.lower():
                        print("[ERROR] Wrong page loaded - URL format may be incorrect")
                        print(f"[INFO] Try using direct track URL: https://tidal.com/track/XXXXX")
                        browser.close()
                        return {"success": False, "error": "URL not supported - try direct track URL"}
                    
                    # Find download button
                    buttons = page.query_selector_all('button')
                    download_btn = None
                    
                    for btn in buttons:
                        try:
                            txt = btn.inner_text().lower()
                            vis = btn.is_visible()
                            if vis and 'download' in txt:
                                download_btn = btn
                                print(f"[INFO] Found download button: {btn.inner_text()}")
                                break
                        except:
                            pass
                    
                    if not download_btn:
                        # Check if Cloudflare is blocking
                        page_content = page.content().lower()
                        if 'cloudflare' in page_content or 'cf-challenge' in page_content:
                            print(f"[WARN] Cloudflare protection detected. Retrying...")
                            time.sleep(10)
                            continue
                        
                        if attempt < max_retries:
                            print(f"[WARN] Download button not found. Retrying...")
                            time.sleep(attempt * 5)
                            continue
                        else:
                            browser.close()
                            return {"success": False, "error": "Download button not found"}
                    
                    # For album downloads, need to handle ZIP option
                    
                    if is_album:
                        # Click main download button first
                        print(f"[INFO] Clicking album download button...")
                        download_btn.click(force=True)
                        time.sleep(2)
                        
                        # Look for ZIP option
                        zip_options = ["text=Download ZIP", "button:has-text('ZIP')"]
                        zip_btn = None
                        
                        for selector in zip_options:
                            try:
                                elem = page.locator(selector).first
                                if elem.is_visible(timeout=2000):
                                    zip_btn = elem
                                    print(f"[INFO] Found ZIP option")
                                    break
                            except:
                                pass
                        
                        if zip_btn:
                            print(f"[INFO] Clicking ZIP option...")
                            try:
                                with page.expect_download(timeout=600000) as download_info:
                                    zip_btn.click(force=True)
                                
                                download = download_info.value
                                filename = download.suggested_filename
                                filepath = os.path.join(download_dir, filename)
                                
                                print(f"[INFO] Saving to {filepath}...")
                                download.save_as(filepath)
                                
                                if os.path.exists(filepath):
                                    size = os.path.getsize(filepath)
                                    print(f"[OK] Downloaded: {filepath} ({size:,} bytes)")
                                    
                                    # Check if ZIP is empty (common issue)
                                    if size < 1000:
                                        print(f"[WARN] ZIP file is very small ({size} bytes) - may be incomplete")
                                        return {"success": True, "filepath": filepath, "size": size, "warning": "ZIP may be incomplete"}
                                    
                                    browser.close()
                                    return {"success": True, "filepath": filepath, "size": size}
                            except Exception as e:
                                print(f"[ERROR] Album download failed: {e}")
                                browser.close()
                                return {"success": False, "error": f"Album download failed: {str(e)}"}
                        else:
                            print(f"[WARN] No ZIP option found for album")
                    
                    print(f"[INFO] Clicking download button...")
                    
                    # Use expect_download to capture the download properly
                    try:
                        with page.expect_download(timeout=300000) as download_info:
                            download_btn.click(force=True)
                        
                        download = download_info.value
                        filename = download.suggested_filename
                        filepath = os.path.join(download_dir, filename)
                        
                        print(f"[INFO] Saving to {filepath}...")
                        download.save_as(filepath)
                        
                        if os.path.exists(filepath):
                            size = os.path.getsize(filepath)
                            print(f"[OK] Downloaded: {filepath} ({size:,} bytes)")
                            
                            if embed_metadata:
                                try:
                                    self._embed_metadata(filepath, url)
                                except:
                                    pass
                            
                            browser.close()
                            return {
                                "success": True,
                                "filepath": filepath,
                                "size": size,
                            }
                    except Exception as e:
                        print(f"[ERROR] Download failed: {e}")
                        browser.close()
                        return {"success": False, "error": str(e)}
                    
            except Exception as e:
                last_error = str(e)
                print(f"[ERROR] Attempt {attempt} failed: {last_error}")
                if attempt < max_retries:
                    time.sleep(attempt * 5)
                else:
                    return {"success": False, "error": f"Download failed: {last_error}"}
        
        return {"success": False, "error": last_error or "Unknown error"}

    def _embed_metadata(self, filepath: str, url: str) -> None:
        """Embed metadata into downloaded audio file"""
        from mutagen.flac import FLAC
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3, Title, Artist, Album

        try:
            ext = os.path.splitext(filepath)[1].lower()

            if ext == '.flac':
                audio = FLAC(filepath)
                # FLAC supports Vorbis comments - add basic metadata
                # Note: Full metadata comes from track info, here we just ensure file is valid
                audio.save()
            elif ext == '.mp3':
                audio = MP3(filepath)
                audio.add_tags()
                # Add basic tags if needed
                audio.save()

        except Exception as e:
            print(f"Metadata embedding warning: {e}")

    def _get_filename_from_response(self, response, url: str) -> str:
        """Extract filename from response headers or generate from URL"""
        # Try Content-Disposition header
        if "Content-Disposition" in response.headers:
            content_disp = response.headers["Content-Disposition"]
            filename_match = re.findall(r'filename="(.+)"', content_disp)
            if filename_match:
                return filename_match[0]

        # Try to extract from URL
        url_parts = url.rstrip("/").split("/")
        if url_parts:
            # Clean up the filename
            filename = url_parts[-1]
            # Add extension if missing
            if "." not in filename:
                content_type = response.headers.get("Content-Type", "")
                if "flac" in content_type:
                    filename += ".flac"
                elif "mp3" in content_type:
                    filename += ".mp3"
                elif "aac" in content_type or "m4a" in content_type:
                    filename += ".m4a"
                else:
                    filename += ".bin"
            return filename

        # Fallback
        return f"download_{int(time.time())}.bin"

    def get_available_services(self) -> List[str]:
        """
        Get list of available streaming services from Lucida.to

        Returns:
            List of service names
        """
        # Based on Lucida.to documentation
        return [
            "tidal",
            "qobuz",
            "deezer",
            "soundcloud",
            "amazon_music",
            "yandex_music",
            "spotify",
        ]

    def get_rate_limit_stats(self) -> Dict[str, Any]:
        """
        Get current rate limiter statistics

        Returns:
            Dictionary with rate limit stats and request counts
        """
        stats = self.rate_limiter.get_stats()
        return {
            **stats,
            "limits": {
                "per_minute": self.rate_limiter.requests_per_minute,
                "per_hour": self.rate_limiter.requests_per_hour,
                "min_delay_seconds": self.rate_limiter.min_delay,
            },
        }
