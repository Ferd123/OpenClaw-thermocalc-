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
    'figure.dpi': 200,
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
    rows, current = [], {}
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
        data.append({'cao_n': cao_n, 'mgo_n': mgo_n, 'al2o3_n': al2o3_n, 'x': x, 'y': y, 'assemblage': assemblage, 'is_L': assemblage == 'L'})
    return pd.DataFrame(data).dropna(subset=['x', 'y']).reset_index(drop=True)


def build_liquid_geometries(df: pd.DataFrame):
    tri = Triangulation(df['x'].to_numpy(), df['y'].to_numpy())
    tri_rows = []
    liquid_segments = []
    for tidx, verts in enumerate(tri.triangles):
        labs = df.iloc[verts]['assemblage'].tolist()
        counts = Counter(labs)
        modal, n = counts.most_common(1)[0]
        is_L_modal = (modal == 'L') and (n >= 2)
        cx = float(df.iloc[verts]['x'].mean())
        cy = float(df.iloc[verts]['y'].mean())
        tri_rows.append({'triangle_id': tidx, 'modal': modal, 'is_L_modal': is_L_modal, 'cx': cx, 'cy': cy})
        has_L = any(l == 'L' for l in labs)
        has_nonL = any(l != 'L' for l in labs)
        if has_L and has_nonL:
            pts = np.column_stack([tri.x[verts], tri.y[verts]])
            liquid_segments.append(pts)
    tri_df = pd.DataFrame(tri_rows)
    liquid_triangles = tri_df[tri_df['is_L_modal']]['triangle_id'].to_numpy(dtype=int)
    return tri, tri_df, liquid_triangles, liquid_segments


def triangle_area(poly: np.ndarray) -> float:
    x = poly[:, 0]; y = poly[:, 1]
    return 0.5 * abs(x[0]*(y[1]-y[2]) + x[1]*(y[2]-y[0]) + x[2]*(y[0]-y[1]))


def compute_liquid_metrics(tri, liquid_triangles):
    areas, centroids = [], []
    for tid in liquid_triangles:
        verts = tri.triangles[int(tid)]
        poly = np.column_stack([tri.x[verts], tri.y[verts]])
        area = triangle_area(poly)
        centroid = poly.mean(axis=0)
        areas.append(area); centroids.append(centroid)
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


def setup_axes(fig):
    ax = fig.add_subplot(111)
    ax.set_aspect('equal')
    ax.set_xlim(-0.05, 1.32)
    ax.set_ylim(-0.05, H + 0.09)
    ax.axis('off')
    return ax


def draw_triangle(ax):
    tri = np.array([[0, 0], [1, 0], [0.5, H], [0, 0]])
    ax.plot(tri[:, 0], tri[:, 1], color='black', lw=1.25, zorder=5)
    for val in range(10, 100, 10):
        frac = val / 100.0
        ax.plot([0.5 * frac, 1 - 0.5 * frac], [H * frac, H * frac], color='0.90', lw=0.32, zorder=0)
        ax.plot([frac, 0.5 + 0.5 * frac], [0, H * (1 - frac)], color='0.90', lw=0.32, zorder=0)
        ax.plot([1 - frac, 0.5 * (1 - frac)], [0, H * (1 - frac)], color='0.90', lw=0.32, zorder=0)
    ax.text(-0.03, -0.035, 'CaO* (wt.%)', fontsize=10, ha='left', va='top')
    ax.text(1.03, -0.035, 'MgO* (wt.%)', fontsize=10, ha='right', va='top')
    ax.text(0.5, H + 0.03, 'Al2O3* (wt.%)', fontsize=10, ha='center', va='bottom')
    ax.text(0.5, H + 0.055, 'Normalized CaO–MgO–Al2O3 basis', fontsize=8, ha='center', va='bottom', color='0.35')
    for val in range(10, 100, 10):
        frac = val / 100.0
        ax.text(frac, -0.025, f'{val}', fontsize=8, ha='center', va='top')
        ax.text(0.5 * frac - 0.018, H * frac, f'{val}', fontsize=7, ha='right', va='center')
        ax.text(1 - 0.5 * frac + 0.018, H * frac, f'{val}', fontsize=7, ha='left', va='center')


