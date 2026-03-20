# thermocalc_agent

## Objetivo
Notas operativas para correr Thermo-Calc Console Mode 2025a en batch para el sistema de escoria con Fe usando TCOX12, extraer propiedades, parsear salida y evitar errores ya detectados.

---

## Entorno confirmado
- Thermo-Calc: `C:\Program Files\Thermo-Calc\2025a\Console.exe`
- Base de datos: `TCOX12`
- Modo usado: `Console Mode` + `POLY` (`go p-3`)
- Patrón de ejecución que sí funciona:
  - correr `Console.exe` **sin argumentos**
  - pasar el macro `.tcm` por **stdin**
  - usar `cwd` = carpeta de corrida
  - capturar `stdout/stderr` a log al final

### Patrón Python validado
```python
with macro.open("r", encoding="utf-8", errors="ignore") as fin:
    proc = subprocess.run(
        [TC_CONSOLE_EXE],
        stdin=fin,
        cwd=str(run_dir),
        text=True,
        capture_output=True,
        timeout=timeout_s,
        env=env,
    )
```

### Entorno
- conviene hacer:
```python
env = os.environ.copy()
env.pop("_JAVA_OPTIONS", None)
```

---

## Sistema termodinámico actual
### Elementos
```text
CA MG SI AL MN FE O
```

### Condiciones base
```text
T = 1873 K
P = 101325 Pa
N = 1
W(AL)=0.0423408
W(MN)=0.03098
W(CA)=0.21441
X(O)-X(CA)-X(MG)-X(FE)-X(MN)-1.5*X(AL)-2*X(SI)=0
W(SI)=NONE
```

### Fases suspendidas
```text
BCC_A2
FCC_A1
HCP_A3
```

---

## Sintaxis que sí funcionó en esta instalación
La consola aceptó tanto sintaxis larga como legacy en varios casos, pero el patrón más estable fue el **legacy**:

```text
set-echo
set-log ...
go data
sw tcox12
def-el
...
get
go p-3
reinitiate_module
s-c ...
c-s ...
c-e
show_value ...
exit
```

---

## Cosas que NO hacer
### 1. No usar `Console.exe archivo.tcm`
Eso causó problemas. Lo correcto es usar stdin.

### 2. No usar `OUTPUT_FILE_FOR_SHOW` en modo interactivo
Lo que falla es el flujo interactivo tipo:
```text
advanced_options
output_file_for_show
archivo.dat
```
Eso:
- abre ventana o prompt
- puede romper la sesión
- puede terminar en errores tipo `fort.53` / permisos / cuelgues

### 3. No confiar en saltos grandes en composición
Thermo-Calc/POLY no es robusto a saltos grandes.

Comportamiento observado:
- si no converge
- **no actualiza el estado**
- `SHOW_VALUE` devuelve el **último equilibrio válido**

Esto obliga a validar convergencia de manera implícita comparando input vs estado reportado.

---

## Estrategia batch correcta
### Exportación robusta
Usar:
- `SHOW_VALUE`
- delimitadores por punto
- log normal (`set-log` / log batch-safe)
- parseo externo posterior

### Delimitadores validados
```text
show_value "POINT_ID=0001_BEGIN"
...
show_value "POINT_ID=0001"
...
show_value "POINT_ID=0001_END"
```

Esto sí salió en el log y sí se pudo parsear.

---

## Propiedades reevaluadas
### Sí funcionan
#### Propiedades puntuales
- `W(FE)`
- `W(MG)`
- `W(SI)`
- `W(CA)`
- `W(AL)`
- `W(MN)`
- `DVIS(IONIC_LIQ#1)`
- `DVIS(IONIC_LIQ#2)`
- `DVIS(IONIC_LIQ#3)`
- `SURF(IONIC_LIQ#1/#2/#3)` **cuando la sesión arranca bien en GES6**
- `NP(IONIC_LIQ#1/#2/#3)`
- `BP(IONIC_LIQ#1/#2/#3)`
- `VP(IONIC_LIQ#1/#2/#3)`
- `NP(*)`
- `BP(*)`
- `VP(*)`
- `NP($)`
- `BP($)`
- `VP($)`
- `BV`
- `VP(phase)` para fases individuales, por ejemplo `VP(HALITE#1)`

