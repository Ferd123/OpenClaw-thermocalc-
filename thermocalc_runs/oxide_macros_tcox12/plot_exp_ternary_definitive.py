from __future__ import annotations
import os
import re
from pathlib import Path
from collections import defaultdict

import matplotlib as mpl
import matplotlib.pyplot as plt
import mpltern
import numpy as np
from matplotlib.lines import Line2D

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
    'CAMA_5CAF2': {'CAF2': 5.0, 'SIO2': 0.0},
    'CAMA_5CAF2_1SIO2': {'CAF2': 5.0, 'SIO2': 1.0},
    'CAMA_5CAF2_5SIO2': {'CAF2': 5.0, 'SIO2': 5.0},
    'CAMA_5CAF2_10SIO2': {'CAF2': 5.0, 'SIO2': 10.0},
}
MM_TO_INCH = 1 / 25.4
SINGLE_COLUMN_MM = 85
TERNARY_SCALE = 100.0

mpl.rcParams.update({
    'figure.dpi': 150,
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
    'lines.linewidth': 1.2,
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
PALETTE = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
    '#393b79', '#637939', '#8c6d31', '#843c39', '#7b4173'
]


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


def pretty_phase_text(phases):
    out = []
    for p in phases:
        out.append(PHASE_REMAP.get(p, p.replace('_', ' ')))
    dedup = []
    for p in out:
        if p not in dedup:
            dedup.append(p)
    return ' + '.join(dedup)


def line_to_ternary(seg_xy, fixed):
    pts = []
    for cao, mgo in seg_xy:
        al2o3 = 100.0 - cao - mgo - fixed['CAF2'] - fixed['SIO2']
        if al2o3 < -1e-8:
            continue
        pts.append((al2o3, cao, mgo))
    return pts


def build_color_map(labels):
    uniq = sorted(set(labels))
    cmap = {}
    for i, lab in enumerate(uniq):
        cmap[lab] = PALETTE[i % len(PALETTE)]
    return cmap


def plot_system(tag: str):
    run_dir = BASE / tag
    exp_path = run_dir / f'{tag}_map.exp'
    blocks, labels = parse_exp(exp_path)
    fixed = FIXED[tag]

    line_groups = defaultdict(list)
    for block in blocks:
        label = pretty_phase_text(block['phases'])
        for seg in block['segments']:
            if len(seg) < 2:
                continue
            pts = line_to_ternary(seg, fixed)
            if len(pts) >= 2:
                line_groups[label].append(np.array(pts))

    color_map = build_color_map(line_groups.keys())

    fig = plt.figure(figsize=(SINGLE_COLUMN_MM * MM_TO_INCH * 1.35, SINGLE_COLUMN_MM * MM_TO_INCH * 1.15))
    ax = fig.add_subplot(111, projection='ternary', ternary_sum=TERNARY_SCALE)
    ax.set_tlabel('Al2O3* (wt.%)')
    ax.set_llabel('CaO (wt.%)')
    ax.set_rlabel('MgO (wt.%)')
    ticks = np.arange(0, 101, 10)
    ax.taxis.set_ticks(ticks)
    ax.laxis.set_ticks(ticks)
    ax.raxis.set_ticks(ticks)
    ax.grid(True, linestyle='--', linewidth=0.5, alpha=0.6)

    legend_handles = []
    for label, segs in line_groups.items():
        color = color_map[label]
        for seg in segs:
            t = seg[:, 0]
            l = seg[:, 1]
            r = seg[:, 2]
            ax.plot(t, l, r, color=color, linewidth=1.05, alpha=0.95)
        legend_handles.append(Line2D([0], [0], color=color, lw=1.4, label=label))

    for x, y, text in labels:
        cao = x * 100.0
        mgo = y * 100.0
        al2o3 = 100.0 - cao - mgo - fixed['CAF2'] - fixed['SIO2']
        if al2o3 < 0:
            continue
        pretty = pretty_phase_text(text.split('+'))
        color = color_map.get(pretty, '#333333')
        ax.text(al2o3, cao, mgo, pretty, fontsize=6.0, ha='left', va='bottom', color=color)

    ax.set_title(f'{tag} phase diagram from EXP\nAl2O3* = 100 - CaO - MgO - CaF2 - SiO2', pad=12)
    fig.legend(handles=legend_handles, loc='center left', bbox_to_anchor=(0.98, 0.5), frameon=True, title='Color → phase field')
    plt.tight_layout()
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
