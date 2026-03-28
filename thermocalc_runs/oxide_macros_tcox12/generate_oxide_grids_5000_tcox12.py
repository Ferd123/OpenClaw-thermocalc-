from pathlib import Path

T = 1873.15
P = 101325
N = 1
DB = "TCOX12"
POINTS = 5000
BASE_DIR = Path(r"C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\oxide_macros_tcox12\batch_5000")
BASE_DIR.mkdir(parents=True, exist_ok=True)

SYSTEMS = [
    {'tag': 'CAMA', 'title': 'CaO-MgO-Al2O3', 'fixed': {}, 'avail': 1.0, 'components': ['CAO', 'MGO', 'AL2O3']},
    {'tag': 'CAMA_5CAF2', 'title': 'CaO-MgO-Al2O3-5%CaF2', 'fixed': {'CAF2': 0.05}, 'avail': 0.95, 'components': ['CAO', 'MGO', 'AL2O3', 'CAF2']},
    {'tag': 'CAMA_5CAF2_1SIO2', 'title': 'CaO-MgO-Al2O3-5%CaF2-1%SiO2', 'fixed': {'CAF2': 0.05, 'SIO2': 0.01}, 'avail': 0.94, 'components': ['CAO', 'MGO', 'AL2O3', 'CAF2', 'SIO2']},
    {'tag': 'CAMA_5CAF2_5SIO2', 'title': 'CaO-MgO-Al2O3-5%CaF2-5%SiO2', 'fixed': {'CAF2': 0.05, 'SIO2': 0.05}, 'avail': 0.9, 'components': ['CAO', 'MGO', 'AL2O3', 'CAF2', 'SIO2']},
    {'tag': 'CAMA_5CAF2_10SIO2', 'title': 'CaO-MgO-Al2O3-5%CaF2-10%SiO2', 'fixed': {'CAF2': 0.05, 'SIO2': 0.1}, 'avail': 0.85, 'components': ['CAO', 'MGO', 'AL2O3', 'CAF2', 'SIO2']},
]

def fixed_conditions(fixed):
    return [f'SET_CONDITION W({comp})={val:.8f}' for comp, val in fixed.items()]

def generate_points_exact(avail, n_points=5000):
    nx = 100
    ny = 100
    xs = [avail * i / (nx - 1) for i in range(nx)]
    ys = [avail * j / (ny - 1) for j in range(ny)]
    pts = []
    for y in ys:
        for x in xs:
            if x + y <= avail + 1e-12:
                pts.append((x, y))
                if len(pts) == n_points:
                    return pts
    raise RuntimeError('No se pudieron generar 5000 puntos factibles.')

def show_values(sys):
    comps = ['CAO', 'MGO', 'AL2O3']
    if 'CAF2' in sys['components']:
        comps.append('CAF2')
    if 'SIO2' in sys['components']:
        comps.append('SIO2')
    comp_line = ' '.join([f'W({c})' for c in comps])
    return [
        f'SHOW_VALUE {comp_line}',
        'SHOW_VALUE DVIS(IONIC_LIQ)',
        'SHOW_VALUE NP($)',
        'SHOW_VALUE W($,*)',
    ]

def grid_macro(sys):
    tag = sys['tag']
    run_dir = BASE_DIR / tag
    run_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = run_dir / f'{tag}_grid5000.stdout.log'
    dat_file = run_dir / f'{tag}_grid5000_show.dat'
    stdout_log.touch(exist_ok=True)
    dat_file.touch(exist_ok=True)
    comps_define = ' '.join(sys['components'])
    lines = [
        'SET_GES_VERSION 6',
        'SET_ECHO',
        f'SET_LOG_FILE "{stdout_log}"',
        '',
        'GO DATA',
        f'SWITCH_DATABASE {DB}',
        'DEFINE_ELEMENTS CA MG AL O F SI',
        'GET_DATA',
        '',
        'GO P-3',
        'REINITIATE_MODULE',
        f'DEFINE_COMPONENTS {comps_define}',
        '',
        f'SET_CONDITION T={T}',
        f'SET_CONDITION P={P}',
        f'SET_CONDITION N={N}',
        'SET_CONDITION AC(O2,GAS)=0.2',
    ]
    lines += fixed_conditions(sys['fixed'])
    lines += [
        '',
        f'ADVA OUTPUT_FILE_FOR_SHOW "{dat_file}"',
        '',
        'SET_CONDITION W(CAO)=0',
        'SET_CONDITION W(MGO)=0',
        'COMPUTE_EQUILIBRIUM',
        '',
    ]
    pts = generate_points_exact(sys['avail'], POINTS)
    for idx, (x, y) in enumerate(pts, start=1):
        lines += [
            f'@@ Punto {idx:04d}',
            f'SET_CONDITION W(CAO)={x:.10f}',
            f'SET_CONDITION W(MGO)={y:.10f}',
            'COMPUTE_EQUILIBRIUM',
        ]
        lines += show_values(sys)
        lines += ['']
    lines += ['EXIT', '']
    return run_dir, '\n'.join(lines)

def main():
    for sys in SYSTEMS:
        run_dir, macro = grid_macro(sys)
        fname = run_dir / f'grid_{sys["tag"]}_5000.tcm'
        fname.write_text(macro, encoding='utf-8')
        print(f'Creado: {fname}')

if __name__ == '__main__':
    main()
