from __future__ import annotations
import math
from pathlib import Path
from collections import Counter

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import PolyCollection
from matplotlib.lines import Line2D
from matplotlib.tri import Triangulation

ROOT = Path(r"C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\oxide_macros_tcox12")
OUT_DIR = ROOT / r"diagramas finales\comparacion_CAMA_normalizada"
OUT_DIR.mkdir(parents=True, exist_ok=True)
SYSTEMS = [
    ('CAMA', '#1f77b4'),
    ('CAMA_5CAF2', '#d62728'),
    ('CAMA_5CAF2_1SIO2', '#2ca02c'),
    ('CAMA_5CAF2_5SIO2', '#9467bd'),
    ('CAMA_5CAF2_10SIO2', '#ff7f0e'),
]

MM_TO_INCH = 1 / 25.4
SINGLE_COLUMN_MM = 85
H = math.sqrt(3) / 2.0
TRACE_THRESHOLD = 1e-4

mpl.rcParams.update({
    'figure.dpi': 180,
    'savefig.dpi': 600,
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'Times', 'DejaVu Serif'],
    'mathtext.fontset': 'dejavuserif',
    'font.size': 9,
    'axes.labelsize': 9,
    'axes.titlesize': 10,
    'legend.fontsize': 8,
    'svg.fonttype': 'none',
})


def parse_dat(dat_path: Path):
    import re
    pair_re = re.compile(r'([A-Z0-9_#]+\([^)]*\)|[A-Z0-9_#]+)=([-+0-9.Ee]+|0\.)')
    rows = []
    current = {}
    for raw in dat_path.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = raw.strip()
        if not line:
            continue
        pairs = pair_re.findall(line)
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


def canonical_assemblage(row: dict) -> str:
    remap = {
        'IONIC_LIQ#1': 'L', 'IONIC_LIQ#2': 'L', 'IONIC_LIQ#3': 'L',
        'HALITE#1': 'MgO', 'HALITE#2': 'CaO', 'SPINEL': 'Spinel',
        'C1A2': 'CA2', 'C1A8M2': 'CA8M2', 'C2A14M2': 'C2A14M2', 'C1A6': 'CA6',
        'CORUNDUM': 'Corundum', 'GAS': 'Gas'
    }
    phases = []
    for k, v in row.items():
        if not (k.startswith('NP(') and k.endswith(')')):
            continue
        phase = k[3:-1]
        try:
            val = float(v)
        except Exception:
            continue
        if val <= TRACE_THRESHOLD:
            continue
        pname = remap.get(phase, phase)
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
    return 0.5 * (2 * b + c), H * c


def load_projected_system(tag: str) -> pd.DataFrame:
    dat_path = ROOT / 'batch_5000' / tag / f'{tag}_grid5000_show.dat'
    rows = parse_dat(dat_path)
    data = []
    for row in rows:
        try:
            cao = float(row['W(CAO)'])
            mgo = float(row['W(MGO)'])
            al2o3 = float(row['W(AL2O3)'])
        except Exception:
            continue
        denom = cao + mgo + al2o3
        if denom <= 0:
            continue
        cao_n = cao / denom * 100.0
        mgo_n = mgo / denom * 100.0
        al2o3_n = al2o3 / denom * 100.0
        x, y = ternary_to_xy(cao_n, mgo_n, al2o3_n)
        assemblage = canonical_assemblage(row)
        data.append({
            'cao_n': cao_n, 'mgo_n': mgo_n, 'al2o3_n': al2o3_n,
            'x': x, 'y': y,
            'assemblage': assemblage,
            'is_L': assemblage == 'L',
            'has_L': assemblage.startswith('L'),
        })
    return pd.DataFrame(data).dropna(subset=['x', 'y']).reset_index(drop=True)


