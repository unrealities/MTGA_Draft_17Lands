let activityData = [];
let manifestData = [];
let activeSetsList = [];
let currentSort = { col: 'set', dir: 'asc' };
let showOnlyActive = true; // Toggle state for the Warehouse list

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', () => {
    fetchReport();
    fetchManifest();
    setupSortListeners();
    setupSearchListener();
});

function fetchReport() {
    fetch('report.json?' + new Date().getTime())
        .then(res => res.json())
        .then(data => {
            const run = data.pipeline_run || {};
            const api = data.api_stats || {};
            activityData = data.datasets_updated || [];

            document.getElementById('last-updated').innerHTML = `Last ETL Run: <span class="text-slate-300">${new Date(run.completed_at).toLocaleString()}</span>`;
            document.getElementById('duration').textContent = `${run.duration_sec}s`;
            document.getElementById('api-reqs').textContent = api.total_requests || 0;

            const statusEl = document.getElementById('status');
            statusEl.textContent = run.status || "UNKNOWN";
            if (run.status === 'SUCCESS') statusEl.className = "text-2xl font-bold text-emerald-400";
            else if (run.status === 'FAILED') statusEl.className = "text-2xl font-bold text-rose-500";
            else statusEl.className = "text-2xl font-bold text-amber-400";

            renderActivityTable();
        }).catch(e => console.error("Error loading report:", e));
}

function fetchManifest() {
    fetch('manifest.json?' + new Date().getTime())
        .then(res => res.json())
        .then(data => {
            const datasets = data.datasets || {};
            activeSetsList = data.active_sets || [];
            manifestData = Object.keys(datasets).map(k => ({ id: k, ...datasets[k] }));
            document.getElementById('total-datasets').textContent = manifestData.length;
            renderManifestList(manifestData);
        }).catch(e => console.error("Error loading manifest:", e));
}

// Visual Badges Helper
function getFormatBadge(format) {
    if (format.includes('Premier')) return `<span class="bg-blue-600/20 text-blue-400 border border-blue-500/30 px-2 py-0.5 rounded text-xs">${format}</span>`;
    if (format.includes('Quick')) return `<span class="bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded text-xs">${format}</span>`;
    if (format.includes('Trad')) return `<span class="bg-amber-600/20 text-amber-400 border border-amber-500/30 px-2 py-0.5 rounded text-xs">${format}</span>`;
    if (format.includes('Sealed')) return `<span class="bg-purple-600/20 text-purple-400 border border-purple-500/30 px-2 py-0.5 rounded text-xs">${format}</span>`;
    return `<span class="bg-slate-600/20 text-slate-400 border border-slate-500/30 px-2 py-0.5 rounded text-xs">${format}</span>`;
}

function getUserBadge(userGroup) {
    const ug = userGroup || "All";
    if (ug.toLowerCase() === 'top') return `<span class="bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 px-2 py-0.5 rounded text-xs font-semibold">Top</span>`;
    return `<span class="bg-slate-700/50 text-slate-300 border border-slate-600/50 px-2 py-0.5 rounded text-xs">${ug}</span>`;
}

function renderActivityTable() {
    const tbody = document.getElementById('activity-table');
    tbody.innerHTML = '';

    if (activityData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-slate-500">No active sets scheduled for today.</td></tr>';
        return;
    }

    activityData.forEach(u => {
        tbody.innerHTML += `
            <tr class="hover:bg-slate-700/20 transition-colors">
                <td class="p-4 font-bold text-slate-200">${u.set}</td>
                <td class="p-4">${getFormatBadge(u.format)}</td>
                <td class="p-4">${getUserBadge(u.user_group)}</td>
                <td class="p-4 text-right text-slate-300">${u.card_count}</td>
                <td class="p-4 text-right text-emerald-400/90">${u.game_count.toLocaleString()}</td>
                <td class="p-4 text-right text-slate-400">${u.size_kb}</td>
            </tr>
        `;
    });
}

