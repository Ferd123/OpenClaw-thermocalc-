from pathlib import Path
import subprocess, os
run_dir=Path(r'C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\oxide_macros_tcox12\batch_5000\CAMA')
macro=Path(r'C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\oxide_macros_tcox12\batch_5000\CAMA\grid_CAMA_5000.tcm')
exe=Path(r'C:\Program Files\Thermo-Calc\2025a\Console.exe')
env=os.environ.copy(); env.pop('_JAVA_OPTIONS', None)
with macro.open('r', encoding='utf-8', errors='ignore') as fin:
    p=subprocess.run([str(exe)], stdin=fin, cwd=str(run_dir), text=True, capture_output=True, timeout=7200, env=env)
(run_dir / 'grid_CAMA_5000.console.stdout.log').write_text(p.stdout or '', encoding='utf-8', errors='ignore')
(run_dir / 'grid_CAMA_5000.console.stderr.log').write_text(p.stderr or '', encoding='utf-8', errors='ignore')
print('BATCH_RC='+str(p.returncode))