### No funcionan o no son útiles en este modo
- `SURF(...)` falla si la sesión efectiva cae en `GES5`
- `DS(...)` → `NO SUCH STATE VARIABLE: DS`
- `NV(IONIC_LIQ#k)` no sirve como volumen de fase en este contexto
- `NV(*)` devolvió salidas a nivel componente/otra variable, no usarlo para `phi_s`
- `NP($)` / `BP($)` / `VP($)` sí fueron validados después como útiles en el flujo correcto

---

## Hallazgos clave sobre superficie y densidad
### Surface tension
Diagnóstico refinado:
- `SURF(...)` **falla en sesiones que quedan en GES5** con error:
  - `Property SURF not supported in GES5`
- pero **sí funciona** cuando se arranca limpio con:
  - `set-ges-version 6`
  - `go data`
  - `sw data`
  - `tcox12`
  - `def-el ...`
  - `get`
  - `go p-3`
- por tanto, `SURF(...)` no debe considerarse universalmente roto; depende del arranque/engine efectivo de la sesión

### Densidad
`DS(...)` no funciona directo.

Ruta correcta:
- reconstruir densidad usando `BP/VP`

Ejemplos:
```text
rho_phase = BP_phase / VP_phase
rho_liq = BP_liq / VP_liq
rho_mix = sum(BP_i) / sum(VP_i)
```

Usar con cuidado revisando unidades internas consistentes del output.

---

## Resultados relevantes ya obtenidos
### Corrida de 5000 puntos sin SURF
Archivos en:
`C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\run_2026-03-18_183915`

#### Generados
- `transport_5000pts_nosurf.tcm`
- `transport_5000pts_nosurf.stdout.log`
- `tc_points_summary_from_log.csv`
- `tc_phase_fractions_long_from_log.csv`
- `tc_points_final_enriched.csv`
- `audit_output_from_log\...`

#### Estado
- 5000 puntos corridos
- parser batch funcionando
- composición y viscosidad extraídas

### Error detectado en esa corrida
Se perdió la información de sólidos en el CSV final porque el macro de esa corrida solo extrajo explícitamente propiedades de `IONIC_LIQ#1/#2/#3` y no dejó bien capturadas todas las fases estables para postproceso sólido.

Importante:
- **eso NO significa que no haya sólidos en el sistema**
- solo que la extracción fue incompleta

---

## Verificación contra `slag foaming`
Carpeta:
`C:\Users\ELANOR\Documents\slag foaming`

### Hechos confirmados
- `datosparaVisc.dat` sí contiene fases sólidas
- fases detectadas en el flujo viejo:
  - `HALITE#1`
  - `HALITE#2`
  - `CA2SIO4_ALPHA_A`
  - `IONIC_LIQ#1`
  - `IONIC_LIQ#2`
  - `IONIC_LIQ#3`
- en el CSV viejo:
  - `nonzero solids = 3443`
  - `solid_fraction_mass max ≈ 0.6577`

Esto demuestra que el sistema sí tiene zonas con sólidos en el dominio.

---

## Prueba puntual de 2 puntos con fases estables
Macro: `solid_eval_2pts.tcm`

### Punto 0738
```text
W(FE)=0.2170000000
W(MG)=0.0353535354
```
Resultado:
- convergió
- no mostró sólido estable en ese punto

### Punto 0792
```text
W(FE)=0.2750000000
W(MG)=0.0404040404
```
Resultado:
- convergió
- sí mostró sólido estable:
  - `HALITE#1 > 0`

### Propiedades observadas en 0792
- `DVIS(IONIC_LIQ#1)=5.2207329E-3`
- `DVIS(IONIC_LIQ#2)=1.8064411E-2`
- `DVIS(IONIC_LIQ#3)=1.8064411E-2`
- `BP(HALITE#1)=0.15448915`
- `VP(HALITE#1)=3.7783152E-8`
- `VP(IONIC_LIQ#1)=5.3036316E-8`
- `VP(IONIC_LIQ#2)=8.4598678E-6`

---

## Cálculo puntual de fracción volumétrica y viscosidad efectiva
Para el punto 0792:

### Volúmenes
```text
V_liq = VP(IONIC_LIQ#1) + VP(IONIC_LIQ#2) + VP(IONIC_LIQ#3)
      = 8.512904116E-6

V_sol = VP(HALITE#1) + VP(HALITE#2)
      = 3.7783152E-8

V_tot = 8.550687268E-6
```

