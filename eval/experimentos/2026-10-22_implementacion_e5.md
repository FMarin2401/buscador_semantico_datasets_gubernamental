# Implementación: cambio a `multilingual-e5-small` y calibración del umbral

**Fecha:** 2026-10-22
**Antecedente:** [comparación de modelos](2026-10-21_comparacion_modelos.md)
**Resultados crudos:** [`eval/resultados/e5_small.json`](../resultados/e5_small.json) (antes: [`baseline.json`](../resultados/baseline.json))

## Qué se cambió

1. **Modelo:** `paraphrase-multilingual-MiniLM-L12-v2` → `intfloat/multilingual-e5-small` en `app/nlp_model.py` y en la precarga del `Dockerfile`.
2. **Prefijos de e5:** las búsquedas se codifican con `"query: "` y los textos de los datasets con `"passage: "`. `app/nlp_model.py` expone funciones separadas (`generar_embedding_consulta` y `generar_embedding_documento`) para que ningún punto del código pueda olvidar el prefijo. El formato del texto indexado quedó en una sola función, `texto_para_indexar`.
3. **Re-indexación:** con `scripts/migrate_chroma.py`, que reutiliza los IDs existentes. Los 75 datasets conservaron su ID, su CSV en `data/raw/` y su contador de descargas. Los datasets subidos desde el panel también se re-indexan.
4. **Protección contra índices incompatibles:** MiniLM y e5-small generan vectores de 384 dimensiones, así que una Chroma indexada con el modelo anterior **no da error**, pero devuelve resultados sin sentido. Ahora la colección guarda el modelo con que se indexó (`modelo_embeddings`) y, si no coincide con el de la app, `/api/health/ready` responde 503 y el log indica que hay que re-indexar.
5. **Umbral:** `0.60` → `0.19`, definido junto al modelo en `app/nlp_model.py` (`UMBRAL_DISTANCIA`).

## Resultados

| Métrica | MiniLM (antes) | **e5-small (ahora)** |
|---|---|---|
| Recall@1 | 49% | **72%** |
| Recall@5 (meta: 85%) | 78% | **95%** |
| Recall@10 | 88% | **98%** |
| MRR@10 | 0.620 | **0.815** |
| **Recall@5 visible** (correcto en Top-5 y dentro del umbral) | 65% (umbral 0.60) | **89%** (umbral 0.19) |
| Consultas ajenas rechazadas | — | **83%** (25 de 30) |

El número que más importa para el ciudadano es el **Recall@5 visible**, que pasa de 65% a 89%: es la proporción de búsquedas en las que la web muestra el dataset correcto entre los 5 primeros.

## Calibración del umbral

Se agregó [`eval/consultas_fuera_de_tema.json`](../consultas_fuera_de_tema.json): 30 consultas que ningún dataset municipal debería responder ("receta de pastel de chocolate", "trucos para el minecraft", "asdfghjkl"...). Se evitaron a propósito las ambiguas (por ejemplo, "me duele la cabeza" podría llevar razonablemente a las clínicas).

`python scripts/evaluate_model.py --calibrar` muestra el compromiso:

| Umbral | Recall@5 visible | Ajenas rechazadas |
|---|---|---|
| 0.16 | 62% | 100% |
| 0.17 | 74% | 93% |
| 0.18 | 84% | 87% |
| **0.19** | **89%** | **83%** |
| 0.20 | 90% | 60% |
| 0.21 | 93% | 33% |
| 0.22 | 95% | 10% |

Se eligió **0.19** porque es el punto de quiebre: pasar a 0.20 solo gana 1 punto de aciertos visibles, pero el rechazo de consultas ajenas cae de 83% a 60%.

### Lo que el umbral todavía no resuelve

- **6 aciertos ocultos** por quedar apenas por encima de 0.19 (entre 0.193 y 0.210). Por ejemplo, "Encontré un halcón herido, ¿a dónde lo llevo?" → `refugios_fauna_silvestre.csv` a 0.2003.
- **5 consultas ajenas aceptadas.** Por ejemplo, "nombres para perro en inglés" → `reportes_maltrato_animal.csv` (0.185) y "lorem ipsum dolor sit amet" → `reportes_maltrato_animal.csv` (0.165).

Las dos zonas de distancia se traslapan, así que ningún umbral fijo las separa por completo. Un umbral **relativo** (por ejemplo, mostrar solo los resultados cercanos al primero) o un re-ranker podrían mejorar esto; queda como trabajo futuro.

## Consultas que siguen fuera del Top-5

| ID | Consulta | Esperado | Posición |
|---|---|---|---|
| 1 | ¿A qué hora pasa la última oruga en San Jerónimo? | `transporte_orugas.csv` | 8 |
| 4 | Mapa de asaltos y vandalismo este mes. | `incidencia_delictiva.csv` | 9 |
| 23 | Cuánto cobran por entrar a la alberca de la Tota Carbajal. | `unidades_deportivas.csv` | fuera del Top-10 |
| 37 | Se rompió un tubo y se está tirando mucha agua. | `fugas_sapal.csv` | 6 |
| 39 | ¿Dónde me puede recoger el Uber en Poliforum? | `zonas_ascenso_transporte_plataforma.csv` | fuera del Top-10 |

Varias dependen de nombres propios locales ("oruga", "Tota Carbajal", "Poliforum") que un modelo general no relaciona con el tipo de dataset. Son buenos candidatos para el fine-tuning o para la búsqueda híbrida (BM25 + embeddings).

## Precauciones

- **El umbral se calibró con un conjunto pequeño** (100 consultas positivas y 30 ajenas) escrito por el mismo equipo. Conviene revisarlo con búsquedas reales de usuarios cuando las haya.
- **Si se cambia de modelo otra vez,** hay que re-indexar con `migrate_chroma.py` y recalibrar `UMBRAL_DISTANCIA` con `evaluate_model.py --calibrar`: cada modelo tiene su propia escala de distancias.

## Cómo reproducirlo

```bash
python scripts/migrate_chroma.py                                     # Re-indexa con el modelo de app/nlp_model.py
python scripts/evaluate_model.py --calibrar --salida eval/resultados/e5_small.json
```
