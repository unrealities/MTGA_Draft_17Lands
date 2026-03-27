import os
import json
import hashlib
import time
import random
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

        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self._last_request_time = {
            "api.scryfall.com": 0.0,
            "www.17lands.com": 0.0,
        }
        self._domain_delays = {
            "api.scryfall.com": config.DELAY_SCRYFALL_SEC,
            "www.17lands.com": config.DELAY_17LANDS_SEC,
        }

        self._cache_dir = os.path.join(config.OUTPUT_DIR, ".cache")
        os.makedirs(self._cache_dir, exist_ok=True)

        self.request_count: int = 0
        self.failed_request_count: int = 0
        self.cached_request_count: int = 0

    def _get_cache_path(self, full_url):
        url_hash = hashlib.md5(full_url.encode("utf-8")).hexdigest()
        return os.path.join(self._cache_dir, f"{url_hash}.json")

    def _read_cache(self, full_url):
        path = self._get_cache_path(full_url)
        if os.path.exists(path):
            if time.time() - os.path.getmtime(path) < 43200:  # 12-hour TTL
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        return CachedResponse(data["status_code"], data["json_data"])
                except Exception:
                    pass
        return None

    def _write_cache(self, full_url, response):
        try:
            json_data = response.json()
        except Exception:
            return  # Don't cache non-JSON

        data = {"status_code": response.status_code, "json_data": json_data}
        path = self._get_cache_path(full_url)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def respectful_get(
        self, url, params=None, timeout=config.REQUEST_TIMEOUT_SEC, allow_404=False
    ):
        # Prepare the full URL so our cache key perfectly matches the parameters
        req = requests.Request("GET", url, params=params).prepare()
        full_url = req.url

        cached_resp = self._read_cache(full_url)
        if cached_resp:
            self.cached_request_count += 1
            if cached_resp.status_code == 404 and allow_404:
                return cached_resp
            cached_resp.raise_for_status()
            return cached_resp

        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        base_delay = self._domain_delays.get(domain, 0.0)

        for attempt in range(config.MAX_ATTEMPTS):
            last_time = self._last_request_time.get(domain, 0.0)
            elapsed = time.time() - last_time

            # Anti-Bot Jitter: Add 0.5 to 2.5s of random delay so we don't look like a metronome
            jitter = random.uniform(0.5, 2.5) if base_delay > 0 else 0.0
            total_delay = base_delay + jitter

            if elapsed < total_delay:
                time.sleep(total_delay - elapsed)

            try:
                self.request_count += 1
                resp = self.session.get(url, params=params, timeout=timeout)
                self._last_request_time[domain] = time.time()

                # Handle WAF Blocks (403) and Rate Limits (429) gracefully
                if resp.status_code in (403, 429):
                    wait = (
                        config.WAF_COOLDOWN_SEC
                        if resp.status_code == 403
                        else config.RETRY_BASE_DELAY_SEC * (2**attempt)
                    )
                    logger.warning(
                        f"HTTP {resp.status_code} on {domain}. Backing off {wait}s to cool down IP..."
                    )
                    time.sleep(wait)
                    continue

                if resp.status_code == 404 and allow_404:
                    self._write_cache(full_url, resp)
                    return resp

                resp.raise_for_status()
                self._write_cache(full_url, resp)
                return resp

            except (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
            ) as e:
                self._last_request_time[domain] = time.time()
                wait = config.RETRY_BASE_DELAY_SEC * (2**attempt)
                logger.warning(
                    f"Network error on {full_url}: {e}. Retrying in {wait}s..."
                )
                time.sleep(wait)

            except requests.exceptions.HTTPError as e:
                self._last_request_time[domain] = time.time()
                status = e.response.status_code if e.response is not None else 0
                if attempt < config.MAX_ATTEMPTS - 1 and status >= 500:
                    wait = config.RETRY_BASE_DELAY_SEC * (2**attempt)
                    logger.warning(
                        f"Server error {status} on {full_url}. Retrying in {wait}s..."
                    )
                    time.sleep(wait)
                else:
                    self.failed_request_count += 1
                    logger.error(f"Fatal HTTP error on {full_url}: {e}")
                    raise

        self.failed_request_count += 1
        logger.error(f"FAILED after {config.MAX_ATTEMPTS} attempts: {full_url}.")
        raise Exception(f"Max retries ({config.MAX_ATTEMPTS}) exceeded for {full_url}")
