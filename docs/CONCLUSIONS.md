# Conclusiones

Autor: Angel Salazar Lima · CIP 404730

Basadas en [EXPERIMENT.md](EXPERIMENT.md).

## Lo que muestran los datos

1. **Separación clara.** `docs_ok` obtiene 98.9% y `docs_gap` 11.7%, con veredictos opuestos (*Cumple* y *No cumple*). La diferencia de 87.2 puntos no depende de un solo requisito: 13 de 14 pasan en un corpus y ninguno en el otro.
2. **Las brechas críticas son accionables.** En `docs_gap` el reporte señala seis requisitos críticos (SEC-01, 02, 04, 05, 07, 08) y, para cada uno, qué frase obligatoria falta o qué oración la contradice. Un responsable puede corregir el documento sin releer todo el corpus.
3. **La negación se trata como contra-evidencia.** "We do not enforce multi-factor authentication" no suma al puntaje de SEC-02 (0%) y aparece citada. Un buscador por palabra clave lo habría contado como cumplimiento.
4. **El puntaje máximo no es 100%.** SEC-14 queda en 68% en `docs_ok` por la ausencia de `asset owner`. El verificador detecta omisiones menores que una lectura rápida pasaría por alto.
5. **Estados intermedios con sentido.** SEC-04 y SEC-09 salen `partial` en `docs_gap`: el documento toca el tema pero sin los términos obligatorios.

## Decisiones de diseño que se confirman

- Separar `must_have` de `keywords` permite distinguir "menciona el tema" de "cumple el requisito".
- El veredicto con regla de criticidad evita que un puntaje global alto oculte un control crítico ausente.
- Citar `doc:inicio-fin` hace cada resultado auditable.
- Mantener el motor sin LLM da resultados reproducibles, ejecutables sin red y sin datos saliendo del equipo.

## Lo que no demuestran

- **Exactitud en documentos reales.** Ambos corpus son sintéticos y escritos por el mismo autor. Falta medir contra políticas reales con revisión humana (precisión y recall por requisito).
- **Cumplimiento efectivo.** Que un documento diga "MFA obligatorio" no prueba que MFA esté activo. La herramienta verifica la documentación, no los controles técnicos.
- **Robustez lingüística.** Sinónimos no declarados, políticas en español con terminología distinta o negaciones largas pueden dar falsos negativos o positivos.

## Siguientes pasos

| Prioridad | Acción |
|---|---|
| Alta | Armar un corpus con políticas públicas reales y etiquetarlo a mano para medir precisión y recall |
| Alta | Checklist en español para documentación local |
| Media | Soporte de PDF y DOCX en `corpus.py` |
| Media | Modo de comparación entre dos corridas del mismo corpus (regresión de cumplimiento) |
| Baja | Adaptar `store.py` a PostgreSQL para el despliegue de referencia en AWS descrito en [architecture.md](architecture.md) |
