from __future__ import annotations
import math
import re
from pathlib import Path
from collections import Counter

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.collections import PolyCollection
from matplotlib.tri import Triangulation

ROOT = Path(r"C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\oxide_macros_tcox12")
OUT_ROOT = ROOT / r"diagramas finales"
OUT_ROOT.mkdir(parents=True, exist_ok=True)
SYSTEMS = {
    'CAMA': {'fixed_caf2': 0.0, 'fixed_sio2': 0.0},
    'CAMA_5CAF2': {'fixed_caf2': 5.0, 'fixed_sio2': 0.0},
    'CAMA_5CAF2_1SIO2': {'fixed_caf2': 5.0, 'fixed_sio2': 1.0},
    'CAMA_5CAF2_5SIO2': {'fixed_caf2': 5.0, 'fixed_sio2': 5.0},
    'CAMA_5CAF2_10SIO2': {'fixed_caf2': 5.0, 'fixed_sio2': 10.0},
}

MM_TO_INCH = 1 / 25.4
SINGLE_COLUMN_MM = 85
TRACE_THRESHOLD = 1e-4
MIN_REGION_TRIANGLES = 6
MIN_REGION_POINTS = 10
TOP_LEGEND_FIELDS = 8
H = math.sqrt(3) / 2.0

mpl.rcParams.update({
    'figure.dpi': 160,
    'savefig.dpi': 600,
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'Times', 'DejaVu Serif'],
    'mathtext.fontset': 'dejavuserif',
    'font.size': 9,
    'axes.labelsize': 9,
    'axes.titlesize': 10,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'legend.fontsize': 7,
    'axes.linewidth': 0.8,
    'lines.linewidth': 1.1,
    'svg.fonttype': 'none',
})

PAIR_RE = re.compile(r'([A-Z0-9_#]+\([^)]*\)|[A-Z0-9_#]+)=([-+0-9.Ee]+|0\.)')
BLOCK_START_RE = re.compile(r'^\s*\$ BLOCK')
BLOCK_ID_RE = re.compile(r'\$\s*BLOCK\s*#(\d+)')
PHASE_RE = re.compile(r'^\s*\$(E|F0)\s+(.+)$')
POINT_RE = re.compile(r'^\s*([-+0-9.Ee]+)\s+([-+0-9.Ee]+)')
LABEL_RE = re.compile(r"^\s*([-+0-9.Ee]+)\s+([-+0-9.Ee]+)\s+'(.*)$")

PHASE_REMAP = {
    'IONIC_LIQ#1': 'L', 'IONIC_LIQ#2': 'L', 'IONIC_LIQ#3': 'L',
    'HALITE#1': 'MgO', 'HALITE#2': 'CaO', 'SPINEL': 'Spinel',
    'C1A2': 'CA2', 'C1A8M2': 'CA8M2', 'C2A14M2': 'C2A14M2', 'C1A6': 'CA6',
    'CORUNDUM': 'Corundum', 'GAS': 'Gas',
}
PALETTE = [
    '#4C78A8', '#F58518', '#54A24B', '#E45756', '#B279A2', '#FF9DA6', '#9D755D', '#BAB0AC',
    '#72B7B2', '#EECA3B', '#A0CBE8', '#FFBE7D', '#8CD17D', '#B6992D', '#499894'
]


def parse_dat(dat_path: Path):
    rows = []
    current = {}
    for raw in dat_path.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = raw.strip()
        if not line:
            continue
        pairs = PAIR_RE.findall(line)
        if not pairs:
            continue
        keys = {k for k, _ in pairs}
        if 'W(CAO)' in keys and current:
            rows.append(current)
            current = {}
        for k, v in pairs:
            current[k] = v
    if current:
        rows.append(current)
    return rows


def normalize_phase_name(name: str) -> str:
    return PHASE_REMAP.get(name.strip(), name.strip().replace('_', ' '))