def chaikin(points, n_iter=2):
    pts = np.asarray(points, dtype=float)
    if len(pts) < 3:
        return pts
    closed = np.vstack([pts, pts[:1]])
    for _ in range(n_iter):
        new_pts = []
        for i in range(len(closed) - 1):
            p = closed[i]; q = closed[i + 1]
            new_pts.append(0.75 * p + 0.25 * q)
            new_pts.append(0.25 * p + 0.75 * q)
        closed = np.vstack([new_pts, new_pts[0]])
    return closed[:-1]


def make_overlay_liquid(system_data: dict):
    fig = plt.figure(figsize=(SINGLE_COLUMN_MM * MM_TO_INCH * 2.15, SINGLE_COLUMN_MM * MM_TO_INCH * 1.45))
    ax = setup_axes(fig)
    draw_triangle(ax)
    handles = []
    centroids = []
    for tag, color in SYSTEMS:
        tri, _, liquid_triangles, _ = system_data[tag]['geom']
        polys = []
        for tid in liquid_triangles:
            verts = tri.triangles[int(tid)]
            polys.append(np.column_stack([tri.x[verts], tri.y[verts]]))
        if polys:
            pc = PolyCollection(polys, facecolors=color, edgecolors='none', alpha=0.10, zorder=1)
            ax.add_collection(pc)
            for poly in polys[:]:
                closed = np.vstack([poly, poly[:1]])
                ax.plot(closed[:, 0], closed[:, 1], color=color, lw=0.45, alpha=0.22, zorder=2)
        area, cx, cy = system_data[tag]['metrics']
        if not np.isnan(cx):
            ax.plot(cx, cy, marker='o', color=color, markersize=3.6, zorder=4)
            centroids.append((tag, cx, cy, color))
        handles.append(Line2D([0], [0], color=color, lw=2.2, label=tag))
    if len(centroids) >= 2:
        xs = [c[1] for c in centroids]; ys = [c[2] for c in centroids]
        ax.plot(xs, ys, color='0.25', lw=0.7, ls='--', alpha=0.7, zorder=3)
    ax.set_title('Fully liquid field (L) overlay', pad=4)
    fig.text(0.5, 0.93, 'Projection on normalized CaO–MgO–Al2O3 basis', ha='center', va='center', fontsize=8, color='0.35')
    fig.legend(handles=handles, loc='center left', bbox_to_anchor=(0.83, 0.53), frameon=True, title='Systems')
    fig.savefig(OUT_DIR / 'overlay_L_field_normalized_CAMA_paper.png', bbox_inches='tight')
    fig.savefig(OUT_DIR / 'overlay_L_field_normalized_CAMA_paper.svg', bbox_inches='tight')
    plt.close(fig)


def make_overlay_liquidus(system_data: dict):
    fig = plt.figure(figsize=(SINGLE_COLUMN_MM * MM_TO_INCH * 2.15, SINGLE_COLUMN_MM * MM_TO_INCH * 1.45))
    ax = setup_axes(fig)
    draw_triangle(ax)
    handles = []
    for tag, color in SYSTEMS:
        _, _, _, segments = system_data[tag]['geom']
        for poly in segments:
            sm = chaikin(poly, n_iter=2)
            closed = np.vstack([sm, sm[:1]])
            ax.plot(closed[:, 0], closed[:, 1], color=color, lw=1.1, alpha=0.92, zorder=2)
        handles.append(Line2D([0], [0], color=color, lw=2.0, label=tag))
    ax.set_title('Liquidus boundary overlay', pad=4)
    fig.text(0.5, 0.93, 'Projection on normalized CaO–MgO–Al2O3 basis', ha='center', va='center', fontsize=8, color='0.35')
    fig.legend(handles=handles, loc='center left', bbox_to_anchor=(0.83, 0.53), frameon=True, title='Systems')
    fig.savefig(OUT_DIR / 'overlay_liquidus_normalized_CAMA_paper.png', bbox_inches='tight')
    fig.savefig(OUT_DIR / 'overlay_liquidus_normalized_CAMA_paper.svg', bbox_inches='tight')
    plt.close(fig)


