from __future__ import annotations
import math
import re
from pathlib import Path
from collections import defaultdict

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon

BASE = Path(r"C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\oxide_macros_tcox12\maps")
SYSTEMS = [
    'CAMA',
    'CAMA_5CAF2',
    'CAMA_5CAF2_1SIO2',
    'CAMA_5CAF2_5SIO2',
    'CAMA_5CAF2_10SIO2',
]
FIXED = {
    'CAMA': {'CAF2': 0.0, 'SIO2': 0.0},
    'CAMA_5CAF2': {'CAF2': 0.05, 'SIO2': 0.0},
    'CAMA_5CAF2_1SIO2': {'CAF2': 0.05, 'SIO2': 0.01},
    'CAMA_5CAF2_5SIO2': {'CAF2': 0.05, 'SIO2': 0.05},
    'CAMA_5CAF2_10SIO2': {'CAF2': 0.05, 'SIO2': 0.10},
}

SINGLE_COLUMN_MM = 85
DOUBLE_COLUMN_MM = 170
MM_TO_INCH = 1 / 25.4

mpl.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman'],
    'axes.labelsize': 10,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'axes.titlesize': 10,
    'axes.linewidth': 1.0,
    'lines.linewidth': 1.2,
    'xtick.direction': 'inout',
    'ytick.direction': 'inout',
    'xtick.major.size': 4,
    'ytick.major.size': 4,
    'xtick.major.width': 0.8,
    'ytick.major.width': 0.8,
    'figure.dpi': 600,
    'savefig.dpi': 600,
    'svg.fonttype': 'none',
})

BLOCK_START_RE = re.compile(r'^\s*\$ BLOCK')
BLOCK_ID_RE = re.compile(r'\$\s*BLOCK\s*#(\d+)')
PHASE_RE = re.compile(r'^\s*\$(E|F0)\s+(.+)$')
POINT_RE = re.compile(r'^\s*([-+0-9.Ee]+)\s+([-+0-9.Ee]+)')
LABEL_RE = re.compile(r"^\s*([-+0-9.Ee]+)\s+([-+0-9.Ee]+)\s+'(.*)$")

PHASE_REMAP = {
    'IONIC_LIQ#1': 'Líquido',
    'IONIC_LIQ#2': 'Líquido',
    'IONIC_LIQ#3': 'Líquido',
    'HALITE#1': 'MgO',
    'HALITE#2': 'CaO',
    'SPINEL': 'Espinela',
    'C1A2': 'CA2',
    'C1A8M2': 'CA8M2',
    'C2A14M2': 'C2A14M2',
    'C1A6': 'CA6',
    'CORUNDUM': 'Alúmina',
}
PHASE_COLORS = {
    'Líquido': '#1f77b4',
    'MgO': '#ff7f0e',
    'CaO': '#d62728',
    'Espinela': '#2ca02c',
    'CA2': '#9467bd',
    'CA8M2': '#8c564b',
    'C2A14M2': '#e377c2',
    'CA6': '#7f7f7f',
    'Alúmina': '#bcbd22',
}


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
            x = float(pt.group(1))
            y = float(pt.group(2))
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


def stitch_segments_xy(segments, tol=2e-3):
    segs = [np.asarray(s) for s in segments if s is not None and len(s) >= 2]
    used = [False] * len(segs)
    polylines = []
    def close(a, b):
        return np.hypot(a[0]-b[0], a[1]-b[1]) <= tol
    for i in range(len(segs)):
        if used[i]:
            continue
        cur = segs[i].copy()
        used[i] = True
        changed = True
        while changed:
            changed = False
            for j in range(len(segs)):
                if used[j]:
                    continue
                s = segs[j]
                if close(cur[-1], s[0]):
                    cur = np.vstack([cur, s[1:]])
                    used[j] = True
                    changed = True
                elif close(cur[-1], s[-1]):
                    cur = np.vstack([cur, s[-2::-1]])
                    used[j] = True
                    changed = True
                elif close(cur[0], s[-1]):
                    cur = np.vstack([s[:-1], cur])
                    used[j] = True
                    changed = True
                elif close(cur[0], s[0]):
                    cur = np.vstack([s[:0:-1], cur])
                    used[j] = True
                    changed = True
        polylines.append(cur)
    return polylines


def ternary_xy(cao, mgo, al2o3):
    total = cao + mgo + al2o3
    if total <= 0:
        return None
    b = mgo / total
    c = al2o3 / total
    x = 0.5 * (2*b + c)
    y = (math.sqrt(3)/2.0) * c
    return x, y


