# Experimento: comparación de modelos de embeddings

**Fecha:** 2026-10-21
**Script:** [`scripts/comparar_modelos.py`](../../scripts/comparar_modelos.py)
**Resultados crudos:** [`eval/resultados/comparacion_modelos.json`](../resultados/comparacion_modelos.json) y [`eval/resultados/baseline.json`](../resultados/baseline.json)

## Contexto

El objetivo de la planeación es que el dataset correcto aparezca en el **Top-5 en al menos el 85%** de las consultas del Ground Truth.

La versión anterior de `evaluate_model.py` no medía esto correctamente:

- Comparaba contra el campo `archivo_original`, que `/api/buscar` no devuelve. Como el campo llegaba vacío y en Python `"" in texto` siempre es `True`, **cualquier consulta con al menos un resultado contaba como acierto**.
- Pasaba por la API, que tiene un rate limit de 15 búsquedas por minuto, así que la mayoría de las 100 consultas recibía `429`.

Se reescribió para consultar ChromaDB directamente y comparar el nombre exacto del archivo. Con eso se obtuvo la **línea base real** del modelo en producción y después se compararon modelos alternativos.

## Método

- **Datos:** los 75 datasets indexados en `data/chroma_db`. Los 72 targets del Ground Truth están todos indexados.
- **Consultas:** las 100 de [`eval/ground_truth.json`](../ground_truth.json), en lenguaje coloquial ("Se fundió el foco de la calle, está todo oscuro").
- **Texto de cada dataset:** el mismo que se indexa en producción, `"{titulo}. {descripcion} Dependencia: {dependencia}"`.
- **Procedimiento:** con cada modelo se codifican en memoria los textos y las consultas, sin modificar ChromaDB, y se ordenan los datasets por similitud coseno.
- **Métricas:**
  - **Recall@k:** porcentaje de consultas cuyo dataset correcto aparece entre los primeros *k* resultados. Recall@5 es la "Top-5 Accuracy" de la meta.
  - **MRR (Mean Reciprocal Rank):** promedio de `1 / posición del correcto`. Vale 1.0 si el correcto siempre sale primero.
  - **Distancias:** distancia coseno (`1 - similitud`, la misma escala que ChromaDB) del dataset correcto y del dataset más cercano a 6 consultas sin relación con datos municipales ("receta de pastel de chocolate", "precio del bitcoin hoy"...). Sirven para calibrar el umbral de la API.

## Resultados

| Modelo | Dim. | Tamaño aprox. | Recall@1 | **Recall@5** | Recall@10 | MRR |
|---|---|---|---|---|---|---|
| `paraphrase-multilingual-MiniLM-L12-v2` (actual) | 384 | 470 MB | 49% | **78%** | 88% | 0.627 |
| `paraphrase-multilingual-mpnet-base-v2` | 768 | 1.1 GB | 61% | **87%** | 93% | 0.728 |
| `intfloat/multilingual-e5-small` | 384 | 470 MB | 72% | **95%** | 98% | 0.816 |
| `intfloat/multilingual-e5-base` | 768 | 1.1 GB | 74% | **97%** | 98% | 0.838 |

> El MRR del modelo actual es 0.620 en `evaluate_model.py` y 0.627 aquí. La diferencia es que `evaluate_model.py` calcula MRR@10 (si el correcto no está en el Top-10 cuenta 0) y este script usa el ranking completo.

### Distancias (para el umbral)

| Modelo | Correcto (mediana) | Correcto (p90) | Correcto (máx.) | Consultas ajenas (mín.) |
|---|---|---|---|---|
| MiniLM (actual) | 0.508 | 0.703 | 1.014 | 0.586 |
| mpnet | 0.470 | 0.608 | — | 0.624 |
| e5-small | 0.154 | 0.184 | 0.236 | 0.195 |
| e5-base | 0.172 | 0.213 | — | 0.211 |

## Hallazgos