def build_liquid_geometries(df: pd.DataFrame):
    tri = Triangulation(df['x'].to_numpy(), df['y'].to_numpy())
    tri_rows = []
    for tidx, verts in enumerate(tri.triangles):
        labs = df.iloc[verts]['assemblage'].tolist()
        counts = Counter(labs)
        modal, n = counts.most_common(1)[0]
        is_L_modal = (modal == 'L') and (n >= 2)
        has_L_mix = any(l.startswith('L') for l in labs)
        cx = float(df.iloc[verts]['x'].mean())
        cy = float(df.iloc[verts]['y'].mean())
        tri_rows.append({
            'triangle_id': tidx,
            'modal': modal,
            'is_L_modal': is_L_modal,
            'has_L_mix': has_L_mix,
            'cx': cx,
            'cy': cy,
        })
    tri_df = pd.DataFrame(tri_rows)

    liquid_triangles = tri_df[tri_df['is_L_modal']]['triangle_id'].to_numpy(dtype=int)
    liquid_boundary_segments = []
    for tidx, verts in enumerate(tri.triangles):
        labs = df.iloc[verts]['assemblage'].tolist()
        if 'L' not in labs:
            continue
        if all(l == 'L' for l in labs):
            continue
        pts = np.column_stack([tri.x[verts], tri.y[verts]])
        liquid_boundary_segments.append(pts)
    return tri, tri_df, liquid_triangles, liquid_boundary_segments


def triangle_area_xy(poly: np.ndarray) -> float:
    x = poly[:, 0]
    y = poly[:, 1]
    return 0.5 * abs(x[0]*(y[1]-y[2]) + x[1]*(y[2]-y[0]) + x[2]*(y[0]-y[1]))


def compute_liquid_metrics(tri, liquid_triangles):
    areas = []
    centroids = []
    for tid in liquid_triangles:
        verts = tri.triangles[int(tid)]
        poly = np.column_stack([tri.x[verts], tri.y[verts]])
        area = triangle_area_xy(poly)
        centroid = poly.mean(axis=0)
        areas.append(area)
        centroids.append(centroid)
    total_area = float(np.sum(areas)) if areas else 0.0
    if total_area > 0:
        cx = float(np.average([c[0] for c in centroids], weights=areas))
        cy = float(np.average([c[1] for c in centroids], weights=areas))
    else:
        cx = cy = float('nan')
    return total_area, cx, cy


def xy_to_normalized_cama(x, y):
    c = y / H
    b = x - 0.5 * c
    a = 1.0 - b - c
    return a * 100.0, b * 100.0, c * 100.0


def draw_triangle(ax):
    tri = np.array([[0, 0], [1, 0], [0.5, H], [0, 0]])
    ax.plot(tri[:, 0], tri[:, 1], color='black', lw=1.2, zorder=5)
    for val in range(10, 100, 10):
        frac = val / 100.0
        ax.plot([0.5 * frac, 1 - 0.5 * frac], [H * frac, H * frac], color='0.88', lw=0.35, zorder=0)
        ax.plot([frac, 0.5 + 0.5 * frac], [0, H * (1 - frac)], color='0.88', lw=0.35, zorder=0)
        ax.plot([1 - frac, 0.5 * (1 - frac)], [0, H * (1 - frac)], color='0.88', lw=0.35, zorder=0)
    ax.text(-0.04, -0.04, 'CaO* (wt.%)', fontsize=10, ha='left', va='top')
    ax.text(1.04, -0.04, 'MgO* (wt.%)', fontsize=10, ha='right', va='top')
    ax.text(0.5, H + 0.04, 'Al2O3* (wt.%)', fontsize=10, ha='center', va='bottom')
    ax.text(0.5, H + 0.075, 'Projection on normalized CAMA base', fontsize=8, ha='center', va='bottom', color='0.35')
    for val in range(10, 100, 10):
        frac = val / 100.0
        ax.text(frac, -0.03, f'{val}', fontsize=8, ha='center', va='top')
        ax.text(0.5 * frac - 0.02, H * frac, f'{val}', fontsize=7, ha='right', va='center')
        ax.text(1 - 0.5 * frac + 0.02, H * frac, f'{val}', fontsize=7, ha='left', va='center')
    ax.set_aspect('equal')
    ax.set_xlim(-0.06, 1.28)
    ax.set_ylim(-0.05, H + 0.10)
    ax.axis('off')


