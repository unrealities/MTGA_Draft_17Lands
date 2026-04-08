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
        os.replace(tmp_filepath, filepath)
    except BaseException as e:
        if os.path.exists(tmp_filepath):
            os.remove(tmp_filepath)
        raise


def save_dataset(set_code, draft_format, user_group, dataset) -> dict:
    ensure_output_dir()
    filename = f"{set_code}_{draft_format}_{user_group}_Data.json.gz"
    filepath = os.path.join(config.OUTPUT_DIR, filename)

    json_str = json.dumps(dataset, separators=(",", ":"))

    internal_name = filename.replace(".gz", "")

    def _write_gz(tmp_path):
        with open(tmp_path, "wb") as f_out:
            with gzip.GzipFile(filename=internal_name, mode="wb", fileobj=f_out) as gz:
                gz.write(json_str.encode("utf-8"))

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


def save_index_html():
    """Generates a static HTML dashboard to be served by GitHub Pages."""
    ensure_output_dir()
    filepath = os.path.join(config.OUTPUT_DIR, "index.html")

    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MTGA Draft Tool - Dataset Warehouse</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        .hash-cell { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
    </style>
</head>
<body class="bg-slate-900 text-slate-300 min-h-screen p-4 md:p-8">
    <div class="max-w-6xl mx-auto">
        <!-- Header -->
        <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 pb-6 border-b border-slate-800">
            <div>
                <h1 class="text-3xl font-bold text-slate-100 mb-2">📦 MTGA Dataset Warehouse</h1>
                <p class="text-slate-400 text-sm" id="last-updated">Checking last update time...</p>
            </div>
            <a href="https://github.com/unrealities/MTGA_Draft_17Lands" target="_blank" class="mt-4 md:mt-0 text-sm bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2 rounded-lg border border-slate-700 transition">
                View GitHub Repository
            </a>
        </div>

        <!-- KPI Cards -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8" id="kpi-grid">
            <div class="bg-slate-800/50 p-5 rounded-xl border border-slate-700/50">
                <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Pipeline Status</h3>
                <p class="text-2xl font-bold" id="status">Loading...</p>
            </div>
            <div class="bg-slate-800/50 p-5 rounded-xl border border-slate-700/50">
                <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Duration</h3>
                <p class="text-2xl font-bold text-slate-200" id="duration">--</p>
            </div>
            <div class="bg-slate-800/50 p-5 rounded-xl border border-slate-700/50">
                <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Total Datasets</h3>
                <p class="text-2xl font-bold text-slate-200" id="total-datasets">--</p>
            </div>
            <div class="bg-slate-800/50 p-5 rounded-xl border border-slate-700/50">
                <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">API Requests</h3>
                <p class="text-2xl font-bold text-slate-200" id="api-reqs">--</p>
            </div>
        </div>

        <!-- Data Tables -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            <!-- Left Col: Today's Activity -->
            <div class="lg:col-span-2">
                <h2 class="text-xl font-bold text-slate-200 mb-4">Today's Pipeline Activity</h2>
                <div class="overflow-x-auto bg-slate-800/30 rounded-xl border border-slate-700/50">
                    <table class="w-full text-left text-sm">
                        <thead class="bg-slate-800/50 text-slate-400">
                            <tr>
                                <th class="p-4 font-semibold">Set / Format</th>
                                <th class="p-4 font-semibold text-right">Cards</th>
                                <th class="p-4 font-semibold text-right">Games</th>
                                <th class="p-4 font-semibold text-right">Size</th>
                            </tr>
                        </thead>
                        <tbody id="activity-table" class="divide-y divide-slate-700/50">
                            <tr><td colspan="4" class="p-4 text-center text-slate-500">Loading data...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Right Col: Full Warehouse Manifest -->
            <div>
                <h2 class="text-xl font-bold text-slate-200 mb-4">Available Downloads</h2>
                <div class="bg-slate-800/30 rounded-xl border border-slate-700/50 overflow-hidden">
                    <div class="max-h-[500px] overflow-y-auto p-2" id="manifest-list">
                        <p class="p-4 text-center text-slate-500 text-sm">Loading manifest...</p>
                    </div>
                </div>
            </div>

        </div>
    </div>

    <script>
        // Fetch Report (Today's run details)
        fetch('report.json?' + new Date().getTime())
            .then(res => res.json())
            .then(data => {
                const run = data.pipeline_run || {};
                const summary = data.execution_summary || {};
                const api = data.api_stats || {};
                const updates = data.datasets_updated || [];

                document.getElementById('last-updated').innerHTML = `Last ETL Run: <span class="text-slate-300">${new Date(run.completed_at).toLocaleString()}</span>`;
                document.getElementById('duration').textContent = `${run.duration_sec}s`;
                document.getElementById('api-reqs').textContent = api.total_requests || 0;

                const statusEl = document.getElementById('status');
                statusEl.textContent = run.status || "UNKNOWN";
                if (run.status === 'SUCCESS') statusEl.className = "text-2xl font-bold text-emerald-400";
                else if (run.status === 'FAILED') statusEl.className = "text-2xl font-bold text-rose-500";
                else statusEl.className = "text-2xl font-bold text-amber-400";

                const tbody = document.getElementById('activity-table');
                tbody.innerHTML = '';
                
                if (updates.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-slate-500">No active sets scheduled for today.</td></tr>';
                } else {
                    updates.sort((a, b) => a.set.localeCompare(b.set) || a.format.localeCompare(b.format));
                    updates.forEach(u => {
                        tbody.innerHTML += `
                            <tr class="hover:bg-slate-700/20 transition-colors">
                                <td class="p-4">
                                    <div class="font-bold text-blue-400">${u.set}</div>
                                    <div class="text-xs text-slate-500">${u.format}</div>
                                </td>
                                <td class="p-4 text-right">${u.card_count}</td>
                                <td class="p-4 text-right text-emerald-400/90">${u.game_count.toLocaleString()}</td>
                                <td class="p-4 text-right text-slate-400">${u.size_kb} KB</td>
                            </tr>
                        `;
                    });
                }
            }).catch(e => console.error("Error loading report:", e));

        // Fetch Manifest (All files currently hosted)
        fetch('manifest.json?' + new Date().getTime())
            .then(res => res.json())
            .then(data => {
                const datasets = data.datasets || {};
                const keys = Object.keys(datasets).sort();
                
                document.getElementById('total-datasets').textContent = keys.length;
                
                const listEl = document.getElementById('manifest-list');
                listEl.innerHTML = '';

                keys.forEach(k => {
                    const ds = datasets[k];
                    listEl.innerHTML += `
                        <div class="p-3 mb-2 bg-slate-800/50 rounded-lg border border-slate-700/50 hover:border-slate-600 transition-colors">
                            <div class="flex justify-between items-center mb-1">
                                <span class="font-semibold text-sm text-slate-200">${k}</span>
                                <span class="text-xs text-slate-400">${ds.size_kb} KB</span>
                            </div>
                            <div class="text-[10px] text-slate-500 hash-cell truncate" title="${ds.hash}">
                                SHA-256: ${ds.hash.substring(0, 16)}...
                            </div>
                        </div>
                    `;
                });
            }).catch(e => console.error("Error loading manifest:", e));
    </script>
</body>
</html>"""

    def _write_html(tmp_path):
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    atomic_write(filepath, _write_html)
    logger.info("Index HTML generated successfully.")
