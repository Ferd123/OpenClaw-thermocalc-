from pathlib import Path

T = 1873.15
P = 101325
N = 1
DB = 'TCOX12'
BASE_DIR = Path(r"C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\oxide_macros_tcox12\maps")
BASE_DIR.mkdir(parents=True, exist_ok=True)

SYSTEMS = [
    {'tag': 'CAMA', 'title': 'CaO-MgO-Al2O3', 'fixed': {}, 'avail': 1.0, 'elements': ['CA','MG','AL','O'], 'defcom': ['CAO','MGO','AL2O3','O2']},
    {'tag': 'CAMA_5CAF2', 'title': 'CaO-MgO-Al2O3-5%CaF2', 'fixed': {'CAF2': 0.05}, 'avail': 0.95, 'elements': ['CA','MG','AL','O','F'], 'defcom': ['CAO','MGO','AL2O3','CAF2','O2']},
    {'tag': 'CAMA_5CAF2_1SIO2', 'title': 'CaO-MgO-Al2O3-5%CaF2-1%SiO2', 'fixed': {'CAF2': 0.05, 'SIO2': 0.01}, 'avail': 0.94, 'elements': ['CA','MG','AL','O','F','SI'], 'defcom': ['CAO','MGO','AL2O3','CAF2','SIO2','O2']},
    {'tag': 'CAMA_5CAF2_5SIO2', 'title': 'CaO-MgO-Al2O3-5%CaF2-5%SiO2', 'fixed': {'CAF2': 0.05, 'SIO2': 0.05}, 'avail': 0.9, 'elements': ['CA','MG','AL','O','F','SI'], 'defcom': ['CAO','MGO','AL2O3','CAF2','SIO2','O2']},
    {'tag': 'CAMA_5CAF2_10SIO2', 'title': 'CaO-MgO-Al2O3-5%CaF2-10%SiO2', 'fixed': {'CAF2': 0.05, 'SIO2': 0.1}, 'avail': 0.85, 'elements': ['CA','MG','AL','O','F','SI'], 'defcom': ['CAO','MGO','AL2O3','CAF2','SIO2','O2']},
]

def fixed_conditions(fixed):
    return [f'S-C W({comp})={val:.8f}' for comp, val in fixed.items()]

def map_macro(sys):
    tag = sys['tag']
    run_dir = BASE_DIR / tag
    run_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = run_dir / f'{tag}_map.stdout.log'
    exp_file = run_dir / f'{tag}_map.exp'
    stdout_log.touch(exist_ok=True)
    exp_file.touch(exist_ok=True)
    elems = ' '.join(sys['elements'])
    defcom = ' '.join(sys['defcom'])
    avail = sys['avail']
    step = avail / 120.0
    seed = avail / 4.0
    jpg = run_dir / f'map_{tag}.jpg'
    lines = [
        'SET_GES_VERSION 6',
        'SET_ECHO',
        f'SET_LOG_FILE "{stdout_log}"',
        '',
        'GO DATA',
        f'SWITCH_DATABASE {DB}',
        f'DEFINE_ELEMENTS {elems}',
        'GET_DATA',
        '',
        'GO P-3',
        'REINITIATE_MODULE',
        f'DEF-COM {defcom}',
        f'S-C T={T}',
        f'S-C P={P}',
        f'S-C N={N}',
        'S-C AC(O2,GAS)=0.2',
    ]
    lines += fixed_conditions(sys['fixed'])
    lines += [
        '',
        'ADVANCED_OPTIONS',
        'GLOBAL_MINIMIZATION',
        'Y',
        '6000',
        '',
        f'SET_AXIS_VARIABLE 1 W(CAO) 0 {avail:.10f} {step:.10f}',
        f'SET_AXIS_VARIABLE 2 W(MGO) 0 {avail:.10f} {step:.10f}',
        f'S-C W(CAO)={seed:.10f}',
        f'S-C W(MGO)={seed:.10f}',
        'SET_ALL_START_VALUES',
        'Y',
        'COMPUTE_EQUILIBRIUM',
        'ADD_INITIAL_EQUILIBRIUM 1>',
        'ADD_INITIAL_EQUILIBRIUM -1>',
        'ADD_INITIAL_EQUILIBRIUM 2>',
        'ADD_INITIAL_EQUILIBRIUM -2>',
        f'SAVE_WORKSPACES "{run_dir / (tag + ".POLY3")}" Y',
        'MAP',
        'POST',
        f'POST:M-E-D FILE "{exp_file}" Y',
        f'DUMP_DIAGRAM JPG "{jpg}"',
        'BACK',
        'EXIT',
        ''
    ]
    return run_dir, '\n'.join(lines)

def main():
    for sys in SYSTEMS:
        run_dir, macro = map_macro(sys)
        fname = run_dir / f'map_{sys["tag"]}_tcox12.tcm'
        fname.write_text(macro, encoding='utf-8')
        print(f'Creado: {fname}')

if __name__ == '__main__':
    main()
