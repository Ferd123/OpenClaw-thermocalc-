from __future__ import annotations
from pathlib import Path
import re
import math
import csv
import pandas as pd
import matplotlib.pyplot as plt

BASE = Path(r"C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\oxide_macros_tcox12\batch_5000")
SYSTEMS = [
    'CAMA',
    'CAMA_5CAF2',
    'CAMA_5CAF2_1SIO2',
    'CAMA_5CAF2_5SIO2',
    'CAMA_5CAF2_10SIO2',
]

PAIR_RE = re.compile(r'([A-Z0-9_#]+\([^)]*\)|[A-Z0-9_#]+)=([0-9.E+-]+|0\.)')


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


def to_master_csv(rows, out_csv: Path):
    fieldnames = sorted({k for row in rows for k in row.keys()})
    with out_csv.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


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


def make_plot(csv_path: Path, out_png: Path, title: str):
    df = pd.read_csv(csv_path)
    for col in ['W(CAO)', 'W(MGO)']:
        if col not in df.columns:
            raise ValueError(f'Falta columna {col} en {csv_path.name}')
    df['W(CAF2)'] = pd.to_numeric(df.get('W(CAF2)', 0), errors='coerce').fillna(0.0)
    df['W(SIO2)'] = pd.to_numeric(df.get('W(SIO2)', 0), errors='coerce').fillna(0.0)
    df['W(CAO)'] = pd.to_numeric(df['W(CAO)'], errors='coerce')
    df['W(MGO)'] = pd.to_numeric(df['W(MGO)'], errors='coerce')
    df['W(AL2O3)_ternary'] = 1.0 - df['W(CAO)'] - df['W(MGO)'] - df['W(CAF2)'] - df['W(SIO2)']
    xy = df.apply(lambda r: ternary_xy(r['W(CAO)'], r['W(MGO)'], r['W(AL2O3)_ternary']), axis=1)
    df['x'] = [p[0] for p in xy]
    df['y'] = [p[1] for p in xy]

    color_col = 'DVIS(IONIC_LIQ#1)' if 'DVIS(IONIC_LIQ#1)' in df.columns else None
    if color_col:
        df[color_col] = pd.to_numeric(df[color_col], errors='coerce')

    fig, ax = plt.subplots(figsize=(8, 7), constrained_layout=True)
    triangle_x = [0, 1, 0.5, 0]
    triangle_y = [0, 0, math.sqrt(3)/2, 0]
    ax.plot(triangle_x, triangle_y, color='black', lw=1.2)
    if color_col:
        sc = ax.scatter(df['x'], df['y'], c=df[color_col], s=10, cmap='viridis', alpha=0.85)
        cbar = plt.colorbar(sc, ax=ax)
        cbar.set_label(color_col)
    else:
        ax.scatter(df['x'], df['y'], s=10, color='#3366cc', alpha=0.85)
    ax.text(-0.03, -0.04, 'CaO', fontsize=11)
    ax.text(1.01, -0.04, 'MgO', fontsize=11, ha='right')
    ax.text(0.5, math.sqrt(3)/2 + 0.03, 'Al2O3*', fontsize=11, ha='center')
    ax.set_title(title + '\n* Al2O3 ternario = 1 - CaO - MgO - CaF2 - SiO2')
    ax.set_aspect('equal')
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, math.sqrt(3)/2 + 0.08)
    ax.axis('off')
    fig.savefig(out_png, dpi=220)
    plt.close(fig)


def main():
    for tag in SYSTEMS:
        run_dir = BASE / tag
        dat_path = run_dir / f'{tag}_grid5000_show.dat'
        if not dat_path.exists():
            print(f'Falta DAT: {dat_path}')
            continue
        rows = parse_dat(dat_path)
        out_csv = run_dir / f'{tag}_grid5000_master.csv'
        to_master_csv(rows, out_csv)
        out_png = run_dir / f'{tag}_ternary_dvis.png'
        make_plot(out_csv, out_png, f'{tag} ternary map')
        print(f'OK {tag}: rows={len(rows)} csv={out_csv.name} png={out_png.name}')

if __name__ == '__main__':
    main()
