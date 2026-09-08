/**
 * 1. CONFIGURACIÓN Y ESTADO GLOBAL
 */
let resultadosOriginales = [];
let modoFiltroActual = 'and'; // 


/**
 * 2. INICIALIZACIÓN (WINDOW.ONLOAD)
 */
window.onload = async function() {
    const parametros = new URLSearchParams(window.location.search);
    const busqueda = parametros.get('q');
    
    // 2.1. Cargar el total real de datasets para el placeholder del input pequeño
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

    // 2.2. Escuchar cambios en los checkboxes de categoría
    document.querySelectorAll('.filtro-cat').forEach(checkbox => {
        checkbox.addEventListener('change', aplicarFiltrosLocales);
    });

    // 2.3. Asignación de Event Listeners
    
    // Formulario de búsqueda
    const formBusqueda = document.getElementById('formBusquedaInterna');
    if (formBusqueda) {
        formBusqueda.addEventListener('submit', (e) => {
            e.preventDefault();
            ejecutarBusquedaDesdeInput();
        });
    }

    // Select de ordenamiento
    const selectOrdenar = document.getElementById('selectOrdenar');
    if (selectOrdenar) {
        selectOrdenar.addEventListener('change', aplicarOrdenamiento);
    }

    // Botones de la barra lateral (Filtros)
    const btnLimpiar = document.getElementById('btnLimpiar');
    if (btnLimpiar) {
        btnLimpiar.addEventListener('click', limpiarFiltros);
    }

    const btnModoAnd = document.getElementById('btn-modo-and');
    if (btnModoAnd) {
        btnModoAnd.addEventListener('click', () => cambiarModoFiltro('and'));
    }

    const btnModoOr = document.getElementById('btn-modo-or');
    if (btnModoOr) {
        btnModoOr.addEventListener('click', () => cambiarModoFiltro('or'));
    }

    const btnExplorarCat = document.getElementById('btnExplorarCat');
    if (btnExplorarCat) {
        btnExplorarCat.addEventListener('click', toggleFiltrosMovil);
    }

    // Cerrar el modal de la ficha
    document.querySelectorAll('.btn-cerrar-modal').forEach(btn => {
        btn.addEventListener('click', cerrarFichaModal);
    });

    // Delegación de eventos para las tarjetas (que se inyectan dinámicamente)
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

    // 2.4. Evaluar si hay búsqueda por parámetro o cargar el catálogo completo
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

// Petición para búsqueda semántica
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

// Petición para traer todo el catálogo sin IA
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

// Función que se activa al hacer clic en el botón "Buscar" o presionar Enter
function ejecutarBusquedaDesdeInput() {
    const inputSmall = document.getElementById('searchInputResultados');
    if (!inputSmall) return;
    
    const texto = inputSmall.value.trim();
    if (texto === "") {
        window.location.href = "conjunto_datos.html";
    } else {
        window.location.href = `conjunto_datos.html?q=${encodeURIComponent(texto)}`;
    }
}

function cambiarModoFiltro(modo) {
    modoFiltroActual = modo;
    
    const btnAnd = document.getElementById('btn-modo-and');
    const btnOr = document.getElementById('btn-modo-or');
    
    if (!btnAnd || !btnOr) return;

    if (modo === 'and') {
        btnAnd.classList.add('active');
        btnOr.classList.remove('active');
    } else {
        btnOr.classList.add('active');
        btnAnd.classList.remove('active');
    }

    aplicarFiltrosLocales();
}

// Restablecer únicamente los filtros de categoría
function limpiarFiltros(evento) {
    if (evento) evento.preventDefault(); 

    // 1. Desmarca todos los checkboxes de categoría
    document.querySelectorAll('.filtro-cat').forEach(checkbox => {
        checkbox.checked = false;
    });

    // 2. Vuelve a renderizar las tarjetas usando los resultados originales 
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
        if (modoFiltroActual === 'and') {
            return categoriasSeleccionadas.every(cat => 
                item.dependencia.toLowerCase().includes(cat.toLowerCase())
            );
        } else {
            return categoriasSeleccionadas.some(cat => 
                item.dependencia.toLowerCase().includes(cat.toLowerCase())
            );
        }
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
            if (modoFiltroActual === 'and') {
                return categoriasSeleccionadas.every(cat => 
                    item.dependencia.toLowerCase().includes(cat.toLowerCase())
                );
            } else {
                return categoriasSeleccionadas.some(cat => 
                    item.dependencia.toLowerCase().includes(cat.toLowerCase())
                );
            }
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

// Función auxiliar para pintar las tarjetas en el DOM
function renderizarTarjetas(listaItems) {
    const contenedor = document.getElementById('contenedor-tarjetas');
    const textoResultados = document.getElementById('texto-resultados');
    
    if (!contenedor || !textoResultados) return;
    
    contenedor.innerHTML = ''; 
    
    if (listaItems.length === 0) {
        textoResultados.innerHTML = `<strong>0</strong> conjuntos encontrados`;
        contenedor.innerHTML = `
            <div style="background: white; padding: 40px 20px; border-radius: 12px; border: 1px dashed #ccc; text-align: center;">
                <p style="color: #666; margin: 0;">Ningún conjunto de datos coincide con los criterios seleccionados.</p>
            </div>
        `;
        return;
    }

    textoResultados.innerHTML = `<strong>${listaItems.length}</strong> conjuntos encontrados`;
    
    let htmlContent = '';
    
    listaItems.forEach(item => {
        const tituloSeguro = item.dataset_recomendado.replace(/'/g, "\\'");
        
        // Aquí reemplazamos el onclick por los atributos data-
        htmlContent += `
            <article class="card-resultado-v2">
                <div class="card-icon" aria-hidden="true">📁</div>
                <div class="card-body">
                    <header class="badges-container">
                        <span class="badge-dep">${item.dependencia.toUpperCase()}</span>
                        <span class="badge-pub">DOMINIO PÚBLICO</span>
                    </header>
                    <h3>${item.dataset_recomendado}</h3>
                    <p class="card-desc">Conjunto de datos oficial disponible para consulta y descarga municipal.</p>
                    <footer class="card-meta">
                        <span>Secretaría de ${item.dependencia}</span>
                        <span>Actualizado: ${item.fecha_actualizacion}</span>
                        <span>0 descargas</span>
                    </footer>
                </div>
                <div class="card-actions">
                    <div class="format-badges" aria-label="Formatos de descarga disponibles">
                        <a href="${CONFIG.API_BASE_URL}/api/descargar/${item.id}?formato=csv"><span>CSV</span></a>
                        <a href="${CONFIG.API_BASE_URL}/api/descargar/${item.id}?formato=json"><span>JSON</span></a>
                        <a href="${CONFIG.API_BASE_URL}/api/descargar/${item.id}?formato=xml"><span>XML</span></a>
                        <a href="${CONFIG.API_BASE_URL}/api/descargar/${item.id}?formato=geojson"><span>GeoJSON</span></a>
                    </div>
                    <button type="button" class="btn-ficha-v2" 
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
}

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

// Función para actualizar contadores laterales
function actualizarContadores(lista) {
    let conteos = {
        "Seguridad": 0,
        "Salud Pública": 0,
        "Educación": 0,
        "Movilidad y Transporte": 0
    };

    lista.forEach(item => {
        if (conteos[item.dependencia] !== undefined) {
            conteos[item.dependencia]++;
        }
    });

    const elSeguridad = document.getElementById('count-seguridad');
    const elSalud = document.getElementById('count-salud');
    const elEducacion = document.getElementById('count-educacion');
    const elMovilidad = document.getElementById('count-movilidad');

    if (elSeguridad) elSeguridad.textContent = conteos["Seguridad"];
    if (elSalud) elSalud.textContent = conteos["Salud Pública"];
    if (elEducacion) elEducacion.textContent = conteos["Educación"];
    if (elMovilidad) elMovilidad.textContent = conteos["Movilidad y Transporte"];
}

// Función para mostrar u ocultar el panel de filtros en dispositivos móviles
function toggleFiltrosMovil(evento) {
    if (evento) evento.preventDefault();
    
    const sidebar = document.getElementById('sidebarFiltros');
    if (sidebar) {
        sidebar.classList.toggle('activo');
    }
}