def draw_triangle(ax):
    h = math.sqrt(3.0)/2.0
    tri = np.array([[0,0],[1,0],[0.5,h],[0,0]])
    ax.plot(tri[:,0], tri[:,1], color='black', linewidth=1.0)
    step = 10
    tick_len = 0.015
    txt_off = 0.035
    for val in range(step, 100, step):
        frac = val/100.0
        p1 = ternary_xy(1-frac, 0, frac)
        p2 = ternary_xy(0, 1-frac, frac)
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color='0.85', linewidth=0.6)
        p1 = ternary_xy(frac, 0, 1-frac)
        p2 = ternary_xy(frac, 1-frac, 0)
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color='0.85', linewidth=0.6)
        p1 = ternary_xy(0, frac, 1-frac)
        p2 = ternary_xy(1-frac, frac, 0)
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color='0.85', linewidth=0.6)
        # base ticks (CaO-MgO edge)
        x, y = ternary_xy(frac, 0, 1-frac)
        ax.plot([x, x], [y, y-tick_len], color='black', linewidth=0.7)
        ax.text(x, y-txt_off, f'{val}', ha='center', va='top', fontsize=10)
        # left edge ticks (CaO)
        x, y = ternary_xy(0, 1-frac, frac)
        ax.text(x-0.03, y, f'{val}', ha='right', va='center', fontsize=10)
        # right edge ticks (MgO)
        x, y = ternary_xy(1-frac, frac, 0)
        ax.text(x+0.03, y, f'{val}', ha='left', va='center', fontsize=10)
    ax.text(-0.08, -0.04, 'CaO', ha='left', va='top', fontsize=13)
    ax.text(1.08, -0.04, 'MgO', ha='right', va='top', fontsize=13)
    ax.text(0.5, h+0.04, 'Al2O3', ha='center', va='bottom', fontsize=13)
    ax.set_aspect('equal')
    ax.set_xlim(-0.08, 1.08)
    ax.set_ylim(-0.06, h+0.08)
    ax.axis('off')
    return tri


def pretty_phase_text(phases):
    out = []
    for p in phases:
        out.append(PHASE_REMAP.get(p, p.replace('_', ' ')))
    dedup = []
    for p in out:
        if p not in dedup:
            dedup.append(p)
    return ' + '.join(dedup)


def color_for_label(label: str):
    for key, color in PHASE_COLORS.items():
        if key in label:
            return color
    return '#333333'


def plot_system(tag: str):
    run_dir = BASE / tag
    exp_path = run_dir / f'{tag}_map.exp'
    blocks, labels = parse_exp(exp_path)
    fixed = FIXED[tag]
    width = DOUBLE_COLUMN_MM * MM_TO_INCH
    fig, ax = plt.subplots(figsize=(width, width))
    triangle = draw_triangle(ax)

    liquid_regions = []
    line_groups = defaultdict(list)

    for block in blocks:
        segs_xy = []
        for seg in block['segments']:
            if len(seg) < 2:
                continue
            pts = []
            for cao, mgo in seg:
                al2o3 = 1.0 - cao - mgo - fixed['CAF2'] - fixed['SIO2']
                if al2o3 < -1e-8:
                    continue
                xy = ternary_xy(cao, mgo, al2o3)
                if xy is not None:
                    pts.append(xy)
            if len(pts) >= 2:
                segs_xy.append(np.array(pts))
        if not segs_xy:
            continue
        key = pretty_phase_text(block['phases'])
        line_groups[key].extend(segs_xy)
        if len(block['phases']) == 1 and 'IONIC_LIQ' in block['phases'][0]:
            liquid_regions.extend(segs_xy)

    for polyline in stitch_segments_xy(liquid_regions, tol=5e-3):
        if len(polyline) < 3:
            continue
        if np.hypot(polyline[0,0]-polyline[-1,0], polyline[0,1]-polyline[-1,1]) > 5e-3:
            continue
        poly = Polygon(polyline, closed=True, facecolor='#ADD8E6', edgecolor='none', alpha=0.22, zorder=0)
        tri_patch = Polygon(triangle[:3], closed=True, transform=ax.transData)
        poly.set_clip_path(tri_patch)
        ax.add_patch(poly)

    for label, segs in line_groups.items():
        color = color_for_label(label)
        for seg in segs:
            ax.plot(seg[:,0], seg[:,1], color=color, linewidth=1.1, alpha=0.95)

    for x, y, text in labels:
        al2o3 = 1.0 - x - y - fixed['CAF2'] - fixed['SIO2']
        if al2o3 < 0:
            continue
        xy = ternary_xy(x, y, al2o3)
        if xy is None:
            continue
        pretty = pretty_phase_text(text.split('+'))
        ax.text(xy[0], xy[1], pretty, fontsize=6.2, ha='center', va='center',
                color=color_for_label(pretty),
                bbox=dict(facecolor='white', alpha=0.68, edgecolor='none', pad=0.35), zorder=10)

    title = f'{tag} phase diagram from EXP\nAl2O3* = 1 - CaO - MgO - CaF2 - SiO2'
    ax.set_title(title, fontsize=10)
    out_png = run_dir / f'{tag}_exp_ternary_definitive.png'
    out_svg = run_dir / f'{tag}_exp_ternary_definitive.svg'
    fig.savefig(out_png, bbox_inches='tight')
    fig.savefig(out_svg, bbox_inches='tight')
    plt.close(fig)
    print(f'OK {tag}: {out_png.name}, {out_svg.name}')


def main():
    for tag in SYSTEMS:
        plot_system(tag)

if __name__ == '__main__':
    main()