### Fracción volumétrica de sólidos
```text
phi_s = V_sol / V_tot = 0.0044187269
```

### Viscosidad líquida usada
Se tomó el set líquido dominante (`IONIC_LIQ#2`):
```text
mu_liq = 0.018064411
```

### Viscosidad efectiva
Con `phi_m = 0.64`:
```text
mu_eff = mu_liq * (1 - phi_s/phi_m)^(-2.5*phi_m)
       = 0.0182657713
```

### Interpretación
- `phi_s` ~ 0.44 vol%
- incremento relativo de viscosidad ~ +1.1%

---

## Regla de convergencia para parser/control
Nunca confiar ciegamente en un punto si la convergencia falló.

### Regla práctica
Si el valor reportado no coincide con el valor impuesto:
```python
if abs(W_FE_reported - W_FE_input) > tol:
    # descartar punto
```
Análogo para `W_MG`.

Esto es crítico porque cuando POLY no converge puede dejar el estado anterior válido.

---

## Pipeline correcto a futuro
### Para barridos grandes
1. correr batch con log normal
2. usar delimitadores `POINT_ID=...`
3. extraer:
   - composición
   - `DVIS(...)`
   - `NP(*)`
   - `BP(*)`
   - `VP(*)`
4. en parser:
   - detectar fases líquidas vs sólidas
   - calcular `V_liq`, `V_sol`, `phi_s`
   - calcular `rho` desde `BP/VP`
   - calcular `mu_eff`
5. validar convergencia punto por punto

### Para puntos difíciles
- no saltar lejos en composición
- usar un punto real del batch como semilla
- preferir puntos convergidos ya existentes

---

## Patrón `.dat` validado (importante)
Hallazgo clave posterior:
`OUTPUT_FILE_FOR_SHOW` sí puede usarse en batch **si** se hace así:
1. `set-ges-version 6`
2. arranque limpio (`go data` → `sw data` → `tcox12` → `def-el` → `get` → `go p-3`)
3. crear previamente el archivo `.dat`
4. usar comando directo con ruta absoluta:
```text
adva OUTPUT_FILE_FOR_SHOW "C:\ruta\archivo.dat"
```

Esto evita que se abra la ventana interactiva.

### Regla de oro del arranque
Antes de `go data`, arrancar siempre con:
```text
set-ges-version 6
```

### Arranque mínimo correcto para macros finales
```text
set-ges-version 6

go data
sw data
tcox12

def-el
CA MG SI AL MN FE O
get
go p-3
```

### Macro mínimo validado con `.dat`
En carpeta:
`C:\Users\ELANOR\Documents\pruebas GES6`

Archivos:
- `ges6_2pts_dat_test.tcm`
- `auditoria.dat`
- `ges6_2pts_dat_test.stdout.log`

Resultado:
- `RC=0`
- `.dat` generado correctamente
- `SURF(...)` sí salió
- `NP($)`, `BP($)`, `VP($)` sí salieron

### Observación importante sobre `.dat`
El archivo `.dat` no conserva comentarios/markers tipo `@@ POINT ...` del macro.
En la práctica, el parser debe segmentar puntos por el patrón real del archivo, empezando por líneas como:
```text
W(FE)=...
W(MG)=...
...
VP($)...
```
No asumir que el `.dat` trae delimitadores textuales del macro.

## Corrida productiva en 5 chunks con `.dat`
Carpeta:
`C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\run_2026-03-18_183915\chunks_5x1000_dat`

Se generaron y corrieron 5 chunks de 1000 puntos cada uno:
- `tc_chunk_01.tcm/.dat/.stdout.log`
- `tc_chunk_02.tcm/.dat/.stdout.log`
- `tc_chunk_03.tcm/.dat/.stdout.log`
- `tc_chunk_04.tcm/.dat/.stdout.log`
- `tc_chunk_05.tcm/.dat/.stdout.log`

Todos terminaron con `RC=0`.

## Parsers finales creados
En `chunks_5x1000_dat`:
- `parse_chunks_dat_to_master.py`
- `build_effective_viscosity_csv.py`

### Salidas finales
- `tc_master_from_dat.csv`
- `tc_phases_long_from_dat.csv`
- `tc_master_with_mu_eff.csv`

