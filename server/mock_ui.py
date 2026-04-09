import os
import json
import gzip
import hashlib
from datetime import datetime, timezone
import http.server
import socketserver
import threading
import time

from server import config
from server.load import deploy_web_assets, ensure_output_dir

def generate_mock_data():
    """Generates fake manifest, report, and dummy .gz files for UI testing."""
    ensure_output_dir()
    
    print("🧹 Cleaning old build directory...")
    # Clean old mock files to prevent clutter
    for f in os.listdir(config.OUTPUT_DIR):
        if f.endswith(".json") or f.endswith(".gz") or f.endswith(".html") or f.endswith(".css") or f.endswith(".js"):
            os.remove(os.path.join(config.OUTPUT_DIR, f))

    print("📝 Generating mock report and manifest...")
    
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # Fake datasets to simulate a pipeline run
    mock_datasets = [
        {"set": "BLB", "format": "PremierDraft", "user_group": "All", "cards": 285, "games": 154320, "size": 1250},
        {"set": "BLB", "format": "PremierDraft", "user_group": "Top", "cards": 285, "games": 42100, "size": 1245},
        {"set": "TMT", "format": "QuickDraft", "user_group": "All", "cards": 310, "games": 89000, "size": 1420},
        {"set": "FDN", "format": "TradDraft", "user_group": "All", "cards": 290, "games": 12050, "size": 1300},
        {"set": "CUBE-POWERED", "format": "PremierDraft", "user_group": "All", "cards": 540, "games": 205000, "size": 2100},
    ]
    
    report_updated = []
    manifest_datasets = {}
    
    for ds in mock_datasets:
        filename = f"{ds['set']}_{ds['format']}_{ds['user_group']}_Data.json.gz"
        filepath = os.path.join(config.OUTPUT_DIR, filename)
        
        # Create a dummy valid gzip file so download buttons work in the UI
        dummy_content = json.dumps({"mock": True, "set": ds['set']}).encode('utf-8')
        with gzip.open(filepath, 'wb') as f:
            f.write(dummy_content)
            
        # Calculate a fake hash
        fake_hash = hashlib.sha256(dummy_content).hexdigest()
        
        # Add to Report
        report_updated.append({
            "set": ds['set'],
            "format": ds['format'],
            "user_group": ds['user_group'],
            "filename": filename,
            "size_kb": ds['size'],
            "card_count": ds['cards'],
            "start_date": "2026-01-01",
            "end_date": "2026-03-01",
            "game_count": ds['games'],
            "status": "success"
        })
        
        # Add to Manifest
        manifest_key = f"{ds['set']}_{ds['format']}_{ds['user_group']}"
        manifest_datasets[manifest_key] = {
            "filename": filename,
            "hash": fake_hash,
            "size_kb": ds['size']
        }

    # 1. Write mock report.json
    mock_report = {
        "pipeline_run": {
            "started_at": "2026-03-01T10:00:00Z",
            "completed_at": now_iso,
            "duration_sec": 145.2,
            "status": "SUCCESS"
        },
        "api_stats": {"total_requests": 142, "failed_requests": 0, "cached_requests": 25},
        "execution_summary": {
            "formats_updated": len(mock_datasets),
            "formats_skipped": 0,
            "total_output_kb": sum(d['size'] for d in mock_datasets),
            "total_cards_rated": sum(d['cards'] for d in mock_datasets),
            "total_errors": 0,
            "total_warnings": 2
        },
        "datasets_updated": report_updated,
        "datasets_skipped": [],
        "errors": [],
        "warnings": [{"message": "Mock warning 1"}, {"message": "Mock warning 2"}]
    }
    
    with open(os.path.join(config.OUTPUT_DIR, "report.json"), "w") as f:
        json.dump(mock_report, f, indent=2)
        
    # 2. Write mock manifest.json
    mock_manifest = {
        "updated_at": now_iso,
        "active_sets": list(set(d['set'] for d in mock_datasets)),
        "datasets": manifest_datasets
    }
    
    with open(os.path.join(config.OUTPUT_DIR, "manifest.json"), "w") as f:
        json.dump(mock_manifest, f, indent=2)

    print("✅ Mock data generated!")

def serve_ui():
    """Starts a local HTTP server in the build directory."""
    PORT = 8000
    
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=config.OUTPUT_DIR, **kwargs)
            
        # Suppress logging to keep the console clean
        def log_message(self, format, *args):
            pass

    # Start server in a daemon thread so it shuts down when the script exits
    httpd = socketserver.TCPServer(("", PORT), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    
    print("\n========================================================")
    print(f"🎨 UI Development Server running at: http://localhost:{PORT}")
    print("========================================================")
    print("-> Edit HTML/CSS/JS in 'server/templates/'")
    print("-> Press ENTER in this console to rebuild assets instantly.")
    print("-> Press Ctrl+C to quit.\n")

    try:
        while True:
            input()  # Wait for user to press Enter
            print("🔄 Re-deploying web assets...")
            deploy_web_assets()
            print("✅ Done! Refresh your browser.\n")
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.shutdown()

if __name__ == "__main__":
    generate_mock_data()
    deploy_web_assets()
    serve_ui()
