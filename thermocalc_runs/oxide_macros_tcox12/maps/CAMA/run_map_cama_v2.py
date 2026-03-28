from pathlib import Path
import subprocess, os
run_dir=Path(r'C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\oxide_macros_tcox12\maps\CAMA')
macro=run_dir / 'map_CAMA_tcox12_v2.tcm'
exe=Path(r'C:\Program Files\Thermo-Calc\2025a\Console.exe')
env=os.environ.copy(); env.pop('_JAVA_OPTIONS', None)
with macro.open('r', encoding='utf-8', errors='ignore') as fin:
    p=subprocess.run([str(exe)], stdin=fin, cwd=str(run_dir), text=True, capture_output=True, timeout=1800, env=env)
(run_dir / 'map_CAMA_tcox12_v2.console.stdout.log').write_text(p.stdout or '', encoding='utf-8', errors='ignore')
(run_dir / 'map_CAMA_tcox12_v2.console.stderr.log').write_text(p.stderr or '', encoding='utf-8', errors='ignore')
print('RC='+str(p.returncode))