### Estado final confirmado
- 5 `.dat` parseados
- 5000 puntos parseados
- 6 fases detectadas
- CSV maestro consolidado generado
- CSV con `mu_eff` generado

### Parser maestro final
Archivo:
- `parse_chunks_dat_to_master.py`

Lógica real usada:
- leer `tc_chunk_*.dat`
- segmentar cada punto por el patrón real del `.dat`, comenzando en líneas `W(FE)=...`
- extraer por punto:
  - composición
  - `DVIS(IONIC_LIQ#1..3)`
  - `SURF(IONIC_LIQ#1..3)`
  - `NP/BP/VP(IONIC_LIQ#1..3)`
  - `BV`
  - fases desde `NP($)`, `BP($)`, `VP($)`

### Postparser final
Archivo:
- `build_effective_viscosity_csv.py`

Calcula:
- `dominant_liquid_set`
- `mu_liq`
- `sigma_liq`
- `rho_liq_dom = BP_liq_dom / VP_liq_dom`
- `phi_s = V_sol_total / V_total`
- `mu_eff`

### Criterio físico usado
- escoria = líquido dominante por `BP`
- `sigma = SURF(liq_dom)`
- `rho_liq = BP(liq_dom) / VP(liq_dom)`
- sólidos = todo lo que no sea `IONIC_LIQ#*`

### Modelo usado para viscosidad efectiva
En la etapa final se usó:
```text
mu_eff = mu_liq * (1 - phi_s/0.64)^(-1.6)
```

### Cuidado importante
En algunos puntos:
- `phi_s_max ≈ 0.8184`
- `mu_eff_max ≈ 1.59E19`

Interpretación:
- para `phi_s > phi_m=0.64`, el modelo se vuelve singular / fuera de rango físico
- esos puntos deben marcarse o filtrarse en postproceso

---

## Archivos relevantes
### Workspace
- `C:\Users\ELANOR\.openclaw\workspace\thermocalc_agent.md`

### Carpeta de corrida actual
- `C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\run_2026-03-18_183915\...`

### Carpeta de referencia vieja
- `C:\Users\ELANOR\Documents\slag foaming\...`

---

## Resumen ejecutivo final
- `OUTPUT_FILE_FOR_SHOW` no sirve para batch aquí
- `SHOW_VALUE` + log normal sí sirve
- `SURF(...)` no está soportado en este modo/base
- `DS(...)` no está disponible como variable usable
- `VP(*)` sí funciona y es la clave para `phi_s`
- el sistema sí presenta sólidos en parte del dominio
- la extracción incompleta puede ocultarlos aunque termodinámicamente existan
- para `mu_eff` real se necesita volumen de sólidos (`VP(*)`), no solo masa

---

## Nuevo flujo validado: sistema CaO-SiO2-Al2O3-3%MgO en modo óxidos

### Objetivo del nuevo flujo
Construir una corrida grande (meta inicial: 5000 puntos) para el sistema cuaternario:
- `CaO-SiO2-Al2O3-MgO`
- con `MgO = 3 wt%` fijo
- usando Thermo-Calc Console 2025a + `TCOX12`
- en **modo óxidos**
- arrancando con `DEF-EL` en elementos y ya dentro de `POLY` usando `DEFINE_COMPONENTS CAO SIO2 AL2O3 MGO`

### Regla de modelado confirmada
Para este flujo no conviene imponer condiciones elementales con oxígeno adicional.
El patrón correcto es:
1. `DEF-EL CA SI AL MG O`
2. `GET`
3. `GO P-3`
4. `REINITIATE_MODULE`
5. `DEFINE_COMPONENTS CAO SIO2 AL2O3 MGO`
6. imponer directamente:
   - `W(CAO)`
   - `W(SIO2)`
   - `W(AL2O3)`
   - `W(MGO)`

### Arranque mínimo correcto validado para este sistema
```text
SET_GES_VERSION 6
SET_ECHO
SET_LOG_FILE ...

GO DATA
SW DATA
TCOX12

DEF-EL
CA SI AL MG O
GET
GO P-3
REINITIATE_MODULE
DEFINE_COMPONENTS CAO SIO2 AL2O3 MGO

SET_CONDITION T=1873.15 P=101325 N=1
```

