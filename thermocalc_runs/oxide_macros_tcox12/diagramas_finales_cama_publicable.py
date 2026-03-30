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
from matplotlib.patches import Polygon
from matplotlib.collections import PolyCollection
from matplotlib.tri import Triangulation

ROOT = Path(r"C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\oxide_macros_tcox12")
GRID_DAT = ROOT / r"batch_5000\CAMA\CAMA_grid5000_show.dat"
EXP_PATH = ROOT / r"maps\CAMA\CAMA_map.exp"
OUT_DIR = ROOT / r"diagramas finales\CAMA_publicable"
OUT_DIR.mkdir(parents=True, exist_ok=True)

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
    'IONIC_LIQ#1': 'L',
    'IONIC_LIQ#2': 'L',
    'IONIC_LIQ#3': 'L',
    'HALITE#1': 'MgO',
    'HALITE#2': 'CaO',
    'SPINEL': 'Spinel',
    'C1A2': 'CA2',
    'C1A8M2': 'CA8M2',
    'C2A14M2': 'C2A14M2',
    'C1A6': 'CA6',
    'CORUNDUM': 'Corundum',
    'GAS': 'Gas',
}
PALETTE = [
    '#4C78A8', '#F58518', '#54A24B', '#E45756', '#B279A2',
    '#FF9DA6', '#9D755D', '#BAB0AC', '#72B7B2', '#EECA3B',
    '#A0CBE8', '#FFBE7D', '#8CD17D', '#B6992D', '#499894'
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
    a = cao / total
    b = mgo / total
    c = al2o3 / total
    x = 0.5 * (2 * b + c)
    y = H * c
    return x, y


def xy_to_ternary(x, y):
    c = y / H
    b = x - 0.5 * c
    a = 1.0 - b - c
    return a * 100.0, b * 100.0, c * 100.0


def parse_grid() -> pd.DataFrame:
    rows = parse_dat(GRID_DAT)
    data = []
    for row in rows:
        try:
            cao = float(row['W(CAO)']) * 100.0
            mgo = float(row['W(MGO)']) * 100.0
            al2o3 = float(row['W(AL2O3)']) * 100.0
        except Exception:
            continue
        x, y = ternary_to_xy(cao, mgo, al2o3)
        data.append({'cao': cao, 'mgo': mgo, 'al2o3': al2o3, 'x': x, 'y': y, 'assemblage': canonical_assemblage(row)})
    return pd.DataFrame(data).dropna(subset=['x', 'y']).reset_index(drop=True)


def parse_exp(path: Path):
    blocks = []
    labels = []
    current = None
    for raw in path.read_text(encoding='latin-1', errors='ignore').splitlines():
        lm = LABEL_RE.match(raw)
        if lm:
            labels.append((float(lm.group(1)), float(lm.group(2)), lm.group(3).strip()))
            continue
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
    return blocks, labels


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
        groups.append({
            'assemblage': label,
            'triangle_ids': g['triangle_id'].tolist(),
            'n_triangles': len(g),
            'approx_area': float(len(g)),
            'cx': float(g['cx'].mean()),
            'cy': float(g['cy'].mean()),
        })
    reg = pd.DataFrame(groups).sort_values('approx_area', ascending=False).reset_index(drop=True)
    reg['region_id'] = [f'R{i+1:02d}' for i in range(len(reg))]
    reg['n_grid_points'] = reg['assemblage'].map(df['assemblage'].value_counts()).fillna(0).astype(int)
    reg['is_minor'] = (reg['n_triangles'] < MIN_REGION_TRIANGLES) | (reg['n_grid_points'] < MIN_REGION_POINTS)
    reg['show_in_legend'] = ~reg['is_minor']
    reg['has_internal_label'] = (~reg['is_minor']) & (reg['n_triangles'] >= MIN_REGION_TRIANGLES * 2)
    return tri, tri_df, reg


def build_color_map(reg: pd.DataFrame):
    cmap = {lab: PALETTE[i % len(PALETTE)] for i, lab in enumerate(reg['assemblage'])}
    cmap['Other minor assemblages'] = '#D9D9D9'
    return cmap


def setup_xy_axes(fig):
    ax = fig.add_subplot(111)
    ax.set_aspect('equal')
    ax.set_xlim(-0.06, 1.30)
    ax.set_ylim(-0.05, H + 0.08)
    ax.axis('off')
    return ax


def draw_triangle_frame(ax):
    tri = np.array([[0, 0], [1, 0], [0.5, H], [0, 0]])
    ax.plot(tri[:, 0], tri[:, 1], color='black', lw=1.2, zorder=5)
    for val in range(10, 100, 10):
        frac = val / 100.0
        ax.plot([0.5 * frac, 1 - 0.5 * frac], [H * frac, H * frac], color='0.87', lw=0.4, zorder=0)
        ax.plot([frac, 0.5 + 0.5 * frac], [0, H * (1 - frac)], color='0.87', lw=0.4, zorder=0)
        ax.plot([1 - frac, 0.5 * (1 - frac)], [0, H * (1 - frac)], color='0.87', lw=0.4, zorder=0)
    ax.text(-0.04, -0.04, 'CaO', fontsize=11, ha='left', va='top')
    ax.text(1.04, -0.04, 'MgO', fontsize=11, ha='right', va='top')
    ax.text(0.5, H + 0.04, 'Al2O3 (wt.%)', fontsize=11, ha='center', va='bottom')
    for val in range(10, 100, 10):
        frac = val / 100.0
        ax.text(frac, -0.03, f'{val}', fontsize=8, ha='center', va='top')
        ax.text(0.5 * frac - 0.025, H * frac, f'{val}', fontsize=8, ha='right', va='center')
        ax.text(1 - 0.5 * frac + 0.025, H * frac, f'{val}', fontsize=8, ha='left', va='center')


def draw_exp_boundaries(ax, blocks):
    for block in blocks:
        for seg in block['segments']:
            if len(seg) < 2:
                continue
            pts = []
            for cao, mgo in seg:
                al2o3 = 100.0 - cao - mgo
                if al2o3 < -1e-8:
                    continue
                pts.append(ternary_to_xy(cao, mgo, al2o3))
            if len(pts) >= 2:
                arr = np.array(pts)
                ax.plot(arr[:, 0], arr[:, 1], color='black', lw=0.95, alpha=0.9, zorder=4)


def build_region_collection(tri, tri_df, reg, color_map):
    polys = []
    colors = []
    for _, row in reg.iterrows():
        color = color_map[row['assemblage']] if not row['is_minor'] else color_map['Other minor assemblages']
        tids = set(row['triangle_ids'])
        for tid in tri_df.loc[tri_df['triangle_id'].isin(tids), 'triangle_id']:
            verts = tri.triangles[int(tid)]
            poly = np.column_stack([tri.x[verts], tri.y[verts]])
            polys.append(poly)
            colors.append(color)
    return PolyCollection(polys, facecolors=colors, edgecolors='none', linewidths=0.0, alpha=1.0, zorder=1)


def draw_internal_labels(ax, reg):
    for _, row in reg.iterrows():
        if not row['has_internal_label']:
            continue
        ax.text(row['cx'], row['cy'], row['assemblage'], fontsize=6.2, ha='center', va='center',
                bbox=dict(facecolor='white', alpha=0.72, edgecolor='none', pad=0.25), zorder=6)


def plot_main(df, tri, tri_df, reg, exp_blocks, color_map):
    fig = plt.figure(figsize=(SINGLE_COLUMN_MM * MM_TO_INCH * 1.7, SINGLE_COLUMN_MM * MM_TO_INCH * 1.2))
    ax = setup_xy_axes(fig)
    draw_triangle_frame(ax)
    ax.add_collection(build_region_collection(tri, tri_df, reg, color_map))
    draw_exp_boundaries(ax, exp_blocks)
    draw_internal_labels(ax, reg)
    legend_rows = reg[reg['show_in_legend']].head(TOP_LEGEND_FIELDS)
    handles = [Line2D([0], [0], color=color_map[r['assemblage']], lw=4, label=r['assemblage']) for _, r in legend_rows.iterrows()]
    if reg['is_minor'].any():
        handles.append(Line2D([0], [0], color=color_map['Other minor assemblages'], lw=4, label='Other minor assemblages'))
    fig.legend(handles=handles, loc='center left', bbox_to_anchor=(0.87, 0.5), frameon=True, title='Phase fields')
    ax.set_title('CAMA final ternary phase diagram\nEXP boundaries + grid-based continuous phase fields', pad=10)
    fig.savefig(OUT_DIR / 'CAMA_final_main.png', bbox_inches='tight')
    fig.savefig(OUT_DIR / 'CAMA_final_main.svg', bbox_inches='tight')
    plt.close(fig)


def plot_control(df, tri, tri_df, reg, exp_blocks, color_map):
    fig = plt.figure(figsize=(SINGLE_COLUMN_MM * MM_TO_INCH * 1.7, SINGLE_COLUMN_MM * MM_TO_INCH * 1.2))
    ax = setup_xy_axes(fig)
    draw_triangle_frame(ax)
    ax.add_collection(build_region_collection(tri, tri_df, reg, color_map))
    ax.scatter(df['x'], df['y'], s=4, color='black', alpha=0.15, zorder=2)
    draw_exp_boundaries(ax, exp_blocks)
    ax.set_title('CAMA control figure\ncontinuous region fill rendered in XY + light grid sampling overlay', pad=10)
    fig.savefig(OUT_DIR / 'CAMA_final_control.png', bbox_inches='tight')
    plt.close(fig)


def export_region_table(reg, color_map):
    out = reg[['region_id', 'assemblage', 'n_grid_points', 'approx_area', 'is_minor', 'show_in_legend', 'has_internal_label']].copy()
    out['color'] = out['assemblage'].map(lambda x: color_map[x] if not out.loc[out['assemblage'] == x, 'is_minor'].iloc[0] else color_map['Other minor assemblages'])
    out.to_csv(OUT_DIR / 'CAMA_region_summary.csv', index=False)


def write_note():
    note = (
        'Render note: the final continuous fill was resolved in Cartesian XY coordinates instead of direct mpltern tripcolor.\n'
        'Reason: mpltern is useful for ternary orientation and annotation, but direct tripcolor with a Cartesian triangulation proved fragile.\n'
        'Therefore, classification, triangulation, and continuous fill are preserved exactly as built, while only the render layer uses robust XY polygon filling.\n'
        'The EXP boundaries are projected consistently to the same XY ternary frame and overplotted as the authoritative phase-boundary geometry.\n'
    )
    (OUT_DIR / 'CAMA_render_note.txt').write_text(note, encoding='utf-8')


def main():
    df = parse_grid()
    exp_blocks, _ = parse_exp(EXP_PATH)
    tri, tri_df, reg = build_regions(df)
    color_map = build_color_map(reg)
    plot_main(df, tri, tri_df, reg, exp_blocks, color_map)
    plot_control(df, tri, tri_df, reg, exp_blocks, color_map)
    export_region_table(reg, color_map)
    write_note()
    print(f'OK main: {OUT_DIR / "CAMA_final_main.png"}')
    print(f'OK control: {OUT_DIR / "CAMA_final_control.png"}')
    print(f'OK table: {OUT_DIR / "CAMA_region_summary.csv"}')
    print(f'OK note: {OUT_DIR / "CAMA_render_note.txt"}')
    print(f'POINTS={len(df)} REGIONS={len(reg)}')


if __name__ == '__main__':
    main()
