# Experimento: docs_ok vs docs_gap

Autor: Angel Salazar Lima · CIP 404730

## Objetivo

Comprobar que el verificador separa un corpus que documenta los controles de uno que no los documenta, y que las brechas críticas señaladas corresponden a requisitos realmente ausentes o negados en el texto.

## Diseño

| Elemento | Detalle |
|---|---|
| Checklist | `samples/checklist/security_baseline.json`, *Security Baseline* v1.0 |
| Requisitos | 14 (6 críticos: SEC-01, 02, 04, 05, 07, 08) |
| Corpus A | `samples/docs_ok`: `access_policy`, `data_protection`, `governance`, `operations` |
| Corpus B | `samples/docs_gap`: `access_notes`, `data_notes`, `ops_notes` |
| Método | Matching léxico por oración, sin LLM, con detección de negación |
| Parámetros | `max_evidence=3`, pesos y umbrales por defecto de `scorer.py` |

`docs_ok` redacta cada control con las frases que pide el checklist. `docs_gap` imita borradores informales: menciona los temas de forma vaga, omite varios y niega explícitamente uno (MFA).

## Reproducción

```bash
pip install -e ".[dev]"
python -m doc_compliance compare
pytest -k experiment
```

`compare` imprime la tabla de abajo y escribe `results/compare.json`. La prueba `test_experiment_reference_scores` fija los valores de referencia, de modo que un cambio en los umbrales que altere el resultado hace fallar `pytest`.

## Resultados

Ejecución del 17/11/2026 sobre el código de este repositorio (20 pruebas previas en verde, más 2 nuevas).

| Corpus | Puntaje global | Veredicto | pass / partial / fail | Brechas críticas |
|---|---|---|---|---|
| `docs_ok` | **98.9%** | Cumple | 13 / 1 / 0 | 0 |
| `docs_gap` | **11.7%** | No cumple | 0 / 2 / 12 | 6 |

Diferencia: 87.2 puntos porcentuales.

### Detalle por requisito

| ID | Requisito | Crítico | Peso | `docs_ok` | `docs_gap` |
|---|---|:-:|:-:|---|---|
| SEC-01 | Least privilege and periodic access reviews | sí | 3 | PASS 100% | FAIL 14% |
| SEC-02 | Multi-factor authentication | sí | 3 | PASS 100% | FAIL 0% |
| SEC-03 | Password policy | no | 2 | PASS 100% | FAIL 7% |
| SEC-04 | Encryption in transit | sí | 3 | PASS 100% | PARTIAL 56% |
| SEC-05 | Encryption at rest and key management | sí | 3 | PASS 100% | FAIL 0% |
| SEC-06 | Centralized logging and monitoring | no | 2 | PASS 100% | FAIL 9% |
| SEC-07 | Incident response plan | sí | 3 | PASS 100% | FAIL 0% |
| SEC-08 | Backups and disaster recovery | sí | 2 | PASS 100% | FAIL 0% |
| SEC-09 | Vulnerability and patch management | no | 2 | PASS 100% | PARTIAL 41% |
| SEC-10 | Change management | no | 1 | PASS 100% | FAIL 0% |
| SEC-11 | Third-party and vendor risk | no | 2 | PASS 100% | FAIL 0% |
| SEC-12 | Data retention and disposal | no | 1 | PASS 100% | FAIL 9% |
| SEC-13 | Security awareness training | no | 1 | PASS 100% | FAIL 0% |
| SEC-14 | Asset inventory | no | 1 | PARTIAL 68% | FAIL 7% |

### Brechas críticas en `docs_gap`

| ID | Estado | Causa |
|---|---|---|
| SEC-01 | FAIL | Los privilegios se otorgan por correo al helpdesk y las cuentas privilegiadas se comparten; no hay revisión periódica |
| SEC-02 | FAIL | "We do not enforce multi-factor authentication for staff, only a password." Se registra como contra-evidencia y no suma |
| SEC-04 | PARTIAL | Hay HTTPS en el sitio público, pero faltan TLS 1.2/1.3 y VPN, y los servicios internos usan HTTP |
| SEC-05 | FAIL | Sin evidencia de cifrado en reposo ni gestión de claves |
| SEC-07 | FAIL | Sin evidencia de plan de respuesta a incidentes |
| SEC-08 | FAIL | Sin evidencia de respaldos ni recuperación ante desastres |

### Hallazgo menor en `docs_ok`

SEC-14 queda en `partial` (68%) porque falta la frase obligatoria `asset owner`: `governance.txt` describe el inventario y su ciclo de vida, pero no nombra un responsable por activo. No es crítico, así que el veredicto sigue siendo *Cumple*.

## Experimento 2: checklist y corpus en español

Misma pregunta, con el checklist `samples/checklist/linea_base_seguridad.json` (*Línea base de seguridad (ES)* v1.0) y corpus redactados en español.

| Elemento | Detalle |
|---|---|
| Requisitos | 12 (6 críticos: ES-01, 02, 04, 05, 07, 08) |
| Corpus A | `samples/docs_ok_es`: `politica_accesos`, `proteccion_datos`, `operaciones_seguridad`, `gobierno` |
| Corpus B | `samples/docs_gap_es`: `notas_accesos`, `notas_datos`, `notas_operaciones` |
| Parámetros | Los mismos que el experimento 1; sin cambios en pesos ni umbrales |