def canonical_assemblage(row: dict, trace_threshold: float = TRACE_THRESHOLD) -> str:
    phases = []
    for k, v in row.items():
        if not (k.startswith('NP(') and k.endswith(')')):
            continue
        phase = k[3:-1]
        try:
            val = float(v)
        except Exception:
            continue
        if val <= trace_threshold:
            continue
        pname = normalize_phase_name(phase)
        if pname == 'Gas':
            continue
        phases.append(pname)
    phases = sorted(set(phases), key=lambda x: (x != 'L', x))
    return ' + '.join(phases) if phases else 'Unknown'


def ternary_to_xy(cao, mgo, al2o3):
    total = cao + mgo + al2o3
    if total <= 0:
        return np.nan, np.nan
    a = cao / total; b = mgo / total; c = al2o3 / total
    return 0.5 * (2 * b + c), H * c


def parse_grid(tag: str, fixed: dict) -> pd.DataFrame:
    dat_path = ROOT / 'batch_5000' / tag / f'{tag}_grid5000_show.dat'
    rows = parse_dat(dat_path)
    data = []
    for row in rows:
        try:
            cao = float(row['W(CAO)']) * 100.0
            mgo = float(row['W(MGO)']) * 100.0
            if 'W(AL2O3)' in row:
                al2o3 = float(row['W(AL2O3)']) * 100.0
            else:
                al2o3 = 100.0 - cao - mgo - fixed['fixed_caf2'] - fixed['fixed_sio2']
        except Exception:
            continue
        x, y = ternary_to_xy(cao, mgo, al2o3)
        data.append({'cao': cao, 'mgo': mgo, 'al2o3': al2o3, 'x': x, 'y': y, 'assemblage': canonical_assemblage(row)})
    return pd.DataFrame(data).dropna(subset=['x', 'y']).reset_index(drop=True)


def parse_exp(path: Path):
    blocks = []
    current = None
    for raw in path.read_text(encoding='latin-1', errors='ignore').splitlines():
        line = raw.rstrip('\n')
        if BLOCK_START_RE.match(line):
            if current:
                blocks.append(current)
            bid = None
            m = BLOCK_ID_RE.search(line)
            if m:
                bid = int(m.group(1))
            current = {'block_id': bid, 'phases': [], 'segments': [], 'current_segment': []}
            continue
        if current is None:
            continue
        pm = PHASE_RE.match(line.strip())
        if pm:
            current['phases'].append(pm.group(2).strip())
            continue
        if line.strip() == 'BLOCKEND':
            if current['current_segment']:
                current['segments'].append(np.array(current['current_segment'], dtype=float))
                current['current_segment'] = []
            blocks.append(current)
            current = None
            continue
        if line.strip().startswith('BLOCK') or line.strip().startswith('$'):
            continue
        pt = POINT_RE.match(line)
        if pt:
            x = float(pt.group(1)) * 100.0
            y = float(pt.group(2)) * 100.0
            if 'M' in line:
                if current['current_segment']:
                    current['segments'].append(np.array(current['current_segment'], dtype=float))
                    current['current_segment'] = []
                current['current_segment'].append([x, y])
            else:
                current['current_segment'].append([x, y])
    if current:
        if current['current_segment']:
            current['segments'].append(np.array(current['current_segment'], dtype=float))
        blocks.append(current)
    return blocks


