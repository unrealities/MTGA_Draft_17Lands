let eventsData = [];
let currentDate = new Date();

// High contrast colors for solid background bars
const formatColors = {
    'PremierDraft': 'bg-blue-600 border border-blue-400 text-white',
    'QuickDraft': 'bg-emerald-600 border border-emerald-400 text-white',
    'TradDraft': 'bg-amber-600 border border-amber-400 text-white',
    'Sealed': 'bg-purple-600 border border-purple-400 text-white',
    'TradSealed': 'bg-fuchsia-600 border border-fuchsia-400 text-white',
    'PickTwoDraft': 'bg-rose-600 border border-rose-400 text-white',
    'Default': 'bg-slate-600 border border-slate-400 text-white'
};

document.addEventListener('DOMContentLoaded', () => {
    const statusEl = document.getElementById('calendar-status');

    fetch('calendar.json?' + new Date().getTime())
        .then(res => {
            if (!res.ok) throw new Error("Failed to fetch calendar.json: HTTP " + res.status);
            return res.json();
        })
        .then(data => {
            eventsData = data.events || [];
            renderCalendar();
        })
        .catch(e => {
            console.error(e);
            if (statusEl) statusEl.innerHTML = `<span class="text-red-400 font-bold">Error loading calendar:</span><br>${e.message}`;
        });

    document.getElementById('prev-month').addEventListener('click', () => {
        currentDate.setMonth(currentDate.getMonth() - 1);
        renderCalendar();
    });

    document.getElementById('next-month').addEventListener('click', () => {
        currentDate.setMonth(currentDate.getMonth() + 1);
        renderCalendar();
    });
});

// Safely parses YYYY-MM-DD to a local Date object without timezone shift bugs
function parseDateStr(str) {
    if (!str) return new Date();
    const [y, m, d] = str.split('-').map(Number);
    return new Date(y, m - 1, d);
}

