"""Validate the filenames and checksums shared by the publisher and client."""

import re


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or not isinstance(manifest.get("datasets"), dict):
        raise ValueError("Manifest must contain a datasets object")
    for key, info in manifest["datasets"].items():
        # A single basename only: no separators, drive letters, URL escapes or dots.
        if not isinstance(key, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9 _-]{0,180}", key
        ):
            raise ValueError("Invalid dataset key")
        if not isinstance(info, dict) or info.get("filename") != f"{key}_Data.json.gz":
            raise ValueError(f"Invalid dataset filename for {key}")
        if not isinstance(info.get("hash"), str) or not re.fullmatch(
            r"[0-9a-fA-F]{64}", info["hash"]
        ):
            raise ValueError(f"Invalid SHA-256 checksum for {key}")
    return manifest
