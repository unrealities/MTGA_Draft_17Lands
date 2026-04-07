import os
import json
import gzip
import requests
import logging
from src import constants
from src.configuration import write_configuration

logger = logging.getLogger(__name__)


class DatasetUpdater:
    def __init__(self, config):
        self.config = config
        self.local_manifest_path = os.path.join(
            constants.SETS_FOLDER, "local_manifest.json"
        )

    def get_local_manifest(self):
        if os.path.exists(self.local_manifest_path):
            try:
                with open(self.local_manifest_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"datasets": {}}

    def save_local_manifest(self, manifest_data):
        with open(self.local_manifest_path, "w") as f:
            json.dump(manifest_data, f)

    def sync_datasets(self, progress_callback):
        """Fetches remote manifest and downloads missing/updated sets."""
        try:
            progress_callback("Checking for official dataset updates...")
            resp = requests.get(constants.REMOTE_MANIFEST_URL, timeout=5)
            resp.raise_for_status()
            remote_manifest = resp.json()

            local_manifest = self.get_local_manifest()

            if "active_sets" in remote_manifest:
                local_manifest["active_sets"] = remote_manifest["active_sets"]

            remote_datasets = remote_manifest.get("datasets", {})
            updates_made = False

            for key, file_info in remote_datasets.items():
                remote_hash = file_info.get("hash")
                remote_filename = file_info.get("filename")

                local_filename = remote_filename.replace(".gz", "")
                local_filepath = os.path.join(constants.SETS_FOLDER, local_filename)

                local_hash = local_manifest.get("datasets", {}).get(key, {}).get("hash")
                file_missing = not os.path.exists(local_filepath)

                if file_missing or local_hash != remote_hash:
                    progress_callback(f"Downloading {key}...")

                    file_url = constants.REMOTE_DATASET_BASE_URL + remote_filename
                    gz_resp = requests.get(file_url, timeout=15)
                    gz_resp.raise_for_status()

                    import gzip

                    json_data = gzip.decompress(gz_resp.content)

                    tmp_path = local_filepath + ".tmp"
                    with open(tmp_path, "wb") as f:
                        f.write(json_data)
                    os.replace(tmp_path, local_filepath)

                    if "datasets" not in local_manifest:
                        local_manifest["datasets"] = {}
                    local_manifest["datasets"][key] = file_info
                    updates_made = True

            self.save_local_manifest(local_manifest)

            if updates_made:
                progress_callback("Datasets updated successfully.")

        except Exception as e:
            logger.error(f"Failed to sync datasets: {e}")
            progress_callback("Skipped dataset sync (Network Error).")