def make_overlay_liquid(system_data: dict):
    fig, ax = plt.subplots(figsize=(SINGLE_COLUMN_MM * MM_TO_INCH * 1.9, SINGLE_COLUMN_MM * MM_TO_INCH * 1.25))
    draw_triangle(ax)
    handles = []
    for tag, color in SYSTEMS:
        tri, _, liquid_triangles, _ = system_data[tag]['geom']
        polys = []
        for tid in liquid_triangles:
            verts = tri.triangles[int(tid)]
            polys.append(np.column_stack([tri.x[verts], tri.y[verts]]))
        if polys:
            pc = PolyCollection(polys, facecolors=color, edgecolors='none', alpha=0.22, zorder=1)
            ax.add_collection(pc)
        area, cx, cy = system_data[tag]['metrics']
        if not np.isnan(cx):
            ax.plot(cx, cy, marker='o', color=color, markersize=4, zorder=4)
        handles.append(Line2D([0], [0], color=color, lw=6, alpha=0.5, label=tag))
    ax.set_title('Overlay of fully liquid field (L)\nall systems projected on normalized CaO–MgO–Al2O3 base', pad=8)
    fig.legend(handles=handles, loc='center left', bbox_to_anchor=(0.83, 0.5), frameon=True, title='Systems')
    fig.savefig(OUT_DIR / 'overlay_liquid_field_normalized_CAMA.png', bbox_inches='tight')
    fig.savefig(OUT_DIR / 'overlay_liquid_field_normalized_CAMA.svg', bbox_inches='tight')
    plt.close(fig)


def make_overlay_liquidus(system_data: dict):
    fig, ax = plt.subplots(figsize=(SINGLE_COLUMN_MM * MM_TO_INCH * 1.9, SINGLE_COLUMN_MM * MM_TO_INCH * 1.25))
    draw_triangle(ax)
    handles = []
    for tag, color in SYSTEMS:
        _, _, _, segments = system_data[tag]['geom']
        for poly in segments:
            closed = np.vstack([poly, poly[:1]])
            ax.plot(closed[:, 0], closed[:, 1], color=color, lw=0.7, alpha=0.65, zorder=2)
        handles.append(Line2D([0], [0], color=color, lw=2, label=tag))
    ax.set_title('Overlay of liquidus boundary\nL vs L + solid fields on normalized CaO–MgO–Al2O3 base', pad=8)
    fig.legend(handles=handles, loc='center left', bbox_to_anchor=(0.83, 0.5), frameon=True, title='Systems')
    fig.savefig(OUT_DIR / 'overlay_liquidus_boundary_normalized_CAMA.png', bbox_inches='tight')
    fig.savefig(OUT_DIR / 'overlay_liquidus_boundary_normalized_CAMA.svg', bbox_inches='tight')
    plt.close(fig)


def export_metrics(system_data: dict):
    rows = []
    prev_tag = None
    prev_area = None
    for tag, _ in SYSTEMS:
        area, cx, cy = system_data[tag]['metrics']
        cao_c, mgo_c, al2o3_c = xy_to_normalized_cama(cx, cy) if not np.isnan(cx) else (np.nan, np.nan, np.nan)
        area_diff_prev = area - prev_area if prev_area is not None else np.nan
        rows.append({
            'system': tag,
            'liquid_field_area_xy': area,
            'liquid_centroid_x': cx,
            'liquid_centroid_y': cy,
            'liquid_centroid_CaO_star': cao_c,
            'liquid_centroid_MgO_star': mgo_c,
            'liquid_centroid_Al2O3_star': al2o3_c,
            'prev_system': prev_tag,
            'area_difference_vs_prev': area_diff_prev,
        })
        prev_tag = tag
        prev_area = area
    pd.DataFrame(rows).to_csv(OUT_DIR / 'liquid_field_metrics_normalized_CAMA.csv', index=False)


def write_note():
    note = (
        'These comparison plots use a common normalized CAMA base: CaO*, MgO*, Al2O3* = 100 wt.% after renormalizing only the three base oxides.\n'
        'Therefore, axes do not represent total real-system composition; they represent projection on the CaO–MgO–Al2O3 subspace.\n'
        'The fully liquid field overlay uses modal L triangles from the grid-based region reconstruction.\n'
        'The liquidus boundary overlay uses triangles at the L / L+solid transition in the projected grid.\n'
    )
    (OUT_DIR / 'normalized_CAMA_projection_note.txt').write_text(note, encoding='utf-8')


def main():
    system_data = {}
    for tag, color in SYSTEMS:
        df = load_projected_system(tag)
        geom = build_liquid_geometries(df)
        metrics = compute_liquid_metrics(geom[0], geom[2])
        system_data[tag] = {'df': df, 'geom': geom, 'metrics': metrics, 'color': color}
        print(f'OK {tag}: points={len(df)} liquid_area={metrics[0]:.6f}')
    make_overlay_liquid(system_data)
    make_overlay_liquidus(system_data)
    export_metrics(system_data)
    write_note()
    print(f'OK outputs in {OUT_DIR}')

if __name__ == '__main__':
    main()
