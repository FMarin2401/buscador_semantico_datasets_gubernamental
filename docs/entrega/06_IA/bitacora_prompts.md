# Bitácora de prompts (Tema 6: Ingeniería de prompts)

**Proyecto:** Buscador Semántico de Datasets Gubernamentales, Municipio de León
**Herramienta:** Claude Code (extensión de VS Code), sobre el repositorio del proyecto
**Periodo:** 15 de octubre al 1 de noviembre de 2026

## Cómo se armó esta bitácora

Los tres prompts son **textuales**, copiados del historial de sesiones de Claude Code (`~/.claude/projects/.../*.jsonl`), con sus erratas. No se reescribieron para que se vieran mejor: lo que se evalúa aquí es cómo se dirigió el trabajo.

En casi todos los casos el prompt inicial fue corto, y lo importante pasó **en la respuesta al plan que propuso Claude**: ahí di el contexto con su porqué, recorté el alcance y cambié el orden antes de aprobar. Por eso cada entrada documenta el intercambio completo:

1. **Prompt:** lo que escribí.
2. **Lo que propuso Claude:** su plan u opciones, resumidos.
3. **Ajuste y por qué:** lo que corregí antes de aprobar.
4. **Resultado:** lo que se hizo y dónde quedó.
5. **Cómo lo escribiría hoy:** el mismo pedido en un solo prompt que aplica las técnicas del Tema 6.

Elementos que se revisan en cada entrada:

| Elemento | Qué significa |
|---|---|
| **Contexto con su porqué** | Dar la información que la IA no puede adivinar y la razón detrás (una restricción de costo, un objetivo), no solo la orden |
| **Restricción de alcance** | Decir qué sí y qué no se hace, para que no cambie más de lo pedido |
| **Formato de salida** | Decir qué entregable se espera (un archivo Markdown, una tabla, un plan por fases) |
| **Plan revisado antes de aprobarlo** | Pedir un plan, leerlo y corregirlo antes de que se ejecute |
| **Sin mitos** | No usar mayúsculas, amenazas ni frases como "eres el mejor experto": no mejoran el resultado; el contexto concreto sí |

Ninguno de los tres prompts usa mitos. Lo que hizo que las respuestas fueran útiles fue el contexto concreto (la cuenta de estudiante, que los datos son de prueba, la rúbrica en PDF), no el tono.

Los tres se eligieron porque, juntos, cubren los cuatro elementos:

| Prompt | Contexto con su porqué | Restricción de alcance | Formato de salida | Plan revisado |
|---|---|---|---|---|
| 1. Documentación técnica | | ✓ | ✓ | |
| 2. Plan de la revisión de código | ✓ | | | ✓ |
| 3. Rúbrica del 2.º parcial | ✓ | ✓ | ✓ | ✓ |

---

## Prompt 1: Documentación técnica del proyecto

**Fecha:** 15 de octubre de 2026 · **Elementos:** formato de salida, restricción de alcance

### Prompt

> Quiero que me hagas un documento del proyecto, una documentacion en markdown

### Lo que propuso Claude

Revisó todo el código y escribió `docs/DOCUMENTACION.md` (arquitectura, instalación, búsqueda, modelo de datos, API, seguridad). Al terminar, además del resumen, señaló varios problemas que encontró en el código (la evaluación del buscador, la persistencia en Azure) y ofreció corregirlos.

### Ajuste y por qué

> Solo haz la documentacion, e incluye una explicacion de porque eso falla

- **Recorté el alcance:** quería un documento, no cambios en el código. Si Claude hubiera empezado a corregir, habría mezclado dos trabajos distintos en el mismo paso y no habría podido revisar uno sin el otro.
- **Pedí un formato concreto para los problemas:** no una lista de fallas, sino la **explicación de por qué fallan**. Así el documento me servía para entender el código y decidir después qué arreglar.

### Resultado

Se agregó la sección "Problemas conocidos y por qué fallan". Al escribirla, Claude corrigió algo que había dicho antes: la evaluación no daba 0 %, sino un número inflado que no medía nada. Ese documento se convirtió en `docs/Documentación_Técnica_Buscador.md` y en la lista de pendientes de la revisión de código (`docs/pendientes.md`).

### Cómo lo escribiría hoy

> Escribe la documentación técnica del proyecto en `docs/DOCUMENTACION.md`, en Markdown, para alguien que va a mantener el código: arquitectura, instalación, cómo funciona la búsqueda, modelo de datos y referencia de la API. No modifiques código; si encuentras errores, agrégalos en una sección "Problemas conocidos" explicando la causa y la consecuencia de cada uno.

**Qué mejora:** dice desde el inicio el lector, las secciones y el límite ("no modifiques código"), así no hace falta un segundo mensaje para recortar el alcance.

---

## Prompt 2: Plan de trabajo para la revisión de código

**Fecha:** 22 de octubre de 2026 · **Elementos:** plan revisado antes de aprobarlo, contexto con su porqué

### Prompt

> Desarrolla un plan de que hacer primero

(Sobre `docs/pendientes.md`, la revisión de código con 22 hallazgos.)

### Lo que propuso Claude

Antes de responder, revisó el código para confirmar que los hallazgos seguían vigentes. Propuso un plan por fases ordenado por riesgo: Fase 0 medir la calidad real del buscador, Fase 1 cambios rápidos, **Fase 2 revisar Azure** (montar Azure Files para no perder datos), y después dependencias de seguridad, Alembic y limpieza.

### Ajuste y por qué

> a mi me gustaria dejar lo de azure hasta el final, creo que ni siquiera puedo hacer eso de azure files pq lo tengo con la cuenta de estudiantes

> si esta bien, no pasa nada, todo sigue siendo de prueba, no planeo subir datasets por el panel solo es demoostracion estoy consciente que se borran en cuanto el contenedro se apga

