import os
import json
import gzip
import hashlib
import io
import logging
import math
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import quote

import requests
from src import constants
from src.configuration import CONFIG_LOCK
from src.dataset_manifest import validate_manifest

logger = logging.getLogger(__name__)

MAX_COMPRESSED_BYTES = 32 * 1024 * 1024
MAX_DATASET_BYTES = 256 * 1024 * 1024


def validate_dataset_payload(data):
    """Check the structure consumed by Dataset before replacing a working cache."""
    if not isinstance(data, dict) or not isinstance(data.get("meta"), dict):
        raise ValueError("Dataset must contain metadata")
    meta = data["meta"]
    if type(meta.get("version")) not in (int, float) or meta["version"] not in (1, 2, 3):
        raise ValueError("Unsupported dataset version")
    if meta["version"] == 1:
        start, end = meta.get("date_range", "").split("->")
    else:
        start, end = meta.get("start_date"), meta.get("end_date")
    if date.fromisoformat(start) > date.fromisoformat(end):
        raise ValueError("Dataset date range is reversed")
    if not isinstance(meta.get("collection_date", ""), str):
        raise ValueError("Invalid collection timestamp")
    if "game_count" in meta and (
        type(meta["game_count"]) is not int or meta["game_count"] < 0
    ):
        raise ValueError("Invalid game count")
    cards = data.get("card_ratings")
    if not isinstance(cards, dict) or len(cards) < 10:
        raise ValueError("Dataset must contain at least ten card ratings")
    if not isinstance(data.get("color_ratings", {}), dict):
        raise ValueError("Invalid color ratings")

    def valid_number(value):
        return type(value) in (int, float) and math.isfinite(value)

    if any(
        not valid_number(value) for value in data.get("color_ratings", {}).values()
    ):
        raise ValueError("Invalid color win rate")
    for card in cards.values():
        if (
            not isinstance(card, dict)
            or not isinstance(card.get("name"), str)
            or not card["name"]
        ):
            raise ValueError("Invalid card rating")
        colors = card.get("deck_colors")
        if not isinstance(colors, dict) or not isinstance(colors.get("All Decks"), dict):
            raise ValueError("Card is missing All Decks statistics")
        if any(not isinstance(stats, dict) for stats in colors.values()):
            raise ValueError("Invalid archetype statistics")
        if any(
            not valid_number(value)
            for stats in colors.values() for value in stats.values()
        ):
            raise ValueError("Invalid archetype statistic value")
        if "cmc" in card and not valid_number(card["cmc"]):
            raise ValueError("Invalid card mana value")
        for field in ("colors", "types", "image"):
            if field in card and (
                not isinstance(card[field], list)
                or any(not isinstance(item, str) for item in card[field])
            ):
                raise ValueError(f"Invalid card {field}")


class DatasetUpdater:
    def __init__(self, config):
        self.config = config
        self.local_manifest_path = os.path.join(constants.SETS_FOLDER, "local_manifest.json")

    def get_local_manifest(self):
        try:
            with open(self.local_manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("datasets"), dict):
                return data
        except (OSError, ValueError):
            pass
        return {"datasets": {}}

    def save_local_manifest(self, manifest_data):
        fd, tmp_path = tempfile.mkstemp(dir=constants.SETS_FOLDER, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f)
            os.replace(tmp_path, self.local_manifest_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _destination(self, filename):
        root = Path(constants.SETS_FOLDER).resolve()
        destination = root / filename
        if destination.resolve().parent != root:
            raise ValueError("Dataset destination is outside Sets")
        return destination

    def _download(self, filename, expected_hash):
        url = constants.REMOTE_DATASET_BASE_URL + quote(filename, safe="")
        with requests.get(url, timeout=15, stream=True) as response:
            response.raise_for_status()
            compressed = bytearray()
            digest = hashlib.sha256()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if len(compressed) + len(chunk) > MAX_COMPRESSED_BYTES:
                    raise ValueError("Compressed dataset exceeds size limit")
                compressed.extend(chunk)
                digest.update(chunk)
        if digest.hexdigest() != expected_hash.lower():
            raise ValueError("Dataset SHA-256 checksum mismatch")
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as archive:
            payload = archive.read(MAX_DATASET_BYTES + 1)
        if len(payload) > MAX_DATASET_BYTES:
            raise ValueError("Decompressed dataset exceeds size limit")

        def reject_constant(value):
            raise ValueError(f"Invalid JSON number: {value}")

        data = json.loads(payload.decode("utf-8"), parse_constant=reject_constant)
        validate_dataset_payload(data)
        return payload

    def sync_datasets(self, progress_callback):
        """Install only confined, checksum-verified, bounded and valid datasets."""
        try:
            try:
                report_resp = requests.get(
                    constants.REMOTE_DATASET_BASE_URL + "report.json", timeout=3
                )
                if (
                    report_resp.status_code == 200
                    and report_resp.json().get("pipeline_run", {}).get("status") == "FAILED"
                ):
                    progress_callback("⚠️ Server sync failed today. Using cached data.")
            except Exception as health_e:
                logger.debug(f"Failed to fetch health report (non-fatal): {health_e}")

            progress_callback("Checking for official dataset updates...")
            resp = requests.get(constants.REMOTE_MANIFEST_URL, timeout=5)
            resp.raise_for_status()
            remote_manifest = validate_manifest(resp.json())
            active_sets = remote_manifest.get("active_sets")
            if not isinstance(active_sets, list) or any(
                not isinstance(code, str) or not code.strip() for code in active_sets
            ):
                raise ValueError("Manifest is missing a valid active_sets list")
            active_set_codes = set(active_sets)
            local_manifest = self.get_local_manifest()
            updates_made = False
            failures = 0

            for key, file_info in remote_manifest["datasets"].items():
                # The warehouse also retains historical sets. Only the schedule's
                # exact set identifiers are eligible for automatic downloads.
                if key.rsplit("_", 2)[0] not in active_set_codes:
                    continue
                local_filename = file_info["filename"][:-3]
                if local_filename in self.config.card_data.excluded_datasets:
                    continue
                tmp_path = None
                try:
                    local_filepath = self._destination(local_filename)
                    local_info = local_manifest["datasets"].get(key, {})
                    if not isinstance(local_info, dict):
                        local_info = {}
                    if (
                        local_filepath.exists()
                        and local_info.get("hash") == file_info["hash"]
                    ):
                        continue
                    progress_callback(f"Downloading {key}...")
                    payload = self._download(file_info["filename"], file_info["hash"])
                    fd, tmp_path = tempfile.mkstemp(dir=constants.SETS_FOLDER, suffix=".tmp")
                    with os.fdopen(fd, "wb") as f:
                        f.write(payload)
                    with CONFIG_LOCK:
                        if local_filename in self.config.card_data.excluded_datasets:
                            continue
                        os.replace(tmp_path, self._destination(local_filename))
                    local_manifest["datasets"][key] = file_info
                    updates_made = True
                except Exception as error:
                    failures += 1
                    logger.error(f"Rejected dataset {key}; kept cached data: {error}")
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        os.remove(tmp_path)

            if "active_sets" in remote_manifest:
                local_manifest["active_sets"] = remote_manifest["active_sets"]
            self.save_local_manifest(local_manifest)
            if failures:
                progress_callback(f"Skipped {failures} dataset update(s). Kept cached data.")
            elif updates_made:
                progress_callback("Datasets updated successfully.")
        except Exception as error:
            logger.error(f"Failed to sync datasets; kept cached data: {error}")
            progress_callback("Skipped dataset sync. Kept cached data.")
