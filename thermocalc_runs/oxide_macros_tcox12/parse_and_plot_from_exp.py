from __future__ import annotations
from pathlib import Path
import re
import math
import matplotlib.pyplot as plt

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

BLOCK_START_RE = re.compile(r'^\s*\$ BLOCK')
PHASE_RE = re.compile(r'^\s*\$(E|F0)\s+(.+)$')
POINT_RE = re.compile(r'^\s*([-+0-9.Ee]+)\s+([-+0-9.Ee]+)')


def ternary_xy(cao, mgo, al2o3):
    total = cao + mgo + al2o3
    if total <= 0:
        return math.nan, math.nan
    a = cao / total
    b = mgo / total
    c = al2o3 / total
    x = 0.5 * (2 * b + c)
    y = (math.sqrt(3) / 2.0) * c
    return x, y


def parse_exp(path: Path):
    blocks = []
    current = None
    for raw in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = raw.rstrip('\n')
        if BLOCK_START_RE.match(line):
            if current:
                blocks.append(current)
            current = {'phases': [], 'points': []}
            continue
        if current is None:
            continue
        if line.strip() == 'BLOCKEND':
            blocks.append(current)
            current = None
            continue
        pm = PHASE_RE.match(line)
        if pm:
            current['phases'].append(pm.group(2).strip())
            continue
        pt = POINT_RE.match(line)
        if pt:
            try:
                x = float(pt.group(1))
                y = float(pt.group(2))
                current['points'].append((x, y))
            except Exception:
                pass
    if current:
        blocks.append(current)
    return blocks


def plot_system(tag: str):
    run_dir = BASE / tag
    exp_path = run_dir / f'{tag}_map.exp'
    if not exp_path.exists():
        print(f'Falta EXP: {exp_path}')
        return
    blocks = parse_exp(exp_path)
    fixed = FIXED[tag]
    fig, ax = plt.subplots(figsize=(8, 7), constrained_layout=True)
    triangle_x = [0, 1, 0.5, 0]
    triangle_y = [0, 0, math.sqrt(3)/2, 0]
    ax.plot(triangle_x, triangle_y, color='black', lw=1.2)

    n_drawn = 0
    for blk in blocks:
        pts = blk['points']
        if len(pts) < 2:
            continue
        xs, ys = [], []
        for cao, mgo in pts:
            al2o3 = 1.0 - cao - mgo - fixed['CAF2'] - fixed['SIO2']
            x, y = ternary_xy(cao, mgo, al2o3)
            xs.append(x)
            ys.append(y)
        label = ' + '.join(blk['phases'][:4]) if blk['phases'] else None
        ax.plot(xs, ys, lw=1.0, alpha=0.95)
        n_drawn += 1

    ax.text(-0.03, -0.04, 'CaO', fontsize=11)
    ax.text(1.01, -0.04, 'MgO', fontsize=11, ha='right')
    ax.text(0.5, math.sqrt(3)/2 + 0.03, 'Al2O3*', fontsize=11, ha='center')
    ax.set_title(f'{tag} phase boundaries from EXP\n* Al2O3 ternario = 1 - CaO - MgO - CaF2 - SiO2\nblocks drawn={n_drawn}')
    ax.set_aspect('equal')
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, math.sqrt(3)/2 + 0.08)
    ax.axis('off')
    out_png = run_dir / f'{tag}_exp_ternary_boundaries.png'
    fig.savefig(out_png, dpi=220)
    plt.close(fig)
    print(f'OK {tag}: {out_png.name} blocks={n_drawn}')


def main():
    for tag in SYSTEMS:
        plot_system(tag)

if __name__ == '__main__':
    main()