- **Cambié el orden del plan antes de aprobarlo:** Azure pasó al final.
- **Di el contexto que Claude no podía saber, con su porqué:** uso una **cuenta de estudiante** (probablemente sin Azure Files ni servicios de pago) y la app en Azure es **solo una demostración**, así que perder los datos al apagarse el contenedor es aceptable. Sin ese contexto, Claude trataba la persistencia como un riesgo urgente.

### Resultado

Claude reordenó las fases. Además movió el ajuste de `--forwarded-allow-ips` al final, porque solo se puede afinar viendo el comportamiento real de Azure. Se ejecutaron las fases 1 a 6 en PRs separados (#2 a #11). La Fase 1 reveló que la calidad real del buscador era 78 % y no el número inflado de antes; con el cambio de modelo (PR #7) llegó a 95 %.

### Cómo lo escribiría hoy

> Lee `docs/pendientes.md` y propón un plan por fases para resolver los hallazgos, ordenado por riesgo, con lo que incluye cada fase. Contexto: la app en Azure es una demo con cuenta de estudiante; no puedo pagar servicios extra y acepto que los datos se pierdan al apagarse el contenedor, así que lo de Azure va al final. Muéstrame el plan antes de cambiar código.

**Qué mejora:** el contexto y la restricción van en el primer mensaje, así el primer plan ya sale con el orden correcto; y queda explícito que se debe esperar la aprobación.

---

## Prompt 3: Contrastar el repositorio con la rúbrica del 2.º parcial

**Fecha:** 1 de noviembre de 2026 · **Elementos:** contexto con su porqué, formato de salida, restricción de alcance, plan revisado antes de aprobarlo

### Prompt

> Acabo de colocar un pdf en la carpeta, analizalo y contrastalo con mi repo para ver que le falta para obtener una calificacnio perfecta

### Lo que propuso Claude

Leyó la rúbrica y el repositorio y entregó una tabla criterio por criterio (estado actual y qué falta), con los tres riesgos más grandes: un solo contenedor en lugar de tres, SQLite en lugar de PostgreSQL y que `docker compose up --build` fallaría en una copia limpia. Propuso un orden de trabajo en 7 pasos.

### Ajuste y por qué

> si, me parece bien, podemos usar postgres para el compose local porque no quiero pagar en azure, si es mejor que se quede igual con sqlite, vamos con el paso 1 en una nueva rama

- **Contexto con su porqué:** PostgreSQL solo para el compose local, porque no quiero pagar en Azure; la demo pública se queda con SQLite.
- **Alcance:** solo el paso 1, en una rama nueva.

Después, Claude entró en **modo plan**: escribió el plan detallado y me hizo dos preguntas antes de tocar código.

| Pregunta de Claude | Su recomendación | Lo que elegí | Por qué |
|---|---|---|---|
| ¿Versionar los 75 CSV de ejemplo en el repositorio público? | Sí | Sí | Sin ellos, la copia del profesor arrancaría sin datos |
| ¿Mover el backend a una carpeta `api/`? | No moverlo | **Moverlo** | La rúbrica pide `04_Codigo/` con `frontend/`, `api/` y `db/`; preferí que la estructura coincidiera aunque costara ajustar rutas |

Al revisar el plan escrito, **rechacé la primera versión** porque decía que Docker no estaba disponible en mi WSL; corregí que Docker Desktop sí existe pero no estaba abierto. Con eso Claude ajustó la sección de verificación y aprobé.

### Resultado

PR #16: tres contenedores (nginx, FastAPI, PostgreSQL) con red privada, `.env.example`, datos de ejemplo y README de un solo comando, verificado desde un clon limpio. Le siguieron los PR #17 (modelo con llaves foráneas y SC-001), #18 (Swagger y 60 pruebas) y #19 (CLAUDE.md, diagramas y diccionario de datos).

### Cómo lo escribiría hoy

> Puse la rúbrica del 2.º parcial en `Segundo_Parcial_Criterios_Evaluacion.pdf`. Compárala con el repositorio y dame una tabla por criterio con: puntos, estado actual (cumple, parcial, no cumple), qué falta y si lo hago yo o tú. Contexto: Azure debe quedarse con SQLite porque no voy a pagar; PostgreSQL solo en docker compose local. No cambies nada todavía: primero quiero el análisis y un orden de trabajo para revisarlo.

**Qué mejora:** define desde el inicio las columnas de la tabla, las restricciones conocidas y que no se ejecute nada sin aprobación.

---

## Lo que aprendí

1. **El contexto con su porqué vale más que cualquier truco de redacción.** "Cuenta de estudiante", "es solo una demo" y "no quiero pagar" cambiaron por completo las recomendaciones; ninguna instrucción en mayúsculas habría logrado eso.
2. **Pedir el plan y revisarlo antes de aprobar** evitó trabajo en la dirección equivocada: Azure al principio del plan de octubre, y en noviembre un plan de verificación basado en un dato falso (que Docker no estaba instalado).
3. **Recortar el alcance de forma explícita** ("solo haz la documentación", "vamos con el paso 1 en una nueva rama") mantuvo cada cambio pequeño y revisable en su propio PR.
4. **Mis prompts iniciales eran demasiado cortos:** el contexto y las restricciones llegaban en el segundo mensaje. Ponerlos desde el primero (como en las versiones "Cómo lo escribiría hoy") ahorra una vuelta.
5. **Hay que verificar lo que afirma la IA.** En el prompt 1, Claude corrigió su propia afirmación de que la evaluación daba 0 % al revisarla con más cuidado. Por eso cada cambio del proyecto se verificó con pruebas, capturas o la app funcionando, no solo con el resumen de la IA.
