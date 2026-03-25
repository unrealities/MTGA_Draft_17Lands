import os
import json
import hashlib
import time
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse
from server import config

logger = logging.getLogger(__name__)


class CachedResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        if self._json_data is None:
            raise ValueError("Not JSON")
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400 and self.status_code != 404:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


class APIClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(config.HEADERS)

        # Optimize underlying TCP connections
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Rate limiter setup
        self._last_request_time = {
            "api.scryfall.com": 0.0,
            "www.17lands.com": 0.0,
        }
        self._domain_delays = {
            "api.scryfall.com": config.DELAY_SCRYFALL_SEC,
            "www.17lands.com": config.DELAY_17LANDS_SEC,
        }

        # Cache setup
        self._cache_dir = os.path.join(config.OUTPUT_DIR, ".cache")
        if not os.path.exists(self._cache_dir):
            os.makedirs(self._cache_dir, exist_ok=True)

        # Counters exposed to the run-report
        self.request_count: int = 0
        self.failed_request_count: int = 0
        self.cached_request_count: int = 0

    def _get_cache_path(self, url):
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
        return os.path.join(self._cache_dir, f"{url_hash}.json")

    def _read_cache(self, url):
        path = self._get_cache_path(url)
        if os.path.exists(path):
            # 12-hour TTL for the local HTTP cache
            if time.time() - os.path.getmtime(path) < 43200:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        return CachedResponse(data["status_code"], data["json_data"])
                except Exception:
                    pass
        return None

    def _write_cache(self, url, response):
        try:
            json_data = response.json()
        except Exception:
            # Prevent Cache Poisoning: Do not cache non-JSON payloads
            return

        data = {"status_code": response.status_code, "json_data": json_data}
        path = self._get_cache_path(url)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def respectful_get(self, url, timeout=config.REQUEST_TIMEOUT_SEC, allow_404=False):
        # 1. Check disk cache first. Instant return if found!
        cached_resp = self._read_cache(url)
        if cached_resp:
            self.cached_request_count += 1
            if cached_resp.status_code == 404 and allow_404:
                return cached_resp
            cached_resp.raise_for_status()
            return cached_resp

        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        delay = self._domain_delays.get(domain, 0.0)

        # 2. Request loop with Backoff
        for attempt in range(config.MAX_ATTEMPTS):

            # Domain-aware rate limiter logic (Checked inside the loop for retries)
            last_time = self._last_request_time.get(domain, 0.0)
            elapsed = time.time() - last_time
            if elapsed < delay:
                time.sleep(delay - elapsed)

            try:
                self.request_count += 1
                resp = self.session.get(url, timeout=timeout)
                self._last_request_time[domain] = time.time()

                if resp.status_code == 429:
                    wait = config.RETRY_BASE_DELAY_SEC * (2**attempt)
                    logger.warning(
                        f"HTTP 429 (Rate Limit) on {url}. Backing off {wait}s..."
                    )
                    time.sleep(wait)
                    continue

                if resp.status_code == 404 and allow_404:
                    self._write_cache(url, resp)
                    return resp

                resp.raise_for_status()
                self._write_cache(url, resp)
                return resp

            except (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
            ) as e:
                self._last_request_time[domain] = time.time()
                wait = config.RETRY_BASE_DELAY_SEC * (2**attempt)
                logger.warning(f"Network error on {url}: {e}. Retrying in {wait}s...")
                time.sleep(wait)

            except requests.exceptions.HTTPError as e:
                self._last_request_time[domain] = time.time()
                status = e.response.status_code if e.response is not None else 0
                if attempt < config.MAX_ATTEMPTS - 1 and status >= 500:
                    wait = config.RETRY_BASE_DELAY_SEC * (2**attempt)
                    logger.warning(
                        f"Server error {status} on {url}. Retrying in {wait}s..."
                    )
                    time.sleep(wait)
                else:
                    self.failed_request_count += 1
                    logger.error(f"Fatal HTTP error on {url}: {e}")
                    raise

        self.failed_request_count += 1
        logger.error(f"FAILED after {config.MAX_ATTEMPTS} attempts: {url}.")
        raise Exception(f"Max retries ({config.MAX_ATTEMPTS}) exceeded for {url}")