### Estado del arranque: observación importante
Aunque la macro arranca con `SET_GES_VERSION 6`, en el `stdout.log` sigue apareciendo al inicio una secuencia ruidosa:
- arranque temporal en `TCFE4`
- warning de reversión temporal a `GES5`
- luego cambio a `TCOX12`
- finalmente línea clave:
```text
*** Invoking Gibbs Energy System v6 ***
```

Interpretación operativa:
- el arranque de Console no es limpio desde la primera línea
- **pero el cálculo efectivo sí termina entrando a `TCOX12` + `GES6`**
- para validar esto, buscar siempre en log:
```text
Current database: Metal Oxide Solutions  v12.0
*** Invoking Gibbs Energy System v6 ***
```

No lanzar corridas grandes sin confirmar esas dos señales.

---

## Pruebas de validación hechas para 2 puntos
Carpeta:
`C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\run_2026-03-19_cao_sio2_al2o3_mgo3_5000`

### Inputs de validación usados
#### Punto 1
```text
W(CAO)=0.60
W(SIO2)=0.20
W(AL2O3)=0.17
W(MGO)=0.03
```

#### Punto 2
```text
W(CAO)=0.45
W(SIO2)=0.35
W(AL2O3)=0.17
W(MGO)=0.03
```

### Resultado físico general
#### Punto 1
- líquido principal: `IONIC_LIQ#2`
- sólido estable: `CA2SIO4_ALPHA_A`
- `NP(IONIC_LIQ#2)=0.77346429`
- `NP(CA2SIO4_ALPHA_A)=0.22653571`
- `DVIS(IONIC_LIQ#2)=0.1125613`
- `SURF(IONIC_LIQ#2)=0.58248829`

#### Punto 2
- sólo líquido `IONIC_LIQ#2`
- `NP(IONIC_LIQ#2)=1.0`
- `DVIS(IONIC_LIQ#2)=0.23033567`
- `SURF(IONIC_LIQ#2)=0.48974144`

### Interpretación físico-química confirmada
Al pasar del punto 1 al punto 2:
- baja la basicidad efectiva (`CaO` baja, `SiO2` sube)
- la viscosidad aumenta
- la tensión superficial disminuye
- el equilibrio pasa de líquido + sólido a líquido único

Esto es físicamente consistente y sirve como validación inicial del flujo.

---

## Actividades y estados de referencia
### Esquema usado en las pruebas
```text
SET_REFERENCE_STATE CAO HALITE#1,,,
SET_REFERENCE_STATE MGO HALITE#2,,,
SET_REFERENCE_STATE AL2O3 CORUNDUM,,,
SET_REFERENCE_STATE SIO2 QUARTZ,,,
```

### Actividades obtenidas
#### Punto 1
```text
ACR(CAO)=0.77435643
ACR(SIO2)=8.2661372E-5
ACR(AL2O3)=4.87813E-3
ACR(MGO)=0.41224109
```

#### Punto 2
```text
ACR(CAO)=3.7627963E-2
ACR(SIO2)=2.114544E-2
ACR(AL2O3)=0.10803339
ACR(MGO)=0.14192886
```

### Hallazgo crítico sobre el reference state efectivo de MGO
Aunque la macro pidió:
```text
SET_REFERENCE_STATE MGO HALITE#2,,,
```
`LIST_EQUILIBRIUM ,,,` reportó efectivamente:
```text
MGO ... Ref.stat HALITE#1
```

Esto implica que para `MGO`:
- Thermo-Calc está reinterpretando, remapeando o ignorando el estado pedido
- el valor de `ACR(MGO)` debe considerarse válido **respecto al reference state efectivo que el solver terminó usando**, no necesariamente respecto al texto del macro

### Regla nueva
Antes de cualquier corrida grande que use `ACR(...)`, validar siempre reference states efectivos con:
```text
LIST_EQUILIBRIUM ,,,
```
No asumir que `SET_REFERENCE_STATE` fue aceptado literalmente.

---

## Comandos de inspección comparados
### `L-ST` + `CPS`
Sirven para inspección rápida del equilibrio, pero en esta instalación devolvieron principalmente:
- status de componentes
- reference states
- fases presentes
- driving forces
- species activas

Útiles para auditoría cualitativa, pero **no son la mejor salida compacta para composición de fase**.

