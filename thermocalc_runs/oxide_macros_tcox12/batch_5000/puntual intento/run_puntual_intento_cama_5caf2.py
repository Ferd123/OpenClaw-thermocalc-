import subprocess
from pathlib import Path
BASE = Path(r"C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\oxide_macros_tcox12\batch_5000\puntual intento")
TCM = BASE / "puntual_intento_cama_5caf2.tcm"
EXE = Path(r"C:\Program Files\Thermo-Calc\2025b\Thermo-Calc.exe")
if not EXE.exists():
    EXE = Path(r"C:\Program Files\Thermo-Calc\2024b\Thermo-Calc.exe")
res = subprocess.run([str(EXE), str(TCM)], cwd=str(BASE), capture_output=True, text=True)
(BASE / 'console.stdout.log').write_text(res.stdout, encoding='utf-8', errors='ignore')
(BASE / 'console.stderr.log').write_text(res.stderr, encoding='utf-8', errors='ignore')
print(f'RC={res.returncode}')
