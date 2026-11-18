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

## Validez y límites

- Los dos corpus los redactó el mismo autor del checklist. El experimento verifica que el motor se comporta como se diseñó; no mide su exactitud sobre políticas reales de terceros.
- El puntaje depende de la redacción: un documento con las frases correctas pasa aunque el control no se aplique en la práctica.
- Los umbrales (0.65 / 0.35, `pass` con 50% de keywords, `fail` bajo 0.35) son decisiones de diseño, no valores calibrados con datos externos.
- Los resultados son deterministas: repetir `compare` con el mismo código da los mismos números.
