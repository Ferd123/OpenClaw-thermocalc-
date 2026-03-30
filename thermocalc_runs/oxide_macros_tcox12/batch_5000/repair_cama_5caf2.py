from pathlib import Path
import subprocess

BASE = Path(r"C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\oxide_macros_tcox12\batch_5000\CAMA_5CAF2")
POINTS_SMALL = 25
POINTS_FULL = 5000
T = 1873.15
P = 101325
N = 1
DB = "TCOX12"


def generate_points(avail, n_points):
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
    return pts


def make_macro(n_points, out_name):
    stdout_log = BASE / f"{out_name}.stdout.log"
    dat_file = BASE / f"{out_name}_show.dat"
    stdout_log.write_text("", encoding="utf-8")
    dat_file.write_text("", encoding="utf-8")
    pts = generate_points(0.95, n_points)
    lines = [
        "SET_GES_VERSION 6",
        "SET_ECHO",
        f'SET_LOG_FILE "{stdout_log}"',
        "",
        "GO DATA",
        f"SWITCH_DATABASE {DB}",
        "DEFINE_ELEMENTS CA MG AL O F",
        "GET_DATA",
        "",
        "GO P-3",
        "REINITIATE_MODULE",
        "DEFINE_COMPONENTS CAO MGO AL2O3 CAF2 O2",
        "",
        f"SET_CONDITION T={T}",
        f"SET_CONDITION P={P}",
        f"SET_CONDITION N={N}",
        "SET_CONDITION W(CAF2)=0.05000000",
        "",
        f'ADVA OUTPUT_FILE_FOR_SHOW "{dat_file}"',
        "",
    ]
    for idx, (x, y) in enumerate(pts, start=1):
        lines += [
            f"@@ Punto {idx:04d}",
            f"SET_CONDITION W(CAO)={x:.10f}",
            f"SET_CONDITION W(MGO)={y:.10f}",
            "COMPUTE_EQUILIBRIUM",
            "SHOW_VALUE W(CAO) W(MGO) W(AL2O3) W(CAF2)",
            "SHOW_VALUE DVIS(IONIC_LIQ)",
            "SHOW_VALUE NP($)",
            "SHOW_VALUE W($,*)",
            "",
        ]
    lines += ["EXIT", ""]
    p = BASE / f"{out_name}.tcm"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p, dat_file


def run_tc(macro_path):
    runner = BASE / 'run_grid_CAMA_5CAF2.py'
    text = runner.read_text(encoding='utf-8', errors='ignore')
    text = text.replace('grid_CAMA_5CAF2_5000.tcm', macro_path.name)
    temp = BASE / f'run_{macro_path.stem}.py'
    temp.write_text(text, encoding='utf-8')
    subprocess.run(['python', str(temp)], check=True, cwd=str(BASE))


small_macro, small_dat = make_macro(POINTS_SMALL, 'probe_CAMA_5CAF2_25')
run_tc(small_macro)
print(f'PROBE_DAT={small_dat} SIZE={small_dat.stat().st_size}')

full_macro, full_dat = make_macro(POINTS_FULL, 'grid_CAMA_5CAF2_5000_fixed')
run_tc(full_macro)
final_dat = BASE / 'CAMA_5CAF2_grid5000_show.dat'
if full_dat.exists():
    final_dat.write_bytes(full_dat.read_bytes())
print(f'FINAL_DAT={final_dat} SIZE={final_dat.stat().st_size}')
