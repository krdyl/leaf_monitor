"""
generate_dashboard.py
Reads all PAI time series CSVs, generates a self-contained HTML dashboard,
and pushes to gh-pages.

Usage:
    python generate_dashboard.py

Config:
    PAI_DIR   — directory containing *_flagged.csv or *.csv output files
    REPO_DIR  — local clone of leaf-monitor (gh-pages branch)
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
PAI_DIR  = Path("/Stor1/karun/data/pai_timeseries")
REPO_DIR = Path("/home/kdayal/Documents/projects/qfl/leaf_monitor")

# ── Load all CSVs ─────────────────────────────────────────────────────────────
def load_scanners():
    scanners = {}
    for csv in sorted(PAI_DIR.glob("*.csv")):
        df = pd.read_csv(csv, parse_dates=["date"])
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")
        # fill NaN with None for JSON
        df = df.where(pd.notnull(df), None)
        scanners[csv.stem] = df.to_dict(orient="records")
    return scanners

# ── HTML template ─────────────────────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LEAF PAI Monitor</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.26.0/plotly.min.js"></script>
<style>
  :root {{
    --bg:      #0f1117;
    --surface: #181c27;
    --border:  #2a2f3e;
    --accent:  #4a9eff;
    --flag:    #e05c5c;
    --text:    #d4d8e8;
    --muted:   #6b7194;
    --font:    'JetBrains Mono', 'Fira Mono', monospace;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: var(--font); font-size: 13px; }}

  header {{
    padding: 14px 24px;
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  }}
  header h1 {{ font-size: 13px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }}
  .updated {{ margin-left: auto; font-size: 11px; color: var(--muted); }}

  .layout {{ display: flex; height: calc(100vh - 49px); }}

  nav {{
    width: 220px; min-width: 220px;
    border-right: 1px solid var(--border);
    overflow-y: auto;
    padding: 8px 0;
  }}

  nav .plot-label {{
    font-size: 10px; color: var(--muted); text-transform: uppercase;
    letter-spacing: 0.06em; padding: 10px 16px 4px;
  }}

  nav button {{
    display: block; width: 100%; text-align: left;
    font-family: var(--font); font-size: 11px;
    padding: 7px 16px; border: none; background: none;
    color: var(--text); cursor: pointer; transition: background 0.1s;
  }}
  nav button:hover {{ background: var(--surface); }}
  nav button.active {{ color: var(--accent); background: var(--surface); border-left: 2px solid var(--accent); }}
  nav .flag-badge {{ float: right; color: var(--flag); font-size: 10px; }}

  .main {{ flex: 1; overflow-y: auto; padding: 16px 20px; display: flex; flex-direction: column; gap: 10px; }}

  .controls {{
    display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
    padding-bottom: 10px; border-bottom: 1px solid var(--border);
  }}

  .control-group {{ display: flex; gap: 6px; align-items: center; }}
  .control-group label {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }}

  button.tog {{
    font-family: var(--font); font-size: 11px; padding: 4px 10px;
    border-radius: 3px; border: 1px solid var(--border);
    background: var(--surface); color: var(--text); cursor: pointer;
  }}
  button.tog.active {{ background: var(--accent); border-color: var(--accent); color: #fff; }}
  button.action {{
    font-family: var(--font); font-size: 11px; padding: 5px 12px;
    border-radius: 3px; border: 1px solid var(--border);
    background: var(--surface); color: var(--text); cursor: pointer;
  }}
  button.action:hover {{ border-color: var(--accent); }}
  button.action.danger {{ border-color: var(--flag); color: var(--flag); }}
  button.action.danger:hover {{ background: #1a0808; }}
  button.action.primary {{ background: var(--accent); border-color: var(--accent); color: #fff; }}

  .flag-count {{ font-size: 11px; color: var(--flag); min-width: 70px; }}

  .plot-panel {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 6px; overflow: hidden;
  }}
  .plot-header {{
    font-size: 11px; color: var(--muted); text-transform: uppercase;
    letter-spacing: 0.05em; padding: 8px 14px; border-bottom: 1px solid var(--border);
  }}
  .plot-div {{ width: 100%; height: 210px; }}

  #status {{ font-size: 11px; color: var(--muted); padding: 4px 0; }}
</style>
</head>
<body>

<header>
  <h1>LEAF PAI Monitor</h1>
  <span class="updated">Updated {updated}</span>
</header>

<div class="layout">
  <nav id="nav"></nav>
  <div class="main">
    <div class="controls">
      <div class="control-group">
        <label>Estimator</label>
        <button class="tog active" id="tog-hinge"  onclick="toggleEst('hinge',  this)">Hinge</button>
        <button class="tog active" id="tog-hemi"   onclick="toggleEst('hemi',   this)">Hemi</button>
        <button class="tog active" id="tog-linear" onclick="toggleEst('linear', this)">Linear</button>
      </div>
      <div style="margin-left:auto; display:flex; gap:8px; align-items:center;">
        <span class="flag-count" id="flag-count"></span>
        <button class="action" onclick="autoFlag()">Auto-flag 3×IQR</button>
        <button class="action danger" onclick="clearFlags()">Clear flags</button>
        <button class="action primary" onclick="downloadCSV()">Download CSV</button>
      </div>
    </div>
    <div id="status">Select a scanner.</div>
    <div id="plots"></div>
  </div>
</div>

<script>
const ALL_DATA = {all_data};

const SCAN_TYPES = ["hinge_hi", "hemi_hi", "hemi_low"];
const ESTIMATORS = {{
  hinge:  {{ col: "pai_hinge",  std: "pai_hinge_std",  color: "#4a8fc4", label: "Hinge"  }},
  hemi:   {{ col: "pai_hemi",   std: "pai_hemi_std",   color: "#c45a5a", label: "Hemi"   }},
  linear: {{ col: "pai_linear", std: "pai_linear_std", color: "#5a9a4a", label: "Linear" }},
}};

let currentScanner = null;
let activeEst = new Set(["hinge", "hemi", "linear"]);
let flagged = {{}};   // scanner -> Set of row indices

// ── Nav ───────────────────────────────────────────────────────────────────────
function buildNav() {{
  const nav = document.getElementById('nav');
  const scanners = Object.keys(ALL_DATA);

  // group by plot prefix e.g. BOS001
  const groups = {{}};
  scanners.forEach(s => {{
    const prefix = s.split('_')[0];
    if (!groups[prefix]) groups[prefix] = [];
    groups[prefix].push(s);
  }});

  Object.entries(groups).forEach(([prefix, names]) => {{
    const lbl = document.createElement('div');
    lbl.className = 'plot-label';
    lbl.textContent = prefix;
    nav.appendChild(lbl);
    names.forEach(name => {{
      const btn = document.createElement('button');
      btn.id = 'nav-' + name;
      btn.textContent = name.replace(prefix + '_', '');
      btn.onclick = () => selectScanner(name);
      nav.appendChild(btn);
      if (!flagged[name]) flagged[name] = new Set();
    }});
  }});
}}

function updateNavBadges() {{
  Object.keys(ALL_DATA).forEach(name => {{
    const btn = document.getElementById('nav-' + name);
    if (!btn) return;
    const n = flagged[name]?.size || 0;
    const badge = btn.querySelector('.flag-badge');
    if (n > 0) {{
      if (badge) badge.textContent = '⚑' + n;
      else btn.innerHTML += `<span class="flag-badge">⚑${{n}}</span>`;
    }} else if (badge) badge.remove();
  }});
}}

// ── Scanner selection ─────────────────────────────────────────────────────────
function selectScanner(name) {{
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  document.getElementById('nav-' + name)?.classList.add('active');
  currentScanner = name;
  renderAll();
  setStatus('');
}}

// ── Plot rendering ─────────────────────────────────────────────────────────────
function renderAll() {{
  if (!currentScanner) return;
  const container = document.getElementById('plots');
  container.innerHTML = '';
  const rows = ALL_DATA[currentScanner];
  SCAN_TYPES.forEach(st => {{
    const sub = rows.filter(r => r.scan_type === st);
    if (!sub.length) return;
    const panel = document.createElement('div');
    panel.className = 'plot-panel';
    panel.innerHTML = `<div class="plot-header">${{st}}</div><div class="plot-div" id="plot-${{st}}"></div>`;
    container.appendChild(panel);
    renderPlot(st, sub);
  }});
  updateFlagCount();
}}

function renderPlot(scan_type, sub) {{
  const f = flagged[currentScanner];
  const traces = [];

  activeEst.forEach(est => {{
    const cfg = ESTIMATORS[est];
    const normal = sub.filter((r,i) => !f.has(r._orig_idx ?? sub.indexOf(r)));
    const flags  = sub.filter((r,i) =>  f.has(r._orig_idx ?? sub.indexOf(r)));

    // attach stable index
    sub.forEach((r, i) => {{ if (r._orig_idx === undefined) r._orig_idx = i; }});
    const norm2 = sub.filter(r => !f.has(r._orig_idx));
    const flag2 = sub.filter(r =>  f.has(r._orig_idx));

    if (norm2.length) traces.push({{
      x: norm2.map(r => r.date),
      y: norm2.map(r => r[cfg.col]),
      error_y: {{ type:'data', array: norm2.map(r => r[cfg.std]||0), visible:true, color:cfg.color, thickness:0.8, width:0 }},
      mode: 'markers', type: 'scatter', name: cfg.label,
      marker: {{ color: cfg.color, size: 5, opacity: 0.85 }},
      customdata: norm2.map(r => [r._orig_idx, scan_type]),
      hovertemplate: `%{{x}}<br>${{cfg.label}}: %{{y:.3f}}<extra></extra>`,
    }});

    if (flag2.length) traces.push({{
      x: flag2.map(r => r.date),
      y: flag2.map(r => r[cfg.col]),
      mode: 'markers', type: 'scatter', name: cfg.label + ' [flagged]', showlegend: false,
      marker: {{ color: '#e05c5c', size: 7, symbol: 'x' }},
      customdata: flag2.map(r => [r._orig_idx, scan_type]),
      hovertemplate: `%{{x}}<br>${{cfg.label}}: %{{y:.3f}} ⚑<extra></extra>`,
    }});
  }});

  const layout = {{
    paper_bgcolor:'transparent', plot_bgcolor:'transparent',
    margin:{{t:8,b:40,l:50,r:16}},
    xaxis:{{ color:'#6b7194', gridcolor:'#1e2232', tickfont:{{size:10}}, tickformat:'%b %Y' }},
    yaxis:{{ color:'#6b7194', gridcolor:'#1e2232', tickfont:{{size:10}}, title:{{text:'PAI',font:{{size:10,color:'#6b7194'}}}} }},
    legend:{{ font:{{size:10,color:'#d4d8e8'}}, bgcolor:'transparent' }},
    hovermode:'closest',
  }};

  const divId = 'plot-' + scan_type;
  Plotly.newPlot(divId, traces, layout, {{displayModeBar:false, responsive:true}});

  document.getElementById(divId).on('plotly_click', data => {{
    const [idx, st] = data.points[0].customdata;
    const f = flagged[currentScanner];
    if (f.has(idx)) f.delete(idx); else f.add(idx);
    const sub2 = ALL_DATA[currentScanner].filter(r => r.scan_type === st);
    renderPlot(st, sub2);
    updateFlagCount(); updateNavBadges();
  }});

  document.getElementById(divId).on('plotly_selected', data => {{
    if (!data?.points.length) return;
    data.points.forEach(pt => flagged[currentScanner].add(pt.customdata[0]));
    const sub2 = ALL_DATA[currentScanner].filter(r => r.scan_type === scan_type);
    renderPlot(scan_type, sub2);
    updateFlagCount(); updateNavBadges();
    setStatus(`Flagged ${{data.points.length}} points.`);
  }});
}}

// ── Controls ──────────────────────────────────────────────────────────────────
function toggleEst(est, btn) {{
  if (activeEst.has(est)) {{ if (activeEst.size === 1) return; activeEst.delete(est); btn.classList.remove('active'); }}
  else {{ activeEst.add(est); btn.classList.add('active'); }}
  renderAll();
}}

function autoFlag() {{
  if (!currentScanner) return;
  const rows = ALL_DATA[currentScanner];
  let n = 0;
  rows.forEach((r, i) => {{ if (r._orig_idx === undefined) r._orig_idx = i; }});
  SCAN_TYPES.forEach(st => {{
    const sub = rows.filter(r => r.scan_type === st);
    ['hinge','hemi','linear'].forEach(est => {{
      const cfg = ESTIMATORS[est];
      const vals = sub.map(r => r[cfg.col]).filter(v => v != null && isFinite(v)).sort((a,b)=>a-b);
      if (vals.length < 4) return;
      const q1 = vals[Math.floor(vals.length*0.25)];
      const q3 = vals[Math.floor(vals.length*0.75)];
      const iqr = q3 - q1;
      sub.forEach(r => {{
        const v = r[cfg.col];
        if (v != null && isFinite(v) && (v < q1-3*iqr || v > q3+3*iqr)) {{
          flagged[currentScanner].add(r._orig_idx); n++;
        }}
      }});
    }});
  }});
  renderAll(); updateNavBadges();
  setStatus(`Auto-flagged ${{n}} outliers.`);
}}

function clearFlags() {{
  if (!currentScanner) return;
  flagged[currentScanner].clear();
  renderAll(); updateNavBadges(); updateFlagCount();
  setStatus('Flags cleared.');
}}

function downloadCSV() {{
  if (!currentScanner) return;
  const rows = ALL_DATA[currentScanner];
  const f = flagged[currentScanner];
  const cols = Object.keys(rows[0]).filter(k => !k.startsWith('_') && k !== 'flag');
  const header = [...cols, 'flag'].join(',');
  const lines = rows.map(r => {{
    const vals = cols.map(c => r[c] === null || r[c] === undefined ? '' : r[c]);
    vals.push(f.has(r._orig_idx) ? 1 : 0);
    return vals.join(',');
  }});
  const blob = new Blob([[header,...lines].join('\\n')], {{type:'text/csv'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = currentScanner + '_flagged.csv';
  a.click();
  setStatus(`Downloaded ${{currentScanner}}_flagged.csv with ${{f.size}} flagged rows.`);
}}

function updateFlagCount() {{
  if (!currentScanner) return;
  const n = flagged[currentScanner]?.size || 0;
  document.getElementById('flag-count').textContent = n ? `⚑ ${{n}} flagged` : '';
}}

function setStatus(msg) {{ document.getElementById('status').textContent = msg; }}

// ── Init ──────────────────────────────────────────────────────────────────────
buildNav();
const first = Object.keys(ALL_DATA)[0];
if (first) selectScanner(first);
</script>
</body>
</html>
"""

# ── Generate HTML ─────────────────────────────────────────────────────────────
def generate_html(scanners):
    all_data_json = json.dumps(scanners, default=str)
    updated = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    return HTML_TEMPLATE.format(
        all_data=all_data_json,
        updated=updated,
    )

# ── Git push ──────────────────────────────────────────────────────────────────
def git_push(repo_dir, html_content):
    index_path = repo_dir / "index.html"
    index_path.write_text(html_content, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo_dir), "add", "index.html"], check=True)
    msg = f"Update dashboard {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "commit", "-m", msg],
        capture_output=True, text=True
    )
    if "nothing to commit" in result.stdout:
        print("Nothing changed, skipping push.")
        return
    subprocess.run(["git", "-C", str(repo_dir), "push", "origin", "gh-pages"], check=True)
    print(f"Pushed: {msg}")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading CSVs...")
    scanners = load_scanners()
    print(f"  {len(scanners)} scanners: {', '.join(scanners)}")

    print("Generating HTML...")
    html = generate_html(scanners)

    print("Pushing to GitHub...")
    git_push(REPO_DIR, html)

    print("Done.")