def build_regions(df: pd.DataFrame):
    tri = Triangulation(df['x'].to_numpy(), df['y'].to_numpy())
    rows = []
    for tidx, verts in enumerate(tri.triangles):
        labs = df.iloc[verts]['assemblage'].tolist()
        counts = Counter(labs)
        label, n = counts.most_common(1)[0]
        purity = n / len(labs)
        cx = float(df.iloc[verts]['x'].mean())
        cy = float(df.iloc[verts]['y'].mean())
        rows.append({'triangle_id': tidx, 'assemblage': label, 'purity': purity, 'cx': cx, 'cy': cy, 'valid': purity >= 2/3})
    tri_df = pd.DataFrame(rows)
    tri_df = tri_df[tri_df['valid']].copy()
    groups = []
    for label, g in tri_df.groupby('assemblage'):
        groups.append({'assemblage': label, 'triangle_ids': g['triangle_id'].tolist(), 'n_triangles': len(g), 'approx_area': float(len(g)), 'cx': float(g['cx'].mean()), 'cy': float(g['cy'].mean())})
    reg = pd.DataFrame(groups).sort_values('approx_area', ascending=False).reset_index(drop=True)
    reg['region_id'] = [f'R{i+1:02d}' for i in range(len(reg))]
    reg['n_grid_points'] = reg['assemblage'].map(df['assemblage'].value_counts()).fillna(0).astype(int)
    reg['is_minor'] = (reg['n_triangles'] < MIN_REGION_TRIANGLES) | (reg['n_grid_points'] < MIN_REGION_POINTS)
    reg['show_in_legend'] = ~reg['is_minor']
    reg['has_internal_label'] = False
    reg['label_mode'] = 'none'
    reg['numeric_id'] = pd.NA
    reg['label_text'] = reg['assemblage']
    return tri, tri_df, reg


def classify_labels(reg: pd.DataFrame) -> pd.DataFrame:
    reg = reg.copy()
    area_q66 = reg['approx_area'].quantile(0.66) if len(reg) > 1 else reg['approx_area'].iloc[0]
    area_q33 = reg['approx_area'].quantile(0.33) if len(reg) > 1 else reg['approx_area'].iloc[0]
    numeric_counter = 1
    for idx, row in reg.iterrows():
        top_zone = row['cy'] > 0.72 * H
        very_small = row['approx_area'] < max(MIN_REGION_TRIANGLES, area_q33)
        medium = row['approx_area'] >= area_q33 and row['approx_area'] < area_q66
        large = row['approx_area'] >= area_q66
        if large and not top_zone:
            reg.at[idx, 'label_mode'] = 'text'; reg.at[idx, 'has_internal_label'] = True
        elif medium and not top_zone:
            reg.at[idx, 'label_mode'] = 'text'; reg.at[idx, 'has_internal_label'] = True
        elif row['is_minor'] or top_zone or very_small:
            reg.at[idx, 'label_mode'] = 'number'; reg.at[idx, 'numeric_id'] = numeric_counter; reg.at[idx, 'has_internal_label'] = True; numeric_counter += 1
        else:
            reg.at[idx, 'label_mode'] = 'none'; reg.at[idx, 'has_internal_label'] = False
    return reg


def build_color_map(reg: pd.DataFrame):
    cmap = {lab: PALETTE[i % len(PALETTE)] for i, lab in enumerate(reg['assemblage'])}
    cmap['Other minor assemblages'] = '#D9D9D9'
    return cmap


def setup_xy_axes(fig):
    ax = fig.add_subplot(111)
    ax.set_aspect('equal'); ax.set_xlim(-0.06, 1.50); ax.set_ylim(-0.05, H + 0.08); ax.axis('off')
    return ax


