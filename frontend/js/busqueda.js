//0. UTILIDADES
function escaparHTML(texto) {
    if (texto === null || texto === undefined) return "";
    const div = document.createElement("div");
    div.textContent = String(texto);
    return div.innerHTML;
}

// Para valores dentro de atributos HTML (data-*, value, title): además de lo que
// escapa escaparHTML, neutraliza las comillas para evitar romper el atributo.
function escaparAtributo(texto) {
    return escaparHTML(texto).replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// 1. CONFIGURACIÓN Y ESTADO GLOBAL

let resultadosOriginales = [];
let paginaActual = 1;
const elementosPorPagina = 10;
let listaEnMemoria = [];

// Sincroniza el estado actual con la barra de direcciones sin recargar
function sincronizarURL() {
    const params = new URLSearchParams(window.location.search);

    // 1. Paginación
    if (paginaActual > 1) {
        params.set('p', paginaActual);
    } else {
        params.delete('p');
    }

    // 2. Ordenamiento
    const selectOrdenar = document.getElementById('selectOrdenar');
    if (selectOrdenar && selectOrdenar.value) {
        params.set('orden', selectOrdenar.value);
    } else {
        params.delete('orden');
    }

    // 3. Categorías activas (un parámetro 'cat' por categoría, así soporta comas y símbolos)
    const checkboxesActivos = document.querySelectorAll('.filtro-cat:checked');
    const cats = Array.from(checkboxesActivos).map(cb => cb.value);
    params.delete('cat');
    cats.forEach(c => params.append('cat', c));

    const nuevaURL = `${window.location.pathname}${params.toString() ? '?' + params.toString() : ''}`;
    window.history.replaceState(null, '', nuevaURL);
}

//2. INICIALIZACIÓN (WINDOW.ONLOAD)

window.onload = async function() {
    const parametros = new URLSearchParams(window.location.search);
    const busqueda = parametros.get('q');
    const ordenUrl = parametros.get('orden');
    const pagUrl = parseInt(parametros.get('p'), 10);

    // Restaurar select de orden si viene en la URL
    const selectOrdenar = document.getElementById('selectOrdenar');
    if (selectOrdenar && ordenUrl) {
        selectOrdenar.value = ordenUrl;
    }

    // Restaurar página si es válida
    if (!isNaN(pagUrl) && pagUrl > 1) {
        paginaActual = pagUrl;
    }

    try {
        const respCat = await fetch(`/api/catalogos`);
        const dataCat = await respCat.json();
        const total = dataCat.resultados ? dataCat.resultados.length : 0;
        const inputSmall = document.getElementById('searchInputResultados');
        if (inputSmall && !busqueda) {
            inputSmall.placeholder = `Buscar en ${total} conjuntos de datos...`;
        }
    } catch (e) {
        console.error("Error cargando total de catálogos:", e);
    }

    const formBusqueda = document.getElementById('formBusquedaInterna');
    if (formBusqueda) {
        formBusqueda.addEventListener('submit', (e) => {
            e.preventDefault();
            ejecutarBusquedaDesdeInput();
        });
    }

    if (selectOrdenar) {
        selectOrdenar.addEventListener('change', () => {
            paginaActual = 1;
            aplicarOrdenamiento();
            sincronizarURL();
        });
    }

    const btnLimpiar = document.getElementById('btnLimpiar');
    if (btnLimpiar) {
        btnLimpiar.addEventListener('click', limpiarFiltros);
    }

    const btnLimpiarEmpty = document.getElementById('btnLimpiarEmpty');
    if (btnLimpiarEmpty) {
        btnLimpiarEmpty.addEventListener('click', () => {
            // Limpia la búsqueda y recarga el catálogo completo desde cero
            window.location.href = '/explorar_datos.html';
        });
    }

    const btnExplorarCat = document.getElementById('btnExplorarCat');
    if (btnExplorarCat) {
        btnExplorarCat.addEventListener('click', alternarSidebarFiltros);
        sincronizarBotonFiltros();
    }

    document.querySelectorAll('.btn-cerrar-modal').forEach(btn => {
        btn.addEventListener('click', cerrarFichaModal);
    });

    const contenedorTarjetas = document.getElementById('contenedor-tarjetas');
    if (contenedorTarjetas) {
        contenedorTarjetas.addEventListener('click', (e) => {
            if (e.target.classList.contains('btn-ficha')) {
                verFichaDetalle(e.target.getAttribute('data-id'));
            }
        });
    }

    if (busqueda && busqueda.trim() !== "") {
        const inputSmall = document.getElementById('searchInputResultados');
        if (inputSmall) inputSmall.value = busqueda;
        await ejecutarBusquedaAPI(busqueda);
    } else {
        const textoResultados = document.getElementById('texto-resultados');
        if (textoResultados) {
            textoResultados.innerHTML = `<strong>Cargando catálogo...</strong>`;
        }
        await cargarCatalogoCompleto();
    }
};

//3. PETICIONES A LA API

async function ejecutarBusquedaAPI(busq) {
    const contenedor = document.getElementById('contenedor-tarjetas');
    const textoResultados = document.getElementById('texto-resultados');
    const paginacionContenedor = document.getElementById('paginacionContenedor');
    const emptyState = document.getElementById('emptyState');

    if (emptyState) emptyState.style.display = 'none';
    if (paginacionContenedor) paginacionContenedor.style.display = 'none';

    if (textoResultados) {
        textoResultados.innerHTML = `<span>Buscando datos sobre <strong>"${escaparHTML(busq)}"</strong>...</span>`;
    }

    const btnRestablecer = document.getElementById('btnRestablecerBusqueda');
    if (btnRestablecer) {
        btnRestablecer.style.display = 'inline-flex';
    }

    if (contenedor) {
        contenedor.innerHTML = `
            <article class="card-resultado-v2" style="text-align: center; padding: 2.5rem 1.5rem; justify-content: center; align-items: center;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">⏳</div>
                <h3 style="margin-bottom: 0.25rem;">Analizando consulta con IA semántica...</h3>
                <p style="color: #666; font-size: 0.9rem; margin: 0;">Comparando embeddings vectoriales contra el catálogo municipal.</p>
            </article>
        `;
    }

    try {
        const respuesta = await fetch(`/api/buscar?prompt=${encodeURIComponent(busq)}`);

        // Límite de peticiones alcanzado (slowapi): no confundirlo con "sin resultados"
        if (respuesta.status === 429) {
            if (contenedor) {
                contenedor.innerHTML = '<p style="text-align:center; padding: 2rem;">Demasiadas búsquedas seguidas. Espera un minuto e inténtalo de nuevo.</p>';
            }
            if (textoResultados) {
                textoResultados.innerHTML = '<strong>Límite de búsquedas alcanzado</strong>';
            }
            return;
        }

        const data = await respuesta.json();

        resultadosOriginales = data.resultados || [];
        actualizarContadores(resultadosOriginales);
        restaurarFiltrosDesdeURL();
    } catch (error) {
        if (contenedor) {
            contenedor.innerHTML = '<p style="color:red; text-align:center; padding: 2rem;">Error de conexión con la API de búsqueda semántica.</p>';
        }
        if (textoResultados) {
            textoResultados.innerHTML = '<strong>Error en la consulta</strong>';
        }
    }
}

async function cargarCatalogoCompleto() {
    try {
        const respuesta = await fetch(`/api/catalogos`);
        const data = await respuesta.json();

        resultadosOriginales = data.resultados || [];
        actualizarContadores(resultadosOriginales);
        restaurarFiltrosDesdeURL();
    } catch (error) {
        const contenedor = document.getElementById('contenedor-tarjetas');
        if (contenedor) {
            contenedor.innerHTML = '<p style="color:red;">Error al cargar el catálogo general.</p>';
        }
    }
}

//4. MANEJO DE BÚSQUEDA Y FILTROS
function ejecutarBusquedaDesdeInput() {
    const inputSmall = document.getElementById('searchInputResultados');
    if (!inputSmall) return;

    const texto = inputSmall.value.trim();
    if (texto === "") {
        window.location.href = "/explorar_datos.html";
    } else {
        window.location.href = `/explorar_datos.html?q=${encodeURIComponent(texto)}`;
    }
}

function restaurarFiltrosDesdeURL() {
    const params = new URLSearchParams(window.location.search);
    // getAll ya devuelve los valores decodificados: no hace falta decodeURIComponent
    const cats = params.getAll('cat');

    if (cats.length > 0) {
        document.querySelectorAll('.filtro-cat').forEach(cb => {
            if (cats.includes(cb.value)) {
                cb.checked = true;
            }
        });
    }

    aplicarFiltrosLocales(false);
}

function limpiarFiltros(evento) {
    if (evento) evento.preventDefault();
    document.querySelectorAll('.filtro-cat').forEach(checkbox => {
        checkbox.checked = false;
    });
    const selectOrdenar = document.getElementById('selectOrdenar');
    if (selectOrdenar) selectOrdenar.value = 'coincidencia';

    paginaActual = 1;
    aplicarFiltrosLocales(true);
}

function aplicarFiltrosLocales(actualizarUrl = true) {
    actualizarContadorFiltros();
    const checkboxesActivos = document.querySelectorAll('.filtro-cat:checked');
    const categoriasSeleccionadas = Array.from(checkboxesActivos).map(cb => cb.value);

    let datosProcesados = [...resultadosOriginales];

    if (categoriasSeleccionadas.length > 0) {
        datosProcesados = datosProcesados.filter(item => {
            const catItem = item.categoria || "General";
            return categoriasSeleccionadas.includes(catItem);
        });
    }

    // Respetar ordenamiento activo
    const selectOrdenar = document.getElementById('selectOrdenar');
    const criterio = selectOrdenar ? selectOrdenar.value : '';

    if (criterio === 'alfabetico') {
        datosProcesados.sort((a, b) => (a.dataset_recomendado || "").localeCompare(b.dataset_recomendado || ""));
    } else if (criterio === 'recientes') {
        datosProcesados.sort((a, b) => new Date(b.fecha_actualizacion) - new Date(a.fecha_actualizacion));
    }

    listaEnMemoria = datosProcesados;

    const totalPaginas = Math.ceil(listaEnMemoria.length / elementosPorPagina) || 1;
    if (paginaActual > totalPaginas) paginaActual = 1;

    mostrarPaginaActual();

    if (actualizarUrl) {
        sincronizarURL();
    }
}

function aplicarOrdenamiento() {
    aplicarFiltrosLocales(true);
}

//5. RENDERIZADO Y UI
function renderizarFiltrosDependencias(lista) {
    const contenedorFiltros = document.getElementById('contenedor-filtros-dependencias');
    if (!contenedorFiltros) return;

    let conteosCat = {};
    lista.forEach(item => {
        const cat = item.categoria || "General";
        conteosCat[cat] = (conteosCat[cat] || 0) + 1;
    });

    const checkboxesActivos = document.querySelectorAll('.filtro-cat:checked');
    const seleccionadasPrevias = Array.from(checkboxesActivos).map(cb => cb.value);

    let htmlFiltros = '';
    Object.keys(conteosCat).sort().forEach(cat => {
        const isChecked = seleccionadasPrevias.includes(cat) ? 'checked' : '';
        htmlFiltros += `
            <label class="filter-item">
                <input type="checkbox" class="filtro-cat" value="${escaparAtributo(cat)}" ${isChecked}> 
                <span title="${escaparAtributo(cat)}">${escaparHTML(cat)}</span> 
                <span>${conteosCat[cat]}</span>
            </label>
        `;
    });

    contenedorFiltros.innerHTML = htmlFiltros;

    document.querySelectorAll('.filtro-cat').forEach(checkbox => {
        checkbox.addEventListener('change', () => {
            paginaActual = 1;
            aplicarFiltrosLocales(true);
        });
    });
}

function actualizarContadores(lista) {
    renderizarFiltrosDependencias(lista);
}

function renderizarTarjetas(listaItems) {
    listaEnMemoria = listaItems;
    mostrarPaginaActual();
}

function mostrarPaginaActual() {
    const contenedor = document.getElementById('contenedor-tarjetas');
    const textoResultados = document.getElementById('texto-resultados');
    const emptyState = document.getElementById('emptyState');
    const paginacionContenedor = document.getElementById('paginacionContenedor');

    if (!contenedor || !textoResultados) return;

    contenedor.innerHTML = '';

    if (listaEnMemoria.length === 0) {
        textoResultados.innerHTML = `<strong>0</strong> conjuntos encontrados`;
        if (emptyState) emptyState.style.display = 'flex';
        if (paginacionContenedor) paginacionContenedor.style.display = 'none';
        return;
    }

    if (emptyState) emptyState.style.display = 'none';

    const params = new URLSearchParams(window.location.search);
    const hayBusquedaActiva = params.has('q') && params.get('q').trim() !== '';

    textoResultados.innerHTML = `<strong>${listaEnMemoria.length}</strong> conjuntos encontrados`;

    const btnRestablecer = document.getElementById('btnRestablecerBusqueda');
    if (btnRestablecer) {
        btnRestablecer.style.display = hayBusquedaActiva ? 'inline-flex' : 'none';
    }

    const totalPaginas = Math.ceil(listaEnMemoria.length / elementosPorPagina);
    if (paginaActual > totalPaginas) paginaActual = totalPaginas;
    if (paginaActual < 1) paginaActual = 1;

    const inicio = (paginaActual - 1) * elementosPorPagina;
    const fin = inicio + elementosPorPagina;
    const itemsPagina = listaEnMemoria.slice(inicio, fin);

    let htmlContent = '';

    itemsPagina.forEach(item => {
        const titulo = item.dataset_recomendado || "";
        const descripcion = item.descripcion || "Conjunto de datos oficial disponible para consulta y descarga municipal.";
        const dependencia = item.dependencia || "";
        const categoria = item.categoria || "General";
        const fecha = item.fecha_actualizacion || "Sin fecha";
        const idSeguro = encodeURIComponent(item.id);
        const descargas = Number(item.descargas) || 0;

        // El título va primero porque es lo que decide el clic; la dependencia, debajo y sin mayúsculas
        htmlContent += `
            <article class="card-resultado-v2">
                <div class="card-body">
                    <h3>${escaparHTML(titulo)}</h3>
                    <p class="card-dependencia">
                        ${escaparHTML(dependencia)}
                        <span class="badge-pub">Dominio público</span>
                    </p>
                    <p class="card-desc">${escaparHTML(descripcion)}</p>
                    <ul class="card-meta">
                        <li>Categoría: ${escaparHTML(categoria)}</li>
                        <li>Actualizado: ${escaparHTML(fecha)}</li>
                        ${descargas > 0 ? `<li>${descargas} ${descargas === 1 ? 'descarga' : 'descargas'}</li>` : ''}
                    </ul>
                </div>
                <div class="card-actions">
                    ${enlacesDescarga(idSeguro, titulo)}
                    <button type="button" class="btn-ficha" data-id="${escaparAtributo(item.id)}">
                        Ver ficha
                    </button>
                </div>
            </article>
        `;
    });

    contenedor.innerHTML = htmlContent;

    if (paginacionContenedor) {
        if (totalPaginas > 1) {
            paginacionContenedor.style.display = 'flex';

            const btnAnterior = document.getElementById('btnPagAnterior');
            const btnSiguiente = document.getElementById('btnPagSiguiente');
            const contenedorNumeros = document.getElementById('numerosPaginacion');

            btnAnterior.disabled = paginaActual === 1;
            btnSiguiente.disabled = paginaActual === totalPaginas;

            contenedorNumeros.innerHTML = '';
            for (let i = 1; i <= totalPaginas; i++) {
                const btnNum = document.createElement('button');
                btnNum.type = 'button';
                btnNum.className = `btn-num-pag ${i === paginaActual ? 'active' : ''}`;
                btnNum.textContent = i;

                btnNum.addEventListener('click', () => {
                    paginaActual = i;
                    mostrarPaginaActual();
                    sincronizarURL();
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                });

                contenedorNumeros.appendChild(btnNum);
            }
        } else {
            paginacionContenedor.style.display = 'none';
        }
    }
}

document.getElementById('btnPagAnterior')?.addEventListener('click', () => {
    if (paginaActual > 1) {
        paginaActual--;
        mostrarPaginaActual();
        sincronizarURL();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
});

document.getElementById('btnPagSiguiente')?.addEventListener('click', () => {
    const totalPaginas = Math.ceil(listaEnMemoria.length / elementosPorPagina);
    if (paginaActual < totalPaginas) {
        paginaActual++;
        mostrarPaginaActual();
        sincronizarURL();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
});

const FORMATOS_DESCARGA = [['csv', 'CSV'], ['json', 'JSON'], ['xml', 'XML'], ['geojson', 'GeoJSON']];

// Botones de descarga; los usan la tarjeta y la ficha. El aria-label dice qué dataset se descarga,
// porque "CSV" repetido en cada tarjeta no basta para un lector de pantalla
function enlacesDescarga(idSeguro, titulo) {
    const enlaces = FORMATOS_DESCARGA.map(([formato, etiqueta]) =>
        `<a class="btn-formato" href="/api/descargar/${idSeguro}?formato=${formato}" aria-label="Descargar ${escaparAtributo(titulo)} en ${etiqueta}">${etiqueta}</a>`
    ).join('');
    return `<div class="format-badges" role="group" aria-label="Formatos de descarga">${enlaces}</div>`;
}

let elementoAntesDelModal = null;

function verFichaDetalle(idDataset) {
    const item = resultadosOriginales.find(d => String(d.id) === String(idDataset));
    if (!item) return;

    const titulo = item.dataset_recomendado || "";
    document.getElementById('modalTitulo').textContent = titulo;
    document.getElementById('modalDescripcion').textContent = item.descripcion || "Sin descripción disponible.";
    document.getElementById('modalDependencia').textContent = item.dependencia || "No registrada";
    document.getElementById('modalCategoria').textContent = item.categoria || "General";
    document.getElementById('modalFecha').textContent = item.fecha_actualizacion || "Sin fecha";
    document.getElementById('modalDownloadLinks').innerHTML = enlacesDescarga(encodeURIComponent(item.id), titulo);

    elementoAntesDelModal = document.activeElement;
    document.getElementById('modalFicha').style.display = 'flex';
    document.querySelector('#modalFicha .modal-close')?.focus(); // El foco entra al diálogo para teclado y lectores de pantalla

    cargarVistaPrevia(item.id);
}

async function cargarVistaPrevia(idDataset) {
    const contenedor = document.getElementById('modalVistaPrevia');
    contenedor.innerHTML = '<p class="vista-previa-estado">Cargando vista previa…</p>';
    try {
        const respuesta = await fetch(`/api/datasets/${encodeURIComponent(idDataset)}/vista-previa`);
        if (!respuesta.ok) throw new Error(respuesta.status);
        const data = await respuesta.json();

        const encabezados = data.columnas.map(c => `<th scope="col">${escaparHTML(c)}</th>`).join('');
        const filas = data.filas.map(fila => `<tr>${fila.map(v => `<td>${escaparHTML(v)}</td>`).join('')}</tr>`).join('');
        contenedor.innerHTML = `
            <p class="vista-previa-estado">${data.total_filas} ${data.total_filas === 1 ? 'fila' : 'filas'} · ${data.total_columnas} columnas. Primeras ${data.filas.length}:</p>
            <div class="vista-previa-tabla" tabindex="0" role="region" aria-label="Vista previa de los datos">
                <table><thead><tr>${encabezados}</tr></thead><tbody>${filas}</tbody></table>
            </div>`;
    } catch (error) {
        contenedor.innerHTML = '<p class="vista-previa-estado">No se pudo cargar la vista previa. Puedes descargar el archivo completo.</p>';
    }
}

function cerrarFichaModal() {
    document.getElementById('modalFicha').style.display = 'none';
    elementoAntesDelModal?.focus(); // Regresa el foco al botón "Ver ficha" que abrió el diálogo
}

document.addEventListener('keydown', (e) => {
    const modal = document.getElementById('modalFicha');
    if (e.key === 'Escape' && modal && modal.style.display === 'flex') cerrarFichaModal();
});

function alternarSidebarFiltros(evento) {
    if (evento) evento.preventDefault();
    const sidebar = document.getElementById('sidebarFiltros');
    if (sidebar) {
        sidebar.classList.toggle('oculto');
        sidebar.classList.toggle('activo');
        sincronizarBotonFiltros();
    }
}

// aria-expanded según si el panel de filtros se ve (en móvil empieza oculto, en escritorio visible)
function sincronizarBotonFiltros() {
    const sidebar = document.getElementById('sidebarFiltros');
    const boton = document.getElementById('btnExplorarCat');
    if (sidebar && boton) boton.setAttribute('aria-expanded', getComputedStyle(sidebar).display !== 'none');
}

// Número de filtros activos junto al botón, para que se note que hay resultados filtrados aunque el panel esté oculto
function actualizarContadorFiltros() {
    const contador = document.getElementById('contadorFiltros');
    if (!contador) return;
    const activos = document.querySelectorAll('.filtro-cat:checked').length;
    contador.textContent = activos;
    contador.hidden = activos === 0;
}