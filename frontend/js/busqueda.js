//0. UTILIDADES
function escaparHTML(texto) {
    if (texto === null || texto === undefined) return "";
    const div = document.createElement("div");
    div.textContent = String(texto);
    return div.innerHTML;
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

    // 3. Categorías activas
    const checkboxesActivos = document.querySelectorAll('.filtro-cat:checked');
    const cats = Array.from(checkboxesActivos).map(cb => cb.value);
    if (cats.length > 0) {
        params.set('cat', cats.join(','));
    } else {
        params.delete('cat');
    }

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
    }

    document.querySelectorAll('.btn-cerrar-modal').forEach(btn => {
        btn.addEventListener('click', cerrarFichaModal);
    });

    const contenedorTarjetas = document.getElementById('contenedor-tarjetas');
    if (contenedorTarjetas) {
        contenedorTarjetas.addEventListener('click', (e) => {
            if (e.target.classList.contains('btn-ficha')) {
                const titulo = e.target.getAttribute('data-titulo');
                const dependencia = e.target.getAttribute('data-dependencia');
                const fecha = e.target.getAttribute('data-fecha');
                const idDataset = e.target.getAttribute('data-id');
                verFichaDetalle(titulo, dependencia, fecha, idDataset);
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
    const catParam = params.get('cat');

    if (catParam) {
        const cats = catParam.split(',').map(c => decodeURIComponent(c));
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
    if (selectOrdenar) selectOrdenar.value = '';

    paginaActual = 1;
    aplicarFiltrosLocales(true);
}

function aplicarFiltrosLocales(actualizarUrl = true) {
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
                <input type="checkbox" class="filtro-cat" value="${escaparHTML(cat)}" ${isChecked}> 
                <span title="${escaparHTML(cat)}">${escaparHTML(cat)}</span> 
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
        const fecha = item.fecha_actualizacion || "";
        const idSeguro = encodeURIComponent(item.id);
        
        htmlContent += `
            <article class="card-resultado-v2">
                <div class="card-icon" aria-hidden="true">📁</div>
                <div class="card-body">
                    <header class="badges-container">
                        <span class="badge-dep">${escaparHTML(dependencia.toUpperCase())}</span>
                        <span class="badge-pub">DOMINIO PÚBLICO</span>
                    </header>
                    <h3>${escaparHTML(titulo)}</h3>
                    <p class="card-desc">${escaparHTML(descripcion)}</p>
                    <footer class="card-meta">
                        <span>Categoría: ${escaparHTML(categoria)}</span>
                        <span>Actualizado: ${escaparHTML(fecha)}</span>
                        <span>${Number(item.descargas) || 0} descargas</span>
                    </footer>
                </div>
                <div class="card-actions">
                    <div class="format-badges" aria-label="Formatos de descarga disponibles">
                        <a href="/api/descargar/${idSeguro}?formato=csv"><span>CSV</span></a>
                        <a href="/api/descargar/${idSeguro}?formato=json"><span>JSON</span></a>
                        <a href="/api/descargar/${idSeguro}?formato=xml"><span>XML</span></a>
                        <a href="/api/descargar/${idSeguro}?formato=geojson"><span>GeoJSON</span></a>
                    </div>
                    <button type="button" class="btn-ficha" 
                        data-titulo="${escaparHTML(titulo)}" 
                        data-dependencia="${escaparHTML(dependencia)}" 
                        data-fecha="${escaparHTML(fecha)}" 
                        data-id="${idSeguro}">
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

function verFichaDetalle(titulo, dependencia, fecha, idDataset) {
    document.getElementById('modalTitulo').textContent = titulo;
    document.getElementById('modalDependencia').textContent = dependencia;
    document.getElementById('modalFecha').textContent = fecha;
    
    const idSeguro = encodeURIComponent(idDataset);
    const contenedorDescargas = document.getElementById('modalDownloadLinks');
    contenedorDescargas.innerHTML = `
        <a href="/api/descargar/${idSeguro}?formato=csv" class="modal-badge-fmt" style="text-decoration:none; color: var(--blue-dark); transition: 0.2s;">CSV</a>
        <a href="/api/descargar/${idSeguro}?formato=json" class="modal-badge-fmt" style="text-decoration:none; color: var(--blue-dark); transition: 0.2s;">JSON</a>
        <a href="/api/descargar/${idSeguro}?formato=xml" class="modal-badge-fmt" style="text-decoration:none; color: var(--blue-dark); transition: 0.2s;">XML</a>
        <a href="/api/descargar/${idSeguro}?formato=geojson" class="modal-badge-fmt" style="text-decoration:none; color: var(--blue-dark); transition: 0.2s;">GeoJSON</a>
    `;
    
    document.getElementById('modalFicha').style.display = 'flex';
}

function cerrarFichaModal() {
    document.getElementById('modalFicha').style.display = 'none';
}

function alternarSidebarFiltros(evento) {
    if (evento) evento.preventDefault();
    const sidebar = document.getElementById('sidebarFiltros');
    if (sidebar) {
        sidebar.classList.toggle('oculto');
        sidebar.classList.toggle('activo');
    }
}