const terminal = document.getElementById('terminal');
const statusBadge = document.getElementById('global-status');
const stopBtn = document.getElementById('stop-btn');
let pollInterval = null;
let lastLogCount = 0;

function updateStatusUI(status, task) {
    statusBadge.className = 'status-badge';
    if (status === 'running') {
        statusBadge.classList.add('status-running');
        statusBadge.textContent = `RUNNING: ${task}`;
        disableButtons(true);
    } else if (status === 'success') {
        statusBadge.classList.add('status-success');
        statusBadge.textContent = 'SUCCESS';
        disableButtons(false);
        refreshImages();
        fetchMetrics();
    } else if (status === 'error') {
        statusBadge.classList.add('status-error');
        statusBadge.textContent = 'ERROR';
        disableButtons(false);
    } else {
        statusBadge.classList.add('status-idle');
        statusBadge.textContent = 'IDLE';
        disableButtons(false);
        fetchMetrics();
    }
}

function fetchMetrics() {
    fetch('/api/metrics')
        .then(res => {
            if (!res.ok) throw new Error("No metrics yet");
            return res.json();
        })
        .then(data => {
            document.getElementById('metrics-container').style.display = 'block';
            const tbody = document.getElementById('metrics-table-body');
            tbody.innerHTML = `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.1); background: rgba(0,0,0,0.2);">
                    <td colspan="4" style="padding: 0.5rem; color: #94A3B8; font-weight: 600; letter-spacing: 0.5px;">PHYSICAL PARAMETERS</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td style="padding: 0.5rem; color: var(--text-muted);">Thickness (Max)</td>
                    <td style="padding: 0.5rem; font-weight: bold; color: white;">${(data.thickness * 100).toFixed(2)}%</td>
                    <td style="padding: 0.5rem; color: var(--text-muted);">Thickness Loc.</td>
                    <td style="padding: 0.5rem; font-weight: bold; color: white;">${(data.thickness_loc * 100).toFixed(2)}%</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td style="padding: 0.5rem; color: var(--text-muted);">Camber (Max)</td>
                    <td style="padding: 0.5rem; font-weight: bold; color: white;">${(data.camber * 100).toFixed(2)}%</td>
                    <td style="padding: 0.5rem; color: var(--text-muted);">Camber Loc.</td>
                    <td style="padding: 0.5rem; font-weight: bold; color: white;">${(data.camber_loc * 100).toFixed(2)}%</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                    <td style="padding: 0.5rem; color: var(--text-muted);">LE Radius</td>
                    <td style="padding: 0.5rem; font-weight: bold; color: white;">${data.le_radius.toFixed(4)}</td>
                    <td style="padding: 0.5rem; color: var(--text-muted);">TE Angle</td>
                    <td style="padding: 0.5rem; font-weight: bold; color: white;">${data.te_angle.toFixed(2)}°</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.1); background: rgba(0,0,0,0.2);">
                    <td colspan="4" style="padding: 0.5rem; color: #94A3B8; font-weight: 600; letter-spacing: 0.5px;">AERODYNAMIC PERFORMANCE</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td style="padding: 0.5rem; color: var(--text-muted);">Peak L/D (3D)</td>
                    <td style="padding: 0.5rem; font-weight: bold; color: #10B981;">${data.peak_ld.toFixed(2)} <span style="font-size: 0.8em; font-weight: normal; color: gray;">(@ ${data.peak_aoa.toFixed(1)}°)</span></td>
                    <td style="padding: 0.5rem; color: var(--text-muted);">Peak L/D (2D)</td>
                    <td style="padding: 0.5rem; font-weight: bold; color: white;">${data.peak_ld_2d.toFixed(2)} <span style="font-size: 0.8em; font-weight: normal; color: gray;">(@ ${data.aoa_2d.toFixed(1)}°)</span></td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td style="padding: 0.5rem; color: var(--text-muted);">L/D @ 5° (3D)</td>
                    <td style="padding: 0.5rem; font-weight: bold; color: white;">${data.ld_5deg.toFixed(2)}</td>
                    <td style="padding: 0.5rem; color: var(--text-muted);">L/D @ 5° (2D)</td>
                    <td style="padding: 0.5rem; font-weight: bold; color: white;">${data.ld_5deg_2d.toFixed(2)}</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                    <td style="padding: 0.5rem; color: var(--text-muted);">Cl @ 5°</td>
                    <td style="padding: 0.5rem; font-weight: bold; color: white;">${data.cl_5deg.toFixed(4)}</td>
                    <td style="padding: 0.5rem; color: var(--text-muted);">Cd @ 5° (3D)</td>
                    <td style="padding: 0.5rem; font-weight: bold; color: white;">${data.cd_5deg_3d.toFixed(4)}</td>
                </tr>
            `;
        })
        .catch(err => {
            document.getElementById('metrics-container').style.display = 'none';
        });
}