def draw_triangle_frame(ax, top_label: str):
    tri = np.array([[0, 0], [1, 0], [0.5, H], [0, 0]])
    ax.plot(tri[:, 0], tri[:, 1], color='black', lw=1.2, zorder=5)
    for val in range(10, 100, 10):
        frac = val / 100.0
        ax.plot([0.5 * frac, 1 - 0.5 * frac], [H * frac, H * frac], color='0.87', lw=0.4, zorder=0)
        ax.plot([frac, 0.5 + 0.5 * frac], [0, H * (1 - frac)], color='0.87', lw=0.4, zorder=0)
        ax.plot([1 - frac, 0.5 * (1 - frac)], [0, H * (1 - frac)], color='0.87', lw=0.4, zorder=0)
    ax.text(-0.04, -0.04, 'CaO', fontsize=11, ha='left', va='top')
    ax.text(1.04, -0.04, 'MgO', fontsize=11, ha='right', va='top')
    ax.text(0.5, H + 0.04, top_label, fontsize=11, ha='center', va='bottom')
    for val in range(10, 100, 10):
        frac = val / 100.0
        ax.text(frac, -0.03, f'{val}', fontsize=8, ha='center', va='top')
        ax.text(0.5 * frac - 0.025, H * frac, f'{val}', fontsize=8, ha='right', va='center')
        ax.text(1 - 0.5 * frac + 0.025, H * frac, f'{val}', fontsize=8, ha='left', va='center')


def draw_exp_boundaries(ax, blocks, fixed):
    for block in blocks:
        for seg in block['segments']:
            if len(seg) < 2:
                continue
            pts = []
            for cao, mgo in seg:
                al2o3 = 100.0 - cao - mgo - fixed['fixed_caf2'] - fixed['fixed_sio2']
                if al2o3 < -1e-8:
                    continue
                pts.append(ternary_to_xy(cao, mgo, al2o3))
            if len(pts) >= 2:
                arr = np.array(pts)
                ax.plot(arr[:, 0], arr[:, 1], color='black', lw=0.95, alpha=0.9, zorder=4)


def build_region_collection(tri, tri_df, reg, color_map):
    polys, colors = [], []
    for _, row in reg.iterrows():
        color = color_map[row['assemblage']] if not row['is_minor'] else color_map['Other minor assemblages']
        tids = set(row['triangle_ids'])
        for tid in tri_df.loc[tri_df['triangle_id'].isin(tids), 'triangle_id']:
            verts = tri.triangles[int(tid)]
            polys.append(np.column_stack([tri.x[verts], tri.y[verts]]))
            colors.append(color)
    return PolyCollection(polys, facecolors=colors, edgecolors='none', linewidths=0.0, alpha=1.0, zorder=1)


def draw_labels(ax, reg):
    for _, row in reg.iterrows():
        if not row['has_internal_label']:
            continue
        if row['label_mode'] == 'text':
            ax.text(row['cx'], row['cy'], row['label_text'], fontsize=6.0, ha='center', va='center', bbox=dict(facecolor='white', alpha=0.74, edgecolor='none', pad=0.25), zorder=6)
        elif row['label_mode'] == 'number' and pd.notna(row['numeric_id']):
            x, y = row['cx'], row['cy']
            if y > 0.72 * H:
                x += 0.02 if x < 0.5 else -0.02; y -= 0.01
            ax.text(x, y, str(int(row['numeric_id'])), fontsize=6.4, ha='center', va='center', bbox=dict(facecolor='white', alpha=0.82, edgecolor='black', linewidth=0.2, boxstyle='round,pad=0.15'), zorder=7)


def draw_side_tables(fig, reg, color_map):
    legend_rows = reg[reg['show_in_legend']].head(TOP_LEGEND_FIELDS)
    handles = [Line2D([0], [0], color=color_map[r['assemblage']], lw=4, label=r['assemblage']) for _, r in legend_rows.iterrows()]
    if reg['is_minor'].any():
        handles.append(Line2D([0], [0], color=color_map['Other minor assemblages'], lw=4, label='Other minor assemblages'))
    fig.legend(handles=handles, loc='upper left', bbox_to_anchor=(0.79, 0.92), frameon=True, title='Main phase fields')
    numbered = reg[reg['label_mode'] == 'number'].sort_values('numeric_id')
    if len(numbered) > 0:
        lines = ['Numbered minor / compact fields']
        for _, row in numbered.iterrows():
            lines.append(f"{int(row['numeric_id'])} -> {row['assemblage']}")
        fig.text(0.79, 0.50, '\n'.join(lines), ha='left', va='top', fontsize=7, bbox=dict(facecolor='white', edgecolor='0.6', boxstyle='round,pad=0.35'))


