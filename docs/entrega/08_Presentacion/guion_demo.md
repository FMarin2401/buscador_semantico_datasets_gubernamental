# Guion de la presentación en vivo (10 minutos)

| Diapositiva | Tiempo | Acumulado |
|---|---|---|
| 1. Portada | 0:20 | 0:20 |
| 2. El problema | 1:00 | 1:20 |
| 3. Contexto (C4) | 0:45 | 2:05 |
| 4. Despliegue (DAR) | 1:15 | 3:20 |
| 5. Datos (DER) | 1:00 | 4:20 |
| 6. SC-001 | 0:45 | 5:05 |
| 7. API | 0:45 | 5:50 |
| 8. **Demostración** | 3:30 | 9:20 |
| 9. Uso de IA | 0:30 | 9:50 |
| 10. Cierre | 0:10 | 10:00 |

Las notas de cada diapositiva tienen lo que hay que decir. Si vas tarde, recorta de las diapositivas 5 y 7, nunca de la demo: la demo vale 6 de los 15 puntos.

---

## Antes de la clase (15 minutos antes)

1. Abre Docker Desktop y espera a que diga *Engine running*.
2. En la carpeta del proyecto: `docker compose up -d` y espera a que `docker compose ps` muestre los tres servicios `healthy`.
3. Deja abiertas estas pestañas, en este orden:
   - **Terminal** en la carpeta del proyecto, con letra grande (Ctrl + `+`).
   - **Navegador 1:** http://localhost:8080/explorar_datos.html
   - **Navegador 2:** http://localhost:8080/admin.html con la **sesión ya iniciada** (tu usuario de `.env`).
   - **Navegador 3:** http://localhost:8080/docs. En la misma ventana del panel, así comparte la cookie de sesión.
4. Haz un ensayo completo de la demo una vez. El reporte que crees en el ensayo puede quedarse: sirve si algo falla en vivo.
5. Zoom del navegador al 125 % para que se lea desde el fondo.

---

## La demo (3:30)

### 1. Tres contenedores (20 s)

**Hacer:** en la terminal, `docker compose ps`.

**Decir:** «Son tres contenedores separados: frontend con nginx, la API con FastAPI y la base de datos PostgreSQL. Solo el frontend publica un puerto, el 8080; la base está en una red interna.»

### 2. Búsqueda semántica (40 s)

**Hacer:** en *Explorar Datos*, escribe `dónde tiro mis llantas viejas` y busca.

**Decir:** «El primer resultado es *Centros de Acopio de Neumáticos*. No comparte ninguna palabra con la búsqueda: el modelo compara significados.»

*Opcional, si el tiempo va bien:* busca `receta de pastel de chocolate` → no hay resultados, y se ve el **estado vacío**. «El umbral de distancia descarta lo que no tiene que ver.»

### 3. SC-001: el ciudadano reporta (50 s)

**Hacer:** en el primer resultado, **Ver ficha** → baja a «¿Encontraste un problema?» → **Reportar un problema**.
- Tipo: *Información desactualizada*.
- Descripción: `La lista no incluye el nuevo centro de acopio de la colonia Las Joyas.`
- Correo: déjalo vacío o pon uno de prueba.
- **Enviar reporte.**

**Decir:** «Esta es la SC-001. El reporte se guarda con llave foránea al dataset y nace en estado *abierto*. Me da el folio [lee el número].» **Anota el folio**: lo usas en el paso 5.

### 4. SC-001: el funcionario atiende (50 s)

**Hacer:** cambia a la pestaña del panel → **Reportes de Datasets**. Aparece el reporte en *Abiertos*.
- Clic en **Revisar** → aviso «en revisión».
- Cambia el filtro a *En revisión* → clic en **Resolver**.
- Baja a la tabla **Datasets con reportes**.

**Decir:** «Solo aparecen los botones de las transiciones permitidas. Esta tabla de abajo lee la vista `v_resumen_datasets` de PostgreSQL.»

### 5. Prueba negativa (50 s)

**Hacer:** pestaña de `/docs` → **PATCH /api/admin/reportes/{id_reporte}** → *Try it out*.
- `id_reporte`: el folio del paso 3.
- Cuerpo: `{"estado": "abierto"}`
- **Execute.**

**Decir:** «Intento reabrir un reporte resuelto, que viola la regla de negocio. La API responde **409 Conflict** con el mensaje "Un reporte resuelto no se puede reabrir ni modificar." Esta misma prueba está automatizada con pytest, junto con otras 59.»