function disableButtons(disable) {
    document.querySelectorAll('.button:not(#stop-btn)').forEach(btn => {
        btn.disabled = disable;
    });
    stopBtn.disabled = !disable;
}

function appendLog(line) {
    const p = document.createElement('p');
    p.textContent = `> ${line}`;
    terminal.appendChild(p);
}

function pollStatus() {
    fetch('/api/status')
        .then(res => res.json())
        .then(data => {
            if (data.status === 'running' || data.logs.length > 0) {
                const isScrolledToBottom = terminal.scrollHeight - terminal.clientHeight <= terminal.scrollTop + 50;
                
                terminal.innerHTML = ''; // Clear terminal
                data.logs.forEach(log => {
                    appendLog(log);
                });
                
                if (isScrolledToBottom) {
                    terminal.scrollTop = terminal.scrollHeight;
                }
            }
            
            // Call updateStatusUI AFTER processing logs so it can override the progress bar display to 'none'
            updateStatusUI(data.status, data.task);
            
            if (data.status !== 'running' && data.status !== 'idle') {
                clearInterval(pollInterval);
                pollInterval = null;
            }
        })
        .catch(err => console.error(err));
}

function runScript(scriptId) {
    appendLog(`Initializing ${scriptId}...`);
    
    let options = { method: 'POST' };
    
    const formData = new FormData();
    formData.append('mach', document.getElementById('mach').value);
    formData.append('reynolds', document.getElementById('reynolds').value);
    formData.append('ar', document.getElementById('ar').value);
    formData.append('oswald', document.getElementById('oswald').value);
    
    if (scriptId === 'generate') {
        const zipFile = document.getElementById('zip-file').files[0];
        if (zipFile) {
            formData.append('zip_file', zipFile);
        }
    }
    
    options.body = formData;
    
    fetch(`/api/run/${scriptId}`, options)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                appendLog(`Error: ${data.error}`);
            } else {
                updateStatusUI('running', scriptId);
                terminal.innerHTML = ''; // Clear terminal for new run
                lastLogCount = 0;
                if (!pollInterval) {
                    pollInterval = setInterval(pollStatus, 1000);
                }
            }
        })
        .catch(err => {
            appendLog(`Network Error: ${err}`);
        });
}

function stopScript() {
    appendLog("Sending stop signal...");
    fetch('/api/stop', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.error) appendLog(`Stop Error: ${data.error}`);
        })
        .catch(err => appendLog(`Network Error: ${err}`));
}

function dumpData() {
    if (!confirm("Are you sure you want to delete all optimization trials and models? This will keep only the master dataset.")) {
        return;
    }
    appendLog("Dumping previous iterations and models...");
    fetch('/api/dump', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                appendLog(`Dump Error: ${data.error}`);
            } else {
                appendLog(`Success: ${data.message}`);
                // Clear UI metrics
                document.getElementById('metrics-container').style.display = 'none';
                document.getElementById('plot-optimized').src = '';
                refreshImages();
            }
        })
        .catch(err => appendLog(`Network Error: ${err}`));
}

function refreshImages() {
    // Append timestamp to force browser cache refresh
    const timestamp = new Date().getTime();
    document.querySelectorAll('.plot-img').forEach(img => {
        const baseUrl = img.src.split('?')[0];
        img.src = `${baseUrl}?t=${timestamp}`;
        img.style.display = 'block';
    });
}

// Initial status check
fetch('/api/status')
    .then(res => res.json())
    .then(data => {
        if (data.status === 'running') {
            pollInterval = setInterval(pollStatus, 1000);
        }
    });