def export_region_table(out_dir: Path, reg, color_map):
    out = reg[['region_id', 'assemblage', 'n_grid_points', 'approx_area', 'is_minor', 'show_in_legend', 'has_internal_label', 'label_mode', 'numeric_id', 'label_text']].copy()
    out['color'] = out.apply(lambda r: color_map[r['assemblage']] if not r['is_minor'] else color_map['Other minor assemblages'], axis=1)
    out.to_csv(out_dir / 'region_summary_hybrid.csv', index=False)


def write_note(out_dir: Path, tag: str):
    note = f"Hybrid annotation note for {tag}: region logic, triangulation, assemblage classification, EXP boundaries, and XY continuous render were kept unchanged; only annotation/layout were refined."
    (out_dir / 'hybrid_annotation_note.txt').write_text(note, encoding='utf-8')


def render_system(tag: str, fixed: dict):
    out_dir = OUT_ROOT / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    df = parse_grid(tag, fixed)
    exp_blocks = parse_exp(ROOT / 'maps' / tag / f'{tag}_map.exp')
    tri, tri_df, reg = build_regions(df)
    reg = classify_labels(reg)
    color_map = build_color_map(reg)
    top_label = 'Al2O3* (wt.%)' if (fixed['fixed_caf2'] > 0 or fixed['fixed_sio2'] > 0) else 'Al2O3 (wt.%)'

    fig = plt.figure(figsize=(SINGLE_COLUMN_MM * MM_TO_INCH * 1.95, SINGLE_COLUMN_MM * MM_TO_INCH * 1.25))
    ax = setup_xy_axes(fig)
    draw_triangle_frame(ax, top_label)
    ax.add_collection(build_region_collection(tri, tri_df, reg, color_map))
    draw_exp_boundaries(ax, exp_blocks, fixed)
    draw_labels(ax, reg)
    draw_side_tables(fig, reg, color_map)
    ax.set_title(f'{tag} final ternary phase diagram', pad=8)
    fig.savefig(out_dir / f'{tag}_final_main_hybrid_labels.png', bbox_inches='tight')
    fig.savefig(out_dir / f'{tag}_final_main_hybrid_labels.svg', bbox_inches='tight')
    plt.close(fig)

    fig = plt.figure(figsize=(SINGLE_COLUMN_MM * MM_TO_INCH * 1.95, SINGLE_COLUMN_MM * MM_TO_INCH * 1.25))
    ax = setup_xy_axes(fig)
    draw_triangle_frame(ax, top_label)
    ax.add_collection(build_region_collection(tri, tri_df, reg, color_map))
    ax.scatter(df['x'], df['y'], s=4, color='black', alpha=0.12, zorder=2)
    draw_exp_boundaries(ax, exp_blocks, fixed)
    for _, row in reg.iterrows():
        if row['label_mode'] == 'text':
            ax.text(row['cx'], row['cy'], 'T', fontsize=7, ha='center', va='center', color='black', zorder=7)
        elif row['label_mode'] == 'number' and pd.notna(row['numeric_id']):
            ax.text(row['cx'], row['cy'], f"N{int(row['numeric_id'])}", fontsize=6.5, ha='center', va='center', color='black', zorder=7)
    ax.set_title(f'{tag} control figure: hybrid annotation modes', pad=8)
    fig.savefig(out_dir / f'{tag}_final_control_hybrid.png', bbox_inches='tight')
    plt.close(fig)

    export_region_table(out_dir, reg, color_map)
    write_note(out_dir, tag)
    print(f'OK {tag}: points={len(df)} regions={len(reg)}')


def main():
    for tag, fixed in SYSTEMS.items():
        render_system(tag, fixed)

if __name__ == '__main__':
    main()