1. **El modelo actual no alcanza la meta:** 78% en Recall@5.
2. **El umbral actual (`0.60`) oculta aciertos.** Con MiniLM, 13 consultas tenían el dataset correcto en el Top-5, pero a más de 0.60 de distancia, así que la API no lo muestra. Lo que realmente ve el ciudadano es un **65%**, no un 78%. Ejemplo: "Encontré un halcón herido, ¿a dónde lo llevo?" → `refugios_fauna_silvestre.csv` a 0.78.
3. **No hay truncamiento.** Los textos miden 34 tokens en promedio y 47 como máximo; MiniLM acepta 128. El problema no es que el modelo deje de leer parte de la descripción.
4. **e5-small pasa la meta con margen: 95% en Recall@5,** con el mismo tamaño y las mismas dimensiones (384) que el modelo actual, así que no requiere más memoria en el contenedor.
5. **e5-base apenas gana 2 puntos más** (97%) y pesa más del doble. Con 100 consultas, 2 puntos son 2 consultas, una diferencia que puede ser ruido.
6. **Cada modelo usa una escala de distancias distinta.** e5 concentra todo entre 0.15 y 0.24, así que el umbral de `0.60` dejaría pasar cualquier cosa. Para e5-small, un umbral cercano a **0.19** conserva la gran mayoría de los aciertos y descarta casi todas las consultas ajenas. Las dos zonas se tocan en los extremos, así que ningún umbral las separa perfecto.

### Consultas que fallaban con el modelo actual

De las 22 consultas fuera del Top-5 con MiniLM, varias comparten un patrón: el ciudadano usa palabras que no aparecen en la descripción del dataset.

| Consulta | Esperado | Lo que devolvía en Top-1 |
|---|---|---|
| "Turno nocturno de los recolectores de basura." | `rutas_basura.csv` | `puntos_reciclaje.csv` |
| "Deportivas de COMUDE con canchas libres." | `unidades_deportivas.csv` | `bebederos_municipales.csv` |
| "Calles que están pavimentando en el centro." | `bacheo_obras.csv` | `rutas_desfiles_eventos.csv` |
| "¿En qué colonias hay más robos a mano armada?" | `incidencia_delictiva.csv` | `permisos_espectaculos_vivos.csv` |

La lista completa con posiciones y distancias está en `baseline.json` (campo `detalle`).

## Decisión

- Adoptar **`intfloat/multilingual-e5-small`** (pendiente de implementar en una rama aparte).
- Recalibrar el umbral de distancia con el modelo nuevo.

### Qué implica el cambio

1. **Prefijos:** e5 requiere `"query: "` delante de cada búsqueda y `"passage: "` delante de cada texto de dataset. `app/nlp_model.py` necesita dos funciones (consulta y documento), y los endpoints de subida y edición deben usar la de documento.
2. **Re-indexar:** los vectores actuales no son compatibles con el modelo nuevo. Hay que regenerar `data/chroma_db` con `scripts/migrate_chroma.py`.
3. **Umbral:** pasar de `0.60` a ~`0.19` y validarlo con consultas fuera de tema.

## Precauciones

- **No ajustar las descripciones contra el mismo Ground Truth.** Si se reescriben las descripciones hasta que pasen las consultas que fallan, el número sube pero deja de medir la calidad real del buscador. Para evaluar mejoras en las descripciones hay que usar **consultas nuevas**.
- **El conjunto es pequeño:** 100 consultas y 75 datasets. Diferencias de 1 a 3 puntos no son concluyentes.
- **Faltan consultas negativas:** las 6 consultas ajenas son solo un indicio. Conviene agregar al Ground Truth un grupo de consultas fuera de tema para calibrar el umbral con más datos.

## Siguientes pasos

> Los pasos 1 y 2 se completaron el 2026-10-22: ver [implementación de e5-small](2026-10-22_implementacion_e5.md).

1. Implementar e5-small, re-indexar y correr `evaluate_model.py` para confirmar el 95%.
2. Agregar consultas negativas al Ground Truth y fijar el umbral.
3. Opcional: probar búsqueda híbrida (BM25 + embeddings) para nombres propios que el modelo no conoce ("Capeltic", "COMUDE", "Tota Carbajal").
4. Opcional: fine-tuning de e5-small. Ya no es necesario para la meta, pero se puede documentar como mejora adicional, usando este experimento como punto de partida.

## Cómo reproducirlo

```bash
python scripts/evaluate_model.py --salida eval/resultados/baseline.json
python scripts/comparar_modelos.py --salida eval/resultados/comparacion_modelos.json
```

La primera ejecución de `comparar_modelos.py` descarga los modelos de Hugging Face (de 0.5 a 1.1 GB cada uno).