function renderCalendar() {
    try {
        const year = currentDate.getFullYear();
        const month = currentDate.getMonth();

        const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
        document.getElementById('month-label').textContent = `${monthNames[month]} ${year}`;

        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const firstDayIndex = new Date(year, month, 1).getDay();

        // Calculate total weeks (rows) needed for the grid
        const numWeeks = Math.ceil((firstDayIndex + daysInMonth) / 7);

        // Build an array of exact Dates for every cell in the grid
        const cellDates = [];
        let curDate = new Date(year, month, 1 - firstDayIndex);
        for (let i = 0; i < numWeeks * 7; i++) {
            cellDates.push(new Date(curDate));
            curDate.setDate(curDate.getDate() + 1);
        }

        const viewStart = cellDates[0];
        const viewEnd = new Date(cellDates[cellDates.length - 1]);
        viewEnd.setHours(23, 59, 59, 999);

        // 1. Flatten events into individual renderable instances
        let instances = [];
        eventsData.forEach(ev => {
            if (!ev.start_date || !ev.end_date) return; // Guard against broken json

            const start = parseDateStr(ev.start_date);
            const end = parseDateStr(ev.end_date);
            end.setHours(23, 59, 59, 999);

            const formats = ev.formats || ['Default'];
            formats.forEach(fmt => {
                instances.push({
                    set: ev.set_code || "Unknown",
                    format: fmt,
                    start: start,
                    end: end
                });
            });
        });

        // 2. Filter out events that don't overlap the currently viewed month at all
        instances = instances.filter(ins => ins.start <= viewEnd && ins.end >= viewStart);

        // 3. Sort Events per user requirements
        instances.sort((a, b) => {
            const durA = a.end.getTime() - a.start.getTime();
            const durB = b.end.getTime() - b.start.getTime();

            // Rule 1: Longer running items first
            if (durB !== durA) return durB - durA;

            // Rule 2: Closest to completion LAST (meaning End Dates furthest in the future come FIRST)
            if (b.end.getTime() !== a.end.getTime()) return b.end.getTime() - a.end.getTime();

            // Rule 3: Standard chronological tie-breaker
            return a.start.getTime() - b.start.getTime();
        });

        // 4. Assign vertical "Tracks" so overlapping events stack neatly without colliding
        const tracks = [];
        instances.forEach(ins => {
            let t = 0;
            while (true) {
                if (!tracks[t]) tracks[t] = [];

                // Check if this instance overlaps with any existing instance on this track
                const overlap = tracks[t].some(existing => {
                    return ins.start <= existing.end && ins.end >= existing.start;
                });

                if (!overlap) {
                    tracks[t].push(ins);
                    ins.track = t;
                    break;
                }
                t++;
            }
        });

        // 5. DOM Generation
        const container = document.getElementById('calendar-grid');
        if (!container) throw new Error("Could not find element #calendar-grid");

        container.innerHTML = '';

        // A. Draw Headers (Row 1)
        const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        days.forEach((d, i) => {
            const div = document.createElement('div');
            div.className = 'calendar-cell header';
            div.style.gridColumn = `${i + 1}`;
            div.textContent = d;
            container.appendChild(div);
        });

        // B. Draw Day Cells (Backgrounds)
        const today = new Date();
        cellDates.forEach((date, i) => {
            const row = Math.floor(i / 7) + 2; // +2 because Row 1 is the Header
            const col = (i % 7) + 1;

            const div = document.createElement('div');
            div.className = 'day-cell';
            if (date.getMonth() !== month) div.classList.add('inactive');

            div.style.gridRow = row;
            div.style.gridColumn = col;

            const isToday = date.getDate() === today.getDate() && date.getMonth() === today.getMonth() && date.getFullYear() === today.getFullYear();

            const num = document.createElement('div');
            num.textContent = date.getDate();
            if (isToday) {
                num.className = 'text-sm font-bold text-white bg-blue-600 rounded-full w-6 h-6 flex items-center justify-center';
            } else {
                num.className = 'text-sm font-bold text-slate-400';
            }
            div.appendChild(num);

            container.appendChild(div);
        });

        // C. Draw the Spanning Event Bars
        instances.forEach(ins => {
            // Iterate through each week to see if we need to draw a bar segment
            for (let w = 0; w < numWeeks; w++) {
                const weekStart = cellDates[w * 7];
                const weekEnd = new Date(cellDates[w * 7 + 6]);
                weekEnd.setHours(23, 59, 59, 999);

                if (ins.start <= weekEnd && ins.end >= weekStart) {
                    // Event intersects this week, calculate bounds
                    // Use Math.max/min with getTime() to be absolutely safe
                    const drawStart = new Date(Math.max(ins.start.getTime(), weekStart.getTime()));
                    const drawEnd = new Date(Math.min(ins.end.getTime(), weekEnd.getTime()));

                    const startCol = drawStart.getDay() + 1;
                    const endCol = drawEnd.getDay() + 1;
                    const span = endCol - startCol + 1;

                    const bar = document.createElement('div');
                    const styleClass = formatColors[ins.format] || formatColors['Default'];

                    // Determine rounded corners (Flat if continuing into/from another week)
                    let roundingClass = '';
                    const isStart = ins.start >= weekStart;
                    const isEnd = ins.end <= weekEnd;

                    if (isStart && isEnd) roundingClass = 'rounded-md';
                    else if (isStart) roundingClass = 'rounded-l-md border-r-0';
                    else if (isEnd) roundingClass = 'rounded-r-md border-l-0';
                    else roundingClass = 'border-l-0 border-r-0';

                    bar.className = `event-bar ${styleClass} ${roundingClass}`;
                    bar.style.gridRow = w + 2;
                    bar.style.gridColumn = `${startCol} / span ${span}`;

                    // Offset vertically based on track so they don't overlap. 
                    // 34px base margin clears the date number in the cell.
                    bar.style.marginTop = `${34 + (ins.track * 28)}px`;

                    // Only print the text if it's the very beginning of the event, or the beginning of a new week row
                    if (isStart || startCol === 1) {
                        bar.textContent = `${ins.set} ${ins.format}`;
                    }

                    // Hover text
                    bar.title = `${ins.set} ${ins.format} (${ins.start.toLocaleDateString()} to ${ins.end.toLocaleDateString()})`;

                    container.appendChild(bar);
                }
            }
        });
    } catch (err) {
        console.error("Calendar Render Error:", err);
        const statusEl = document.getElementById('calendar-status');
        if (statusEl) {
            statusEl.innerHTML = `<span class="text-red-400 font-bold">Render Error:</span><br>${err.message}`;
        }
    }
}