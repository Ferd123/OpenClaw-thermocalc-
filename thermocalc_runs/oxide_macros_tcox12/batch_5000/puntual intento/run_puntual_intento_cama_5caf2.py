import subprocess
from pathlib import Path
BASE = Path(r"C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\oxide_macros_tcox12\batch_5000\puntual intento")
TCM = BASE / "puntual_intento_cama_5caf2.tcm"
EXE = Path(r"C:\Program Files\Thermo-Calc\2025a\Thermo-Calc.exe")
out = (BASE / 'console.stdout.log').open('w', encoding='utf-8', errors='ignore')
err = (BASE / 'console.stderr.log').open('w', encoding='utf-8', errors='ignore')
try:
    res = subprocess.run([str(EXE), str(TCM)], cwd=str(BASE), stdout=out, stderr=err, text=True)
    print(f'RC={res.returncode}')
finally:
    out.close()
    err.close()