### `LIST_EQUILIBRIUM ,,,`
Este sí resultó ser el comando más útil para inspección detallada en este flujo.

#### Información que sí devuelve
- condiciones de equilibrio
- grados de libertad
- energía/entalpía/volumen total
- tabla de componentes con:
  - moles
  - fracción masa
  - actividad
  - potencial químico
  - reference state efectivo
- fases presentes con:
  - moles
  - masa
  - fracción de volumen
  - mass fractions por fase

### Conclusión operativa nueva
Para validación fina antes de lanzar chunks:
- usar `LIST_EQUILIBRIUM ,,,`
- no depender solo de `CPS`
- usar `SHOW_VALUE` para propiedades numéricas parseables
- usar `LIST_EQUILIBRIUM ,,,` para auditoría termodinámica y composición de fases

---

## Composición de fases confirmada por `LIST_EQUILIBRIUM ,,,`
### Punto 1
#### Fase líquida `IONIC_LIQ#2`
Mass fractions:
```text
CAO    5.86540E-01
SIO2   1.59496E-01
AL2O3  2.16202E-01
MGO    3.77627E-02
```

#### Sólido `CA2SIO4_ALPHA_A`
Mass fractions:
```text
CAO    6.49528E-01
MGO    1.43689E-03
AL2O3  0.00000E+00
SIO2   3.49035E-01
```

### Punto 2
#### Fase líquida `IONIC_LIQ#2`
Mass fractions:
```text
CAO    4.50000E-01
SIO2   3.50000E-01
AL2O3  1.70000E-01
MGO    3.00000E-02
```

Interpretación:
- en el punto 2, la fase líquida reproduce exactamente la composición total porque el sistema está completamente líquido
- en el punto 1, el líquido se enriquece respecto al total por partición hacia el sólido cálcico-silicatado

---

## Reglas nuevas para el workflow de 5000 puntos
### 1. Validación previa obligatoria
Antes de correr los chunks grandes, hacer siempre un test corto de 1–2 puntos verificando:
- `TCOX12` activo
- `GES6` efectivo
- `LIST_EQUILIBRIUM ,,,` sin inconsistencias graves
- properties clave (`ACR`, `DVIS`, `SURF`, `NP/BP/VP`) presentes

### 2. Si se van a reportar actividades
No correr 5000 puntos con `ACR(...)` hasta definir un esquema consistente de reference states.
Pendiente técnico explícito:
- probar microtests dedicados a `MGO`
- comparar lo pedido vs lo efectivo en `LIST_EQUILIBRIUM ,,,`
- sólo después fijar el esquema final de referencias para producción

### 3. Si se va a correr primero por propiedades sin depender de `ACR(MGO)`
Se puede avanzar con:
- `DVIS`
- `SURF`
- `NP/BP/VP`
- fases presentes
- composición de fases

pero documentando que el tema de reference state de `MGO` sigue bajo auditoría.

### 4. Comando más útil de auditoría
Agregar en macros de validación:
```text
LIST_EQUILIBRIUM ,,,
```

### 5. Comandos menos prioritarios
- `L-ST`
- `CPS`

sirven, pero no sustituyen a `LIST_EQUILIBRIUM ,,,`.

---

## Archivos nuevos relevantes
En:
`C:\Users\ELANOR\Documents\ThermoCalc_OpenClaw\run_2026-03-19_cao_sio2_al2o3_mgo3_5000`

### Validaciones creadas
- `test_2pts.tcm`
- `test_2pts.dat`
- `test_2pts.stdout.log`
- `test_2pts_with_acr.tcm`
- `test_2pts_with_acr.dat`
- `test_2pts_with_acr.stdout.log`
- `test_2pts_paranoid.tcm`
- `test_2pts_paranoid.dat`
- `test_2pts_paranoid.stdout.log`
- `test_2pts_lst_cps.tcm`
- `test_2pts_lst_cps.dat`
- `test_2pts_lst_cps.stdout.log`
- `test_2pts_list_equilibrium.tcm`
- `test_2pts_list_equilibrium.dat`
- `test_2pts_list_equilibrium.stdout.log`

### Estado actual del conocimiento
El flujo ya está suficientemente maduro para pasar a construcción de chunks de 5000 puntos, **pero** antes conviene cerrar el pendiente del reference state efectivo de `MGO` si las actividades van a formar parte central del análisis/reportes.
