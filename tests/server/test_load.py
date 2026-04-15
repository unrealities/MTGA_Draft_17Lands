import pytest
import os
import json
import gzip
from unittest.mock import patch
from server.load import save_dataset, save_manifest, atomic_write


@pytest.fixture
def output_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("server.config.OUTPUT_DIR", str(tmp_path))
    return tmp_path


def test_atomic_write(output_dir):
    filepath = str(output_dir / "atomic_test.txt")

    def writer(tmp_path):
        with open(tmp_path, "w") as f:
            f.write("Safe Content")

    atomic_write(filepath, writer)

    assert os.path.exists(filepath)
    assert not os.path.exists(f"{filepath}.tmp")
    with open(filepath, "r") as f:
        assert f.read() == "Safe Content"


def test_save_dataset_compresses_and_hashes(output_dir):
    mock_dataset = {"card_ratings": {"123": {"name": "Bolt", "data": "X" * 5000}}}

    result = save_dataset("M10", "PremierDraft", "All", mock_dataset)

    expected_filename = "M10_PremierDraft_All_Data.json.gz"
    filepath = output_dir / expected_filename

    assert result["filename"] == expected_filename
    assert "hash" in result
    assert (
        result["size_kb"] >= 0
    )  # GZIP compresses repetitive text heavily, so it will be < 1KB
    assert filepath.exists()

    # Verify decompression yields the exact original data
    with gzip.open(filepath, "rb") as f:
        loaded_data = json.loads(f.read().decode("utf-8"))
        assert loaded_data["card_ratings"]["123"]["name"] == "Bolt"


def test_save_manifest(output_dir):
    mock_manifest = {"active_sets": ["M10"]}
    save_manifest(mock_manifest)

    filepath = output_dir / "manifest.json"
    assert filepath.exists()
    with open(filepath, "r") as f:
        assert json.load(f)["active_sets"] == ["M10"]