`docs_gap_es` son borradores informales con tres negaciones explícitas: "No exigimos autenticación multifactor", "No aplicamos cifrado en reposo" y "No contamos con un plan de respuesta a incidentes".

### Cambio en el motor

La detección de negación solo miraba las tres palabras previas a la frase buscada. "No contamos con **un** plan de respuesta a incidentes" quedaba fuera de esa ventana y se contaba como evidencia positiva. `evidence.py` ahora:

- amplía la ventana a seis palabras cuando la negación es `no` + verbo de existencia o aplicación (exigimos, aplicamos, contamos con, tenemos, "no se cuenta con"…), o `nunca`, `jamás`, `tampoco`, `carecemos`;
- incorpora `tampoco`, `jamás`, `carecemos`, `carece` y `carecen` como negaciones;
- no niega las prohibiciones del tipo "no se deben compartir los códigos de autenticación multifactor";
- reconoce mayúsculas acentuadas al inicio de oración ("Áreas…", "Ñandú…").

La ventana del inglés no cambia; las pruebas del experimento 1 siguen iguales.

### Reproducción

```bash
python -m doc_compliance compare --es
pytest -k "es or spanish"
```

### Resultados

Ejecución del 17/11/2026 con `compare --es`.

| Corpus | Puntaje global | Veredicto | pass / partial / fail | Brechas críticas |
|---|---|---|---|---|
| `docs_ok_es` | **100.0%** | Cumple | 12 / 0 / 0 | 0 |
| `docs_gap_es` | **8.8%** | No cumple | 0 / 0 / 12 | 6 |

Diferencia: 91.2 puntos porcentuales (en español; 87.2 en inglés).

| ID | Requisito | Crítico | Peso | `docs_ok_es` | `docs_gap_es` |
|---|---|:-:|:-:|---|---|
| ES-01 | Mínimo privilegio y revisión periódica de accesos | sí | 3 | PASS 100% | FAIL 7% |
| ES-02 | Autenticación multifactor | sí | 3 | PASS 100% | FAIL 0% |
| ES-03 | Política de contraseñas | no | 2 | PASS 100% | FAIL 7% |
| ES-04 | Cifrado en tránsito | sí | 3 | PASS 100% | FAIL 23% |
| ES-05 | Cifrado en reposo y gestión de claves | sí | 3 | PASS 100% | FAIL 0% |
| ES-06 | Registro centralizado y monitoreo | no | 2 | PASS 100% | FAIL 18% |
| ES-07 | Plan de respuesta a incidentes | sí | 3 | PASS 100% | FAIL 0% |
| ES-08 | Respaldos y recuperación ante desastres | sí | 2 | PASS 100% | FAIL 0% |
| ES-09 | Gestión de vulnerabilidades y parches | no | 2 | PASS 100% | FAIL 32% |
| ES-10 | Gestión de cambios | no | 1 | PASS 100% | FAIL 9% |
| ES-11 | Riesgo de terceros y proveedores | no | 2 | PASS 100% | FAIL 12% |
| ES-12 | Capacitación en seguridad | no | 1 | PASS 100% | FAIL 0% |

### Brechas críticas en `docs_gap_es`

| ID | Estado | Causa |
|---|---|---|
| ES-01 | FAIL | Los accesos los gestiona el helpdesk por correo y las cuentas privilegiadas se comparten; sin "mínimo privilegio" ni revisión de accesos |
| ES-02 | FAIL | "No exigimos autenticación multifactor para el personal, solo contraseña." Contra-evidencia citada; no suma |
| ES-04 | FAIL | HTTPS en el sitio público, pero faltan TLS 1.2/1.3 y cifrado en tránsito; los servicios internos usan HTTP |
| ES-05 | FAIL | "No aplicamos cifrado en reposo en las bases de datos." Contra-evidencia; falta AES-256 |
| ES-07 | FAIL | "No contamos con un plan de respuesta a incidentes." Contra-evidencia; falta el plazo de 72 horas |
| ES-08 | FAIL | Respaldos "cuando alguien se acuerda", en el mismo servidor; sin copia diaria ni prueba de restauración |

### Observaciones

- `docs_ok_es` llega a 100% y ningún requisito queda en `partial`; el corpus se redactó con las frases del checklist, así que el resultado confirma el funcionamiento del motor y no es una medida de calidad.
- `docs_gap_es` no tiene ningún `partial` (en inglés hubo dos). ES-09 (32%) fue el más cercano: hay "escaneo de vulnerabilidades", pero falta "parches críticos".
- Las tres negaciones se registran como contra-evidencia (`negated_must_have`) y aparecen citadas en el reporte.

## Validez y límites

- Los dos corpus los redactó el mismo autor del checklist. El experimento verifica que el motor se comporta como se diseñó; no mide su exactitud sobre políticas reales de terceros.
- El puntaje depende de la redacción: un documento con las frases correctas pasa aunque el control no se aplique en la práctica.
- Los umbrales (0.65 / 0.35, `pass` con 50% de keywords, `fail` bajo 0.35) son decisiones de diseño, no valores calibrados con datos externos.
- Los corpus en español también son sintéticos y los redactó el autor del checklist; además, las reglas de negación en español se escribieron mirando esos mismos textos. Falta validarlas con políticas reales.
- Los resultados son deterministas: repetir `compare` con el mismo código da los mismos números.
