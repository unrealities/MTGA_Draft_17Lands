import os
import json
import gzip
import hashlib
import logging
from server import config

logger = logging.getLogger(__name__)


def ensure_output_dir():
    if not os.path.exists(config.OUTPUT_DIR):
        os.makedirs(config.OUTPUT_DIR)


def atomic_write(filepath, write_func):
    """Safely writes to a temporary file, then performs an atomic rename."""
    tmp_filepath = f"{filepath}.tmp"
    try:
        write_func(tmp_filepath)
        os.replace(tmp_filepath, filepath)  # Atomic on POSIX systems
    except BaseException as e:
        if os.path.exists(tmp_filepath):
            os.remove(tmp_filepath)
        raise


def save_dataset(set_code, draft_format, dataset) -> dict:
    ensure_output_dir()
    filename = f"{set_code}_{draft_format}.json.gz"
    filepath = os.path.join(config.OUTPUT_DIR, filename)

    json_str = json.dumps(dataset, separators=(",", ":"))

    def _write_gz(tmp_path):
        with gzip.open(tmp_path, "wt", encoding="UTF-8") as f:
            f.write(json_str)

    atomic_write(filepath, _write_gz)

    with open(filepath, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    size_kb = os.path.getsize(filepath) // 1024
    logger.info(f"Saved {filename} ({size_kb} KB)")

    return {
        "filename": filename,
        "hash": file_hash,
        "size_kb": size_kb,
    }


def save_manifest(manifest_data):
    ensure_output_dir()
    filepath = os.path.join(config.OUTPUT_DIR, "manifest.json")

    def _write_json(tmp_path):
        with open(tmp_path, "w") as f:
            json.dump(manifest_data, f, indent=2)

    atomic_write(filepath, _write_json)
    logger.info("Manifest saved successfully.")


def save_report(report_data: dict):
    ensure_output_dir()
    filepath = os.path.join(config.OUTPUT_DIR, "report.json")

    def _write_json(tmp_path):
        with open(tmp_path, "w") as f:
            json.dump(report_data, f, indent=2)

    atomic_write(filepath, _write_json)
    logger.info(f"Run report saved → {filepath}")


def load_existing_manifest() -> dict:
    filepath = os.path.join(config.OUTPUT_DIR, "manifest.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load existing manifest, creating new one: {e}")

    return {"datasets": {}}