*Si sobra tiempo:* `docker compose exec api pytest -q` → `60 passed`.

---

## Plan B

| Si pasa esto | Haz esto |
|---|---|
| Docker no arranca o la app no responde | Muestra las capturas de `07_Evidencias` en orden; narra igual cada paso |
| `/docs` responde 401 en el paso 5 | Falta la sesión en esa ventana: ejecuta antes `POST /api/login` en `/docs` con tu usuario de `.env` |
| `/docs` responde 404 en el paso 5 | El folio está mal; usa el del reporte del ensayo (lo ves en el panel, columna *Folio*) |
| El paso 5 responde 200 | El reporte no estaba resuelto; resuélvelo en el panel y repite |
| `429 Too Many Requests` | Pasaste el límite de 5 por minuto; espera un minuto o usa el reporte del ensayo |
| Se acaba el tiempo | Salta el paso 4 y muestra solo la prueba negativa con el reporte del ensayo, que ya está resuelto |

---

## Preguntas probables

Si no puedes explicar una parte de tu entrega, ese criterio baja un nivel. Estas son las preguntas más probables y la respuesta corta.

**¿Qué es un embedding y cómo decide qué mostrar?**
Un vector de 384 números que representa el significado de un texto. La consulta y cada dataset se convierten en vectores con el modelo `multilingual-e5-small`, y ChromaDB busca los más cercanos por distancia coseno. Se descartan los que pasan de 0.19, un umbral calibrado con las 100 consultas de evaluación.

**¿Por qué hay una tabla `datasets` si los datasets ya están en ChromaDB?**
ChromaDB es el índice de búsqueda, pero no tiene llaves foráneas. Descargas y reportes necesitan apuntar a un dataset que exista, así que la tabla es su registro relacional. Se sincroniza al arrancar y en cada alta, edición o baja.

**¿Por qué el JWT va en una cookie y no en `localStorage`?**
Porque la cookie es `HttpOnly`: el JavaScript de la página no puede leerla, así que un script inyectado (XSS) no puede robar la sesión. Además es `SameSite=Lax`, contra CSRF.

**¿Qué es CORS y cómo lo configuraste?**
Es la regla del navegador sobre qué sitios pueden llamar a la API con las credenciales del usuario. Solo se permiten los orígenes de `ALLOWED_ORIGINS` (`http://localhost:8080`), nunca `*`. En compose el frontend y la API comparten origen porque nginx los sirve juntos.

**¿Por qué 409 y no 400 en la prueba negativa?**
400 es una petición mal formada. Aquí la petición es válida (el estado existe), pero choca con el estado actual del recurso: eso es un conflicto, 409. Un estado que no existe, como `cerrado`, sí da 422.

**¿Por qué PostgreSQL en local y SQLite en Azure?**
La rúbrica pide la base en su propio contenedor, y PostgreSQL permite índices, vistas y CHECK reales. La demo de Azure usa una cuenta de estudiante y un PostgreSQL administrado cuesta; ahí sigue la versión anterior con SQLite.

**¿Para qué sirve el índice y cómo sabes que se usa?**
`(estado, fecha_creacion)` acelera la bandeja del panel, que filtra por estado y ordena por fecha. Con `EXPLAIN`, PostgreSQL muestra *Index Scan Backward*: lee el índice ya ordenado y no necesita un paso de ordenamiento.

**¿Qué pasa si borro un dataset? ¿Y un usuario?**
Al borrar un dataset se borran su contador de descargas y sus reportes (`ON DELETE CASCADE`). Al borrar un usuario, sus referencias quedan en `NULL` (`SET NULL`) y la bitácora conserva su nombre en texto.

**¿Cómo evitas que las pruebas borren datos reales?**
Cada corrida de pytest trabaja en una carpeta temporal con su propia SQLite y su propio ChromaDB. Se comprobó que después de correrlas el catálogo real sigue con 75 datasets.

**¿Por qué la red `red_privada` es *internal*?**
Para que la base no tenga salida a internet ni sea accesible desde el equipo anfitrión: solo la API llega a ella. Es el equivalente a una red privada detrás de un firewall.

**¿Qué hizo la IA y qué hiciste tú?**
Claude Code escribió buena parte del código siguiendo `CLAUDE.md`. Yo definí el alcance, el orden y las restricciones (Azure sin costo, PostgreSQL solo en local, estructura con `api/`), revisé cada plan antes de aprobarlo y verifiqué los resultados con pruebas, el navegador y una copia limpia. Los detalles están en la bitácora de prompts.
