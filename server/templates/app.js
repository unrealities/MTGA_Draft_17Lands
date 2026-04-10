let activityData = [];
let manifestData = [];
let activeSetsList = [];
let currentSort = { col: 'set', dir: 'asc' };
let showOnlyActive = true; // Toggle state for the Warehouse list

document.addEventListener('DOMContentLoaded', () => {
    // 1. Data Warehouse Dashboard Logic
    if (document.getElementById('activity-table')) {
        fetchReport();
        fetchManifest();
        setupSortListeners();
        setupSearchListener();
    }

    // 2. Landing Page Version Badge Logic
    const latestVersionEl = document.getElementById('latest-version');
    if (latestVersionEl) {
        fetch('https://api.github.com/repos/unrealities/MTGA_Draft_17Lands/releases/latest')
            .then(res => res.json())
            .then(data => {
                if (data.tag_name) {
                    latestVersionEl.textContent = formatVersion(data.tag_name);
                } else {
                    latestVersionEl.textContent = 'View Releases';
                }
            }).catch(e => {
                console.error("Failed to fetch latest version:", e);
                latestVersionEl.textContent = 'View Releases';
            });
    }

    // 3. Past Releases Page Logic
    const releasesListEl = document.getElementById('releases-list');
    if (releasesListEl) {
        fetch('https://api.github.com/repos/unrealities/MTGA_Draft_17Lands/releases')
            .then(res => res.json())
            .then(data => {
                releasesListEl.innerHTML = '';
                if (!Array.isArray(data)) {
                    releasesListEl.innerHTML = '<p class="text-rose-400 p-8 text-center bg-slate-800/50 rounded-xl border border-slate-700">Failed to load releases (API Rate Limit exceeded). Please check GitHub directly.</p>';
                    return;
                }

                data.forEach((rel, i) => {
                    const dateStr = new Date(rel.published_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
                    const ver = formatVersion(rel.tag_name);
                    const bodyHtml = formatMarkdown(rel.body);
                    const assetsHtml = renderAssets(rel.assets);

                    if (i === 0) {
                        // Latest Release (Fully Expanded)
                        releasesListEl.innerHTML += `
                            <div class="bg-slate-800/40 rounded-xl p-6 border border-slate-700/50 mb-10 shadow-lg relative overflow-hidden">
                                <div class="absolute top-0 left-0 w-1 h-full bg-emerald-500"></div>
                                <div class="flex flex-col md:flex-row md:items-center justify-between mb-4 border-b border-slate-700/50 pb-4">
                                    <div>
                                        <div class="flex items-center gap-2 mb-2">
                                            <span class="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest">Latest Release</span>
                                        </div>
                                        <h2 class="text-2xl font-bold text-white flex items-center gap-3">
                                            ${rel.name} <span class="bg-blue-600/20 text-blue-400 border border-blue-500/30 px-2 py-0.5 rounded text-xs font-mono">${ver}</span>
                                        </h2>
                                        <p class="text-slate-400 text-sm mt-1">Published on ${dateStr}</p>
                                    </div>
                                    <a href="${rel.html_url}" target="_blank" class="mt-4 md:mt-0 text-sm bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg transition text-center border border-slate-600 shadow-sm">View on GitHub</a>
                                </div>
                                <div class="text-slate-300 text-sm leading-relaxed font-sans">${bodyHtml}</div>
                                
                                <div class="mt-6 pt-4 border-t border-slate-700/30 flex flex-wrap gap-3">
                                    ${assetsHtml}
                                </div>
                            </div>
                            
                            <h2 class="text-xl font-bold text-slate-200 mb-4 mt-4 border-b border-slate-800 pb-2">Previous Releases</h2>
                        `;
                    } else {
                        // Older Releases (Collapsed Accordion)
                        releasesListEl.innerHTML += `
                            <details class="group bg-slate-800/30 border border-slate-700/50 rounded-lg mb-3 transition-colors open:bg-slate-800/60 shadow-sm">
                                <summary class="flex justify-between items-center font-bold cursor-pointer list-none p-4 select-none">
                                    <div class="flex flex-col md:flex-row md:items-center gap-2 md:gap-4">
                                        <span class="text-lg text-slate-300 group-hover:text-white transition-colors">${rel.name}</span>
                                        <div class="flex items-center gap-3">
                                            <span class="bg-slate-700 text-slate-300 border border-slate-600 px-2 py-0.5 rounded text-xs font-mono">${ver}</span>
                                            <span class="text-slate-500 text-sm font-normal hidden sm:block">• ${dateStr}</span>
                                        </div>
                                    </div>
                                    <span class="text-slate-500 transition-transform group-open:rotate-180">▼</span>
                                </summary>
                                <div class="p-4 pt-2 border-t border-slate-700/50 mt-1">
                                    <div class="text-slate-300 text-sm leading-relaxed font-sans mb-5">${bodyHtml}</div>
                                    <div class="pt-4 border-t border-slate-700/30 flex flex-wrap gap-3">
                                        ${assetsHtml}
                                    </div>
                                </div>
                            </details>
                        `;
                    }
                });
            }).catch(e => {
                releasesListEl.innerHTML = '<p class="text-rose-400 p-8 text-center bg-slate-800/50 rounded-xl border border-slate-700">Failed to load releases. Please check GitHub directly.</p>';
            });
    }
});

// Helper: Converts MTGA_Draft_Tool_V0413 into v4.13
function formatVersion(tag) {
    if (!tag) return '';
    const match = tag.match(/V0?(\d+)(\d\d)/);
    if (match) {
        let decimals = match[2];
        if (decimals.endsWith('0')) decimals = decimals.substring(0, 1);
        return `v${match[1]}.${decimals}`;
    }
    return tag;
}

// Helper: Lightweight Markdown Parser for Release Notes
function formatMarkdown(text) {
    if (!text) return '';
    let html = text;

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h3 class="text-lg font-bold text-slate-200 mt-4 mb-2">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 class="text-xl font-bold text-white mt-6 mb-3 border-b border-slate-700/50 pb-2">$1</h2>');

    // Bold / Italic
    html = html.replace(/\*\*(.*?)\*\*/gim, '<strong class="text-slate-200">$1</strong>');
    html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');

    // Inline Code
    html = html.replace(/`(.*?)`/gim, '<code class="bg-slate-900 text-emerald-400 px-1.5 py-0.5 rounded text-xs border border-slate-700">$1</code>');

    // Links
    html = html.replace(/\[(.*?)\]\((.*?)\)/gim, '<a href="$2" target="_blank" class="text-blue-400 hover:underline">$1</a>');

    // Lists
    html = html.replace(/^\* (.*$)/gim, '<li class="ml-5 list-disc marker:text-blue-500 mb-1">$1</li>');
    html = html.replace(/^- (.*$)/gim, '<li class="ml-5 list-disc marker:text-blue-500 mb-1">$1</li>');

    // Line breaks
    html = html.replace(/\n/gim, '<br>');

    // Cleanup list breaks
    html = html.replace(/(<\/li>)<br>/gim, '$1');

    return html;
}

// Helper: Render Download Buttons for Assets
function renderAssets(assets) {
    if (!assets || assets.length === 0) return '';
    let html = '';
    assets.forEach(asset => {
        let icon = '📦';
        let colorClass = 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700';

        if (asset.name.endsWith('.exe')) { icon = '🪟'; colorClass = 'bg-blue-900/20 text-blue-400 border-blue-800/50 hover:bg-blue-900/40'; }
        else if (asset.name.endsWith('.zip')) { icon = '🍎'; colorClass = 'bg-slate-700/50 text-slate-200 border-slate-600 hover:bg-slate-700'; }
        else if (asset.name.endsWith('.tar.gz')) { icon = '🐧'; colorClass = 'bg-amber-900/20 text-amber-500 border-amber-800/50 hover:bg-amber-900/40'; }
        else if (asset.name.endsWith('.txt')) { icon = '📄'; colorClass = 'bg-slate-800 text-slate-400 border-slate-700 hover:bg-slate-700'; }

        const sizeMb = (asset.size / (1024 * 1024)).toFixed(1);

        html += `
            <a href="${asset.browser_download_url}" class="flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs transition-colors ${colorClass}">
                <span>${icon}</span>
                <span class="font-medium truncate max-w-[150px]" title="${asset.name}">${asset.name}</span>
                <span class="opacity-60 text-[10px] ml-1">${sizeMb}MB</span>
            </a>
        `;
    });
    return html;
}

function fetchReport() {
    fetch('report.json?' + new Date().getTime())
        .then(res => res.json())
        .then(data => {
            const run = data.pipeline_run || {};
            const api = data.api_stats || {};
            activityData = data.datasets_updated || [];

            let dur = run.duration_sec || 0;
            let mins = Math.floor(dur / 60);
            let secs = Math.floor(dur % 60);
            let durStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;

            document.getElementById('last-updated').innerHTML = `Last ETL Run: <span class="text-slate-300">${new Date(run.completed_at).toLocaleString()}</span>`;
            document.getElementById('duration').textContent = durStr;
            document.getElementById('api-reqs').textContent = api.total_requests || 0;

            const statusEl = document.getElementById('status');
            statusEl.textContent = run.status || "UNKNOWN";
            if (run.status === 'SUCCESS') statusEl.className = "text-2xl font-bold text-emerald-400";
            else if (run.status === 'FAILED') statusEl.className = "text-2xl font-bold text-rose-500";
            else statusEl.className = "text-2xl font-bold text-amber-400";

            applySort();
        }).catch(e => console.error("Error loading report:", e));
}

function applySort() {
    activityData.sort((a, b) => {
        let valA = a[currentSort.col];
        let valB = b[currentSort.col];

        if (currentSort.col === "user_group") {
            valA = valA || "All"; valB = valB || "All";
        }

        if (typeof valA === 'string') {
            return currentSort.dir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
        }
        return currentSort.dir === 'asc' ? valA - valB : valB - valA;
    });

    // Keep table headers in sync visually
    document.querySelectorAll('th.sortable').forEach(el => {
        el.classList.remove('asc', 'desc');
        if (el.dataset.sort === currentSort.col) {
            el.classList.add(currentSort.dir);
        }
    });

    renderActivityTable();
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
                <td class="p-4 text-slate-400 text-sm whitespace-nowrap">${u.start_date || '?'} <span class="text-slate-600 px-1">→</span> ${u.end_date || '?'}</td>
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

            applySort();
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

            const dateStr = (ds.start_date && ds.end_date)
                ? `<div class="text-xs text-slate-500 mt-2 font-mono flex items-center gap-1"><svg class="w-3 h-3 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg> ${ds.start_date} <span class="text-slate-600">→</span> ${ds.end_date}</div>`
                : '';

            listEl.innerHTML += `
                <div class="dataset-item p-3 mb-2 bg-slate-800/40 rounded-lg border border-slate-700/50 hover:border-slate-500 transition-colors flex flex-col group">
                    <div class="flex justify-between items-start mb-2">
                        <div>
                            <span class="font-bold text-sm text-slate-200 block mb-1">${ds.id.split('_')[0]}</span>
                            <div class="flex gap-2">
                                ${getFormatBadge(formatStr)}
                                ${getUserBadge(userStr)}
                            </div>
                            ${dateStr}
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