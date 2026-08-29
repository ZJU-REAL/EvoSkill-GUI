"""CSS styles for the eval server dashboard."""

EVAL_SERVER_CSS = """
:root {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --bg-tertiary: #21262d;
    --text-primary: #c9d1d9;
    --text-secondary: #8b949e;
    --accent-color: #58a6ff;
    --success-color: #3fb950;
    --warning-color: #d29922;
    --danger-color: #f85149;
    --border-color: #30363d;
    --shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
    height: 100%;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background-color: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.5;
}

.container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
    min-height: 100vh;
}

/* Header */
.app-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 24px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 24px;
    border-radius: 8px;
}

.app-header h1 {
    font-size: 20px;
    font-weight: 600;
}

/* Filter bar */
.filter-bar {
    display: flex;
    gap: 12px;
    align-items: flex-end;
    padding: 12px 16px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    margin-bottom: 16px;
    flex-wrap: wrap;
}
.filter-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 140px;
}
.filter-label {
    font-size: 11px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.filter-bar select,
.filter-bar input {
    padding: 6px 10px;
    background: var(--bg-tertiary);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 13px;
    outline: none;
}
.filter-bar select:focus,
.filter-bar input:focus {
    border-color: var(--accent-color);
}

/* Stats cards row */
.stats-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
    margin-bottom: 24px;
}

.stat-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 14px;
    text-align: center;
}

.stat-card .stat-value {
    font-size: 24px;
    font-weight: 700;
    color: var(--accent-color);
}

.stat-card .stat-label {
    font-size: 11px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 4px;
}

/* Docker container popover */
.stat-card-popover {
    cursor: help;
    position: relative;
}

.stat-card-popover .popover-body {
    display: none;
    position: absolute;
    left: 0;
    top: 100%;
    margin-top: 4px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    z-index: 100;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    min-width: 420px;
    max-height: 360px;
    overflow-y: auto;
}

.stat-card-popover:hover .popover-body {
    display: block;
}

.popover-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
}

.popover-table th {
    background: var(--bg-tertiary);
    padding: 6px 10px;
    text-align: left;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-secondary);
    position: sticky;
    top: 0;
}

.popover-table td {
    padding: 4px 10px;
    border-bottom: 1px solid var(--border-color);
    white-space: nowrap;
}

.popover-name {
    font-family: 'SF Mono', 'Fira Code', monospace;
    color: var(--accent-color);
}

.popover-status { color: var(--success-color); }
.popover-image { color: var(--text-secondary); }

/* Status badges */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
}
.badge-queued { background: #30363d; color: #8b949e; }
.badge-running { background: #0d419d; color: #58a6ff; }
.badge-completed { background: #0f5323; color: #3fb950; }
.badge-failed { background: #67060c; color: #f85149; }
.badge-cancelled { background: #3d2e00; color: #d29922; }

/* Score breakdown tags */
.score-breakdown {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
}
.score-tag {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
    white-space: nowrap;
}
.score-overall { background: #0f5323; color: #3fb950; }
.score-std { background: #1a3a5c; color: #79c0ff; }
.score-mcp { background: #3d2e00; color: #d29922; }
.score-ui { background: #2d1b4e; color: #bc8cff; }

/* Job table */
.job-table {
    width: 100%;
    border-collapse: collapse;
    background: var(--bg-secondary);
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--border-color);
}

.job-table th {
    background: var(--bg-tertiary);
    padding: 12px 16px;
    text-align: left;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-secondary);
    border-bottom: 1px solid var(--border-color);
}

.job-table td {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
    font-size: 14px;
}

.job-table tr:hover {
    background: var(--bg-tertiary);
}

.job-table tr:last-child td {
    border-bottom: none;
}

/* Modal */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.modal-content {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 24px;
    width: 90%;
    max-width: 680px;
    max-height: 90vh;
    overflow-y: auto;
}

.modal-close {
    background: none;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-secondary);
    font-size: 16px;
    cursor: pointer;
    padding: 4px 10px;
    line-height: 1;
}
.modal-close:hover {
    color: var(--text-primary);
    border-color: var(--text-secondary);
}

/* Forms */
.form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}

.form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.form-group.full-width {
    grid-column: 1 / -1;
}

.form-group label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
}

.form-group input,
.form-group select {
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 8px 12px;
    color: var(--text-primary);
    font-size: 14px;
}

.form-group input:focus,
.form-group select:focus {
    outline: none;
    border-color: var(--accent-color);
    box-shadow: 0 0 0 2px rgba(88, 166, 255, 0.2);
}

/* Buttons */
.btn {
    padding: 8px 20px;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: opacity 0.2s;
}

.btn:hover { opacity: 0.85; }

.btn-primary {
    background: var(--accent-color);
    color: #fff;
}

.btn-danger {
    background: var(--danger-color);
    color: #fff;
}

.btn-sm {
    padding: 4px 12px;
    font-size: 12px;
}

.btn-disabled {
    opacity: 0.5;
    cursor: default;
    pointer-events: none;
}

/* Job detail */
.detail-header {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 24px;
}

.detail-meta {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 0;
    margin-top: 16px;
}

.meta-item {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 10px 16px;
    border-bottom: 1px solid var(--border-color);
    gap: 12px;
}

.meta-label {
    font-size: 12px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    flex-shrink: 0;
}

.meta-value {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
    text-align: right;
    word-break: break-all;
}

/* Log output */
.log-output {
    background: #010409;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 16px;
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 500px;
    overflow-y: auto;
    color: var(--text-primary);
}

/* Checkbox as toggle */
.toggle-label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    font-size: 14px;
}

.toggle-label input[type="checkbox"] {
    width: 16px;
    height: 16px;
    accent-color: var(--accent-color);
}

/* Responsive */
@media (max-width: 768px) {
    .form-grid { grid-template-columns: 1fr; }
    .stats-row { grid-template-columns: 1fr 1fr; }
}

/* Links */
a {
    color: var(--accent-color);
    text-decoration: none;
}
a:hover {
    text-decoration: underline;
}

/* Flash messages */
.flash-error {
    background: #67060c;
    color: #f85149;
    border: 1px solid #da3633;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 16px;
}

/* Action buttons row */
.actions-row {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 24px;
}

.actions-row form {
    display: inline;
    margin: 0;
    padding: 0;
}

.actions-row .action-btn,
.actions-row form .action-btn {
    all: unset;
    display: inline-block;
    padding: 6px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    text-decoration: none;
    line-height: 1.4;
    transition: opacity 0.2s;
    box-sizing: border-box;
}

.actions-row .action-btn:hover {
    opacity: 0.85;
}

.actions-row .action-btn-primary {
    background: var(--accent-color);
    color: #fff;
}

.actions-row .action-btn-danger {
    background: var(--danger-color);
    color: #fff;
}

.actions-row .action-btn-danger:hover {
    opacity: 0.75;
}

/* Progress bar */
.progress-bar {
    width: 100%;
    height: 6px;
    background: var(--bg-tertiary);
    border-radius: 3px;
    overflow: hidden;
}

/* Refresh button */
.refresh-btn {
    all: unset !important;
    display: inline !important;
    width: auto !important;
    height: auto !important;
    padding: 0 3px !important;
    margin: 0 !important;
    background: none !important;
    border: none !important;
    font-size: 12px !important;
    color: var(--text-secondary) !important;
    cursor: pointer !important;
    vertical-align: baseline !important;
    line-height: 1 !important;
}
.refresh-btn:hover {
    color: var(--accent-color) !important;
}

/* Code inline */
code {
    background: var(--bg-tertiary);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 12px;
}
"""
