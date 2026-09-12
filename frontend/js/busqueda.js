/**
 * 1. CONFIGURACIÓN Y ESTADO GLOBAL
 */
let resultadosOriginales = [];
let paginaActual = 1;
const elementosPorPagina = 10;
let listaEnMemoria = [];

/**
 * 2. INICIALIZACIÓN (WINDOW.ONLOAD)
 */
window.onload = async function() {
    const parametros = new URLSearchParams(window.location.search);
    const busqueda = parametros.get('q');
    
    try {
        const respCat = await fetch(`${CONFIG.API_BASE_URL}/api/catalogos`);
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

    const selectOrdenar = document.getElementById('selectOrdenar');
    if (selectOrdenar) {
        selectOrdenar.addEventListener('change', aplicarOrdenamiento);
    }

    const btnLimpiar = document.getElementById('btnLimpiar');
    if (btnLimpiar) {
        btnLimpiar.addEventListener('click', limpiarFiltros);
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

/**
 * 3. PETICIONES A LA API
 */
async function ejecutarBusquedaAPI(busq) {
    try {
        const respuesta = await fetch(`${CONFIG.API_BASE_URL}/api/buscar?prompt=${encodeURIComponent(busq)}`);
        const data = await respuesta.json();
        
        resultadosOriginales = data.resultados || [];
        actualizarContadores(resultadosOriginales);
        renderizarTarjetas(resultadosOriginales);
    } catch (error) {
        const contenedor = document.getElementById('contenedor-tarjetas');
        if (contenedor) {
            contenedor.innerHTML = '<p style="color:red;">Error de conexión con la API.</p>';
        }
    }
}

async function cargarCatalogoCompleto() {
    try {
        const respuesta = await fetch(`${CONFIG.API_BASE_URL}/api/catalogos`);
        const data = await respuesta.json();
        
        resultadosOriginales = data.resultados || [];
        actualizarContadores(resultadosOriginales);
        renderizarTarjetas(resultadosOriginales);
    } catch (error) {
        const contenedor = document.getElementById('contenedor-tarjetas');
        if (contenedor) {
            contenedor.innerHTML = '<p style="color:red;">Error al cargar el catálogo general.</p>';
        }
    }
}

/**
 * 4. MANEJO DE BÚSQUEDA Y FILTROS
 */
function ejecutarBusquedaDesdeInput() {
    const inputSmall = document.getElementById('searchInputResultados');
    if (!inputSmall) return;
    
    const texto = inputSmall.value.trim();
    if (texto === "") {
        window.location.href = "explorar_datos.html";
    } else {
        window.location.href = `explorar_datos.html?q=${encodeURIComponent(texto)}`;
    }
}

function limpiarFiltros(evento) {
    if (evento) evento.preventDefault(); 
    document.querySelectorAll('.filtro-cat').forEach(checkbox => {
        checkbox.checked = false;
    });
    renderizarTarjetas(resultadosOriginales);
}

function aplicarFiltrosLocales() {
    const checkboxesActivos = document.querySelectorAll('.filtro-cat:checked');
    const categoriasSeleccionadas = Array.from(checkboxesActivos).map(cb => cb.value);

    if (categoriasSeleccionadas.length === 0) {
        renderizarTarjetas(resultadosOriginales);
        return;
    }

    const resultadosFiltrados = resultadosOriginales.filter(item => {
        const catItem = item.categoria || "General";
        return categoriasSeleccionadas.includes(catItem);
    });

    renderizarTarjetas(resultadosFiltrados);
}

function aplicarOrdenamiento() {
    const selectOrdenar = document.getElementById('selectOrdenar');
    if (!selectOrdenar) return;

    const criterio = selectOrdenar.value;
    let listaActual = [...resultadosOriginales];
    
    const checkboxesActivos = document.querySelectorAll('.filtro-cat:checked');
    const categoriasSeleccionadas = Array.from(checkboxesActivos).map(cb => cb.value);
    
    if (categoriasSeleccionadas.length > 0) {
        listaActual = listaActual.filter(item => {
            const catItem = item.categoria || "General";
            return categoriasSeleccionadas.includes(catItem);
        });
    }

    if (criterio === 'alfabetico') {
        listaActual.sort((a, b) => a.dataset_recomendado.localeCompare(b.dataset_recomendado));
    } else if (criterio === 'recientes') {
        listaActual.sort((a, b) => new Date(b.fecha_actualizacion) - new Date(a.fecha_actualizacion));
    }

    renderizarTarjetas(listaActual);
}

/**
 * 5. RENDERIZADO Y UI
 */
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
                <input type="checkbox" class="filtro-cat" value="${cat}" ${isChecked}> 
                <span title="${cat}">${cat}</span> 
                <span>${conteosCat[cat]}</span>
            </label>
        `;
    });

    contenedorFiltros.innerHTML = htmlFiltros;

    document.querySelectorAll('.filtro-cat').forEach(checkbox => {
        checkbox.addEventListener('change', aplicarFiltrosLocales);
    });
}

function actualizarContadores(lista) {
    renderizarFiltrosDependencias(lista);
}

function renderizarTarjetas(listaItems) {
    listaEnMemoria = listaItems;
    paginaActual = 1;
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
    textoResultados.innerHTML = `<strong>${listaEnMemoria.length}</strong> conjuntos encontrados`;

    // Calcular límites de la paginación
    const totalPaginas = Math.ceil(listaEnMemoria.length / elementosPorPagina);
    if (paginaActual > totalPaginas) paginaActual = totalPaginas;
    if (paginaActual < 1) paginaActual = 1;

    const inicio = (paginaActual - 1) * elementosPorPagina;
    const fin = inicio + elementosPorPagina;
    const itemsPagina = listaEnMemoria.slice(inicio, fin);
    
    let htmlContent = '';
    
    itemsPagina.forEach(item => {
        const tituloSeguro = item.dataset_recomendado.replace(/'/g, "\\'");
        const descripcionSegura = item.descripcion || "Conjunto de datos oficial disponible para consulta y descarga municipal.";
        
        htmlContent += `
            <article class="card-resultado-v2">
                <div class="card-icon" aria-hidden="true">📁</div>
                <div class="card-body">
                    <header class="badges-container">
                        <span class="badge-dep">${item.dependencia.toUpperCase()}</span>
                        <span class="badge-pub">DOMINIO PÚBLICO</span>
                    </header>
                    <h3>${item.dataset_recomendado}</h3>
                    <p class="card-desc">${descripcionSegura}</p>
                    <footer class="card-meta">
                        <span>Categoría: ${item.categoria || "General"}</span>
                        <span>Actualizado: ${item.fecha_actualizacion}</span>
                        <span>${item.descargas !== undefined ? item.descargas : 0} descargas</span>
                    </footer>
                </div>
                <div class="card-actions">
                    <div class="format-badges" aria-label="Formatos de descarga disponibles">
                        <a href="${CONFIG.API_BASE_URL}/api/descargar/${item.id}?formato=csv"><span>CSV</span></a>
                        <a href="${CONFIG.API_BASE_URL}/api/descargar/${item.id}?formato=json"><span>JSON</span></a>
                        <a href="${CONFIG.API_BASE_URL}/api/descargar/${item.id}?formato=xml"><span>XML</span></a>
                        <a href="${CONFIG.API_BASE_URL}/api/descargar/${item.id}?formato=geojson"><span>GeoJSON</span></a>
                    </div>
                    <button type="button" class="btn-ficha" 
                        data-titulo="${tituloSeguro}" 
                        data-dependencia="${item.dependencia}" 
                        data-fecha="${item.fecha_actualizacion}" 
                        data-id="${item.id}">
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
            
            // Habilitar/Deshabilitar flechas
            btnAnterior.disabled = paginaActual === 1;
            btnSiguiente.disabled = paginaActual === totalPaginas;

            // Limpiar y generar números de página
            contenedorNumeros.innerHTML = '';
            for (let i = 1; i <= totalPaginas; i++) {
                const btnNum = document.createElement('button');
                btnNum.type = 'button';
                // Asignar clase 'active' si es la página actual
                btnNum.className = `btn-num-pag ${i === paginaActual ? 'active' : ''}`;
                btnNum.textContent = i;
                
                // Evento para saltar a la página específica
                btnNum.addEventListener('click', () => {
                    paginaActual = i;
                    mostrarPaginaActual();
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
        window.scrollTo({ top: 0, behavior: 'smooth' }); // Sube suavemente al inicio
    }
});

document.getElementById('btnPagSiguiente')?.addEventListener('click', () => {
    const totalPaginas = Math.ceil(listaEnMemoria.length / elementosPorPagina);
    if (paginaActual < totalPaginas) {
        paginaActual++;
        mostrarPaginaActual();
        window.scrollTo({ top: 0, behavior: 'smooth' }); // Sube suavemente al inicio
    }
});

function verFichaDetalle(titulo, dependencia, fecha, idDataset) {
    document.getElementById('modalTitulo').textContent = titulo;
    document.getElementById('modalDependencia').textContent = dependencia;
    document.getElementById('modalFecha').textContent = fecha;
    
    const contenedorDescargas = document.getElementById('modalDownloadLinks');
    contenedorDescargas.innerHTML = `
        <a href="${CONFIG.API_BASE_URL}/api/descargar/${idDataset}?formato=csv" class="modal-badge-fmt" style="text-decoration:none; color: var(--blue-dark); transition: 0.2s;">CSV</a>
        <a href="${CONFIG.API_BASE_URL}/api/descargar/${idDataset}?formato=json" class="modal-badge-fmt" style="text-decoration:none; color: var(--blue-dark); transition: 0.2s;">JSON</a>
        <a href="${CONFIG.API_BASE_URL}/api/descargar/${idDataset}?formato=xml" class="modal-badge-fmt" style="text-decoration:none; color: var(--blue-dark); transition: 0.2s;">XML</a>
        <a href="${CONFIG.API_BASE_URL}/api/descargar/${idDataset}?formato=geojson" class="modal-badge-fmt" style="text-decoration:none; color: var(--blue-dark); transition: 0.2s;">GeoJSON</a>
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