def make_control(system_data: dict):
    fig = plt.figure(figsize=(SINGLE_COLUMN_MM * MM_TO_INCH * 2.15, SINGLE_COLUMN_MM * MM_TO_INCH * 1.45))
    ax = setup_axes(fig)
    draw_triangle(ax)
    handles = []
    for tag, color in SYSTEMS:
        tri, _, liquid_triangles, segments = system_data[tag]['geom']
        polys = []
        for tid in liquid_triangles:
            verts = tri.triangles[int(tid)]
            polys.append(np.column_stack([tri.x[verts], tri.y[verts]]))
        if polys:
            ax.add_collection(PolyCollection(polys, facecolors=color, edgecolors='none', alpha=0.08, zorder=1))
        for poly in segments:
            closed = np.vstack([poly, poly[:1]])
            ax.plot(closed[:, 0], closed[:, 1], color=color, lw=0.5, alpha=0.55, zorder=2)
        df = system_data[tag]['df']
        ax.scatter(df.loc[df['is_L'], 'x'], df.loc[df['is_L'], 'y'], s=2, color=color, alpha=0.06, zorder=1)
        area, cx, cy = system_data[tag]['metrics']
        if not np.isnan(cx):
            ax.plot(cx, cy, marker='o', color=color, markersize=3.2, zorder=4)
        handles.append(Line2D([0], [0], color=color, lw=1.6, label=tag))
    ax.set_title('Control view: liquid-field support and liquidus discretization', pad=4)
    fig.legend(handles=handles, loc='center left', bbox_to_anchor=(0.83, 0.53), frameon=True, title='Systems')
    fig.savefig(OUT_DIR / 'overlay_normalized_CAMA_control.png', bbox_inches='tight')
    plt.close(fig)


def export_metrics(system_data: dict):
    base_area, base_cx, base_cy = system_data['CAMA']['metrics']
    rows = []
    for tag, _ in SYSTEMS:
        area, cx, cy = system_data[tag]['metrics']
        cao_c, mgo_c, al2o3_c = xy_to_normalized_cama(cx, cy) if not np.isnan(cx) else (np.nan, np.nan, np.nan)
        delta_area = area - base_area
        centroid_shift = math.hypot(cx - base_cx, cy - base_cy) if not np.isnan(cx) else np.nan
        overlap = min(area, base_area)
        gained = max(area - overlap, 0.0)
        lost = max(base_area - overlap, 0.0)
        rows.append({
            'system': tag,
            'projected_L_area': area,
            'centroid_CaO_star': cao_c,
            'centroid_MgO_star': mgo_c,
            'centroid_Al2O3_star': al2o3_c,
            'delta_area_vs_base': delta_area,
            'centroid_shift_vs_base': centroid_shift,
            'overlap_area_vs_base': overlap,
            'gained_area_vs_base': gained,
            'lost_area_vs_base': lost,
        })
    pd.DataFrame(rows).to_csv(OUT_DIR / 'normalized_CAMA_liquid_field_metrics.csv', index=False)


def write_note():
    note = (
        'The renormalization and comparison logic were preserved exactly: CaO*, MgO*, Al2O3* are computed by renormalizing only the CAMA base oxides to 100 wt.%.\n'
        'Visual refinements only: larger ternary footprint, tighter layout, clearer contour hierarchy, softer liquid fill, and smoother liquidus presentation.\n'
        'A mild geometric smoothing (Chaikin, 2 iterations) was applied only to the liquidus display curves to reduce discretization jaggedness; the underlying physics and classification were not changed.\n'
        'Quantitative comparison includes projected liquid-field area, centroid on normalized basis, delta area vs base, centroid shift vs base, and simple overlap/gained/lost area proxies vs the base system.\n'
    )
    (OUT_DIR / 'normalized_CAMA_render_note.txt').write_text(note, encoding='utf-8')


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
    make_control(system_data)
    export_metrics(system_data)
    write_note()
    print(f'OK outputs in {OUT_DIR}')

if __name__ == '__main__':
    main()