function setupSortListeners() {
    document.querySelectorAll('th.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const col = th.dataset.sort;

            if (currentSort.col === col) {
                currentSort.dir = currentSort.dir === 'asc' ? 'desc' : 'asc';
            } else {
                currentSort.col = col;
                currentSort.dir = 'asc';
            }

            document.querySelectorAll('th.sortable').forEach(el => {
                el.classList.remove('asc', 'desc');
            });
            th.classList.add(currentSort.dir);

            activityData.sort((a, b) => {
                let valA = a[col];
                let valB = b[col];

                if (col === "user_group") {
                    valA = valA || "All"; valB = valB || "All";
                }

                if (typeof valA === 'string') {
                    return currentSort.dir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
                }
                return currentSort.dir === 'asc' ? valA - valB : valB - valA;
            });

            renderActivityTable();
        });
    });
}

function renderManifestList(dataArray) {
    const listEl = document.getElementById('manifest-list');
    listEl.innerHTML = '';

    // Render the Active vs Archive Toggle
    const toggleHTML = `
        <div class="flex gap-2 mb-4 px-1 sticky top-0 bg-slate-800/90 py-2 backdrop-blur-sm z-10 border-b border-slate-700/50">
            <button id="btn-active" class="flex-1 py-1.5 text-xs font-bold rounded ${showOnlyActive ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-400 hover:bg-slate-600'} transition">Active on Arena</button>
            <button id="btn-archive" class="flex-1 py-1.5 text-xs font-bold rounded ${!showOnlyActive ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-400 hover:bg-slate-600'} transition">Historical Archive</button>
        </div>
    `;
    listEl.innerHTML = toggleHTML;

    // Attach Toggle Events
    document.getElementById('btn-active').addEventListener('click', () => { showOnlyActive = true; filterAndRenderList(); });
    document.getElementById('btn-archive').addEventListener('click', () => { showOnlyActive = false; filterAndRenderList(); });

    // Filter and Render the actual list
    function filterAndRenderList() {
        const query = document.getElementById('manifest-search').value.toLowerCase();

        const filteredData = manifestData.filter(ds => {
            const setCode = ds.id.split('_')[0];
            const isActive = activeSetsList.includes(setCode);
            const matchesSearch = ds.id.toLowerCase().includes(query);

            const matchesTab = showOnlyActive ? isActive : true;
            return matchesSearch && matchesTab;
        });

        // Clear only the dataset items, leaving the toggle buttons intact
        const existingItems = listEl.querySelectorAll('.dataset-item, .no-items-msg');
        existingItems.forEach(el => el.remove());

        if (filteredData.length === 0) {
            listEl.innerHTML += '<p class="no-items-msg p-4 text-center text-slate-500 text-sm">No datasets found for this view.</p>';
            return;
        }

        filteredData.forEach(ds => {
            const formatStr = ds.id.split('_')[1] || "Format";
            const userStr = ds.id.split('_')[2] || "All";

            listEl.innerHTML += `
                <div class="dataset-item p-3 mb-2 bg-slate-800/40 rounded-lg border border-slate-700/50 hover:border-slate-500 transition-colors flex flex-col group">
                    <div class="flex justify-between items-start mb-2">
                        <div>
                            <span class="font-bold text-sm text-slate-200 block mb-1">${ds.id.split('_')[0]}</span>
                            <div class="flex gap-2">
                                ${getFormatBadge(formatStr)}
                                ${getUserBadge(userStr)}
                            </div>
                        </div>
                        <span class="text-xs text-slate-400 whitespace-nowrap">${ds.size_kb} KB</span>
                    </div>
                    <a href="${ds.filename}" download class="text-xs bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 border border-blue-500/30 rounded py-1.5 px-2 mt-2 text-center transition opacity-0 group-hover:opacity-100">
                        Download .json.gz
                    </a>
                </div>
            `;
        });
    }

    // Initial render
    filterAndRenderList();
}

function setupSearchListener() {
    const input = document.getElementById('manifest-search');
    input.addEventListener('input', () => {
        renderManifestList(manifestData); // Re-trigger the render which includes search filtering
    });
}