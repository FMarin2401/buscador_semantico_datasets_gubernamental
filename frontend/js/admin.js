// Definir el token global para todas las peticiones
const token = localStorage.getItem("authToken");

// Variables de paginación y filtro para el catálogo administrativo
let datasetsCatalogo = [];
let datasetsFiltrados = [];
let paginaActualAdmin = 1;
const ITEMS_POR_PAGINA_ADMIN = 10;

// Variables de paginación para el buzón ciudadano
let mensajesBuzon = [];
let paginaActualMensajes = 1;
const ITEMS_POR_PAGINA_MENSAJES = 10;

// Controlar el historial (Back/Forward Cache) y revelar el panel
window.addEventListener("pageshow", (event) => {
    const tokenActual = localStorage.getItem("authToken");
    if (!tokenActual) {
        window.location.replace("/login.html");
    } else {
        const panel = document.querySelector('.admin-layout');
        if (panel) panel.style.display = 'flex';
    }
});

document.addEventListener('DOMContentLoaded', () => {
    // 1. Poblar dependencias y categorías dinámicas en los selectores
    poblarOpcionesDinamicas();

    // 2. Configurar botones del menú lateral
    const botonesMenu = document.querySelectorAll('button.admin-tab-btn');
    botonesMenu.forEach(boton => {
        boton.addEventListener('click', function() {
            const destino = this.getAttribute('data-target');
            if (destino) cambiarPestana(destino, this);
        });
    });

    // 3. Configurar formulario de subida de datasets
    const formSubir = document.getElementById('formSubirDataset');
    if (formSubir) formSubir.addEventListener('submit', manejarSubidaDataset);

    // 4. Configurar filtro de búsqueda en tiempo real sobre el catálogo
    const inputBuscar = document.getElementById('inputBuscarAdmin');
    if (inputBuscar) {
        inputBuscar.addEventListener('input', (e) => {
            const termino = e.target.value.toLowerCase().trim();
            datasetsFiltrados = datasetsCatalogo.filter(item => 
                item.titulo.toLowerCase().includes(termino) || 
                item.dependencia.toLowerCase().includes(termino)
            );
            paginaActualAdmin = 1;
            renderizarTablaPaginada();
        });
    }

    // 5. Configurar acciones en la tabla de gestión de datasets (borrar o editar)
    const tablaCuerpo = document.getElementById('tablaCuerpoDatasets');
    if (tablaCuerpo) {
        tablaCuerpo.addEventListener('click', function(e) {
            if (e.target.classList.contains('btn-borrar-dataset')) {
                const idDataset = e.target.getAttribute('data-id');
                eliminarDataset(idDataset);
            } else if (e.target.classList.contains('btn-editar-dataset')) {
                const id = e.target.getAttribute('data-id');
                const titulo = e.target.getAttribute('data-titulo');
                const descripcion = e.target.getAttribute('data-descripcion');
                const dependencia = e.target.getAttribute('data-dependencia');
                const categoria = e.target.getAttribute('data-categoria');
                abrirModalEdicion(id, titulo, descripcion, dependencia, categoria);
            }
        });
    }

    // 6. Configurar acciones en la tabla de mensajes (borrar mensaje)
    const tablaMensajes = document.getElementById('tablaCuerpoMensajes');
    if (tablaMensajes) {
        tablaMensajes.addEventListener('click', function(e) {
            if (e.target.classList.contains('btn-borrar-mensaje')) {
                const idMensaje = e.target.getAttribute('data-id');
                eliminarMensajeAdmin(idMensaje);
            }
        });
    }

    // 7. Configurar botones de paginación del catálogo
    const btnAnt = document.getElementById('btnAdminPagAnterior');
    const btnSig = document.getElementById('btnAdminPagSiguiente');

    if (btnAnt) {
        btnAnt.addEventListener('click', () => {
            if (paginaActualAdmin > 1) {
                paginaActualAdmin--;
                renderizarTablaPaginada();
            }
        });
    }

    if (btnSig) {
        btnSig.addEventListener('click', () => {
            const totalPaginas = Math.ceil(datasetsFiltrados.length / ITEMS_POR_PAGINA_ADMIN);
            if (paginaActualAdmin < totalPaginas) {
                paginaActualAdmin++;
                renderizarTablaPaginada();
            }
        });
    }

    // 8. Configurar botones de paginación del buzón ciudadano
    const btnAntMsg = document.getElementById('btnMensajesPagAnterior');
    const btnSigMsg = document.getElementById('btnMensajesPagSiguiente');

    if (btnAntMsg) {
        btnAntMsg.addEventListener('click', () => {
            if (paginaActualMensajes > 1) {
                paginaActualMensajes--;
                renderizarTablaMensajesPaginada();
            }
        });
    }

    if (btnSigMsg) {
        btnSigMsg.addEventListener('click', () => {
            const totalPaginas = Math.ceil(mensajesBuzon.length / ITEMS_POR_PAGINA_MENSAJES);
            if (paginaActualMensajes < totalPaginas) {
                paginaActualMensajes++;
                renderizarTablaMensajesPaginada();
            }
        });
    }

    // 9. Configurar exportación de bitácora
    const btnExportar = document.getElementById('btnExportarAuditoria');
    if (btnExportar) {
        btnExportar.addEventListener('click', exportarBitacora);
    }

    // 10. Configurar gestión de usuarios (formulario y tabla)
    const formUser = document.getElementById('formCrearUsuario');
    if (formUser) formUser.addEventListener('submit', manejarCrearUsuario);

    const tablaUser = document.getElementById('tablaCuerpoUsuarios');
    if (tablaUser) {
        tablaUser.addEventListener('click', (e) => {
            if (e.target.classList.contains('btn-borrar-usuario')) {
                const idUsuario = e.target.getAttribute('data-id');
                eliminarUsuarioAdmin(idUsuario);
            }
        });
    }

    // 11. Configurar eventos del Modal de Edición
    const btnCerrarModal = document.getElementById('cerrarModalEditar');
    if (btnCerrarModal) {
        btnCerrarModal.addEventListener('click', () => {
            document.getElementById('modalEditar').style.display = 'none';
        });
    }

    const formEditar = document.getElementById('formEditarDataset');
    if (formEditar) {
        formEditar.addEventListener('submit', manejarEdicionDataset);
    }

    // 12. Configurar botón de cerrar sesión
    const btnCerrar = document.getElementById('btnCerrarSesion');
    if (btnCerrar) {
        btnCerrar.addEventListener('click', cerrarSesion);
    }

    // 13. Cargar métricas del dashboard al iniciar
    renderizarDashboard();
});

// Control de pestañas del Centro de Mando
function cambiarPestana(idPestana, botonClickeado) {
    const vistas = document.querySelectorAll('.pestana-admin');
    vistas.forEach(vista => {
        vista.classList.add('pestana-oculta');
    });

    const botones = document.querySelectorAll('.admin-tab-btn');
    botones.forEach(btn => {
        btn.classList.remove('active');
    });

    const vistaSeleccionada = document.getElementById(idPestana);
    if (vistaSeleccionada) {
        vistaSeleccionada.classList.remove('pestana-oculta');
    }
    
    botonClickeado.classList.add('active');

    if (idPestana === 'tab-gestionar') {
        cargarCatalogoAdmin();
    } else if (idPestana === 'tab-dashboard') {
        renderizarDashboard();
    } else if (idPestana === 'tab-mensajes') {
        cargarMensajesAdmin();
    } else if (idPestana === 'tab-usuarios') {
        cargarUsuariosAdmin();
    }
}

// Renderizar métricas, gráfica de Chart.js y bitácora real en el Dashboard
async function renderizarDashboard() {
    try {
        const respuesta = await fetch(`/api/admin/datasets`, {
            method: "GET",
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await respuesta.json();
        
        if (data.resultados) {
            const kpiTotal = document.getElementById('kpi-total');
            if (kpiTotal) kpiTotal.textContent = data.resultados.length;

            const dependenciasUnicas = new Set(data.resultados.map(item => item.dependencia));
            const kpiDep = document.getElementById('kpi-dependencias');
            if (kpiDep) kpiDep.textContent = dependenciasUnicas.size;

            const conteoCategorias = {};
            data.resultados.forEach(item => {
                const cat = item.categoria || "General";
                conteoCategorias[cat] = (conteoCategorias[cat] || 0) + 1;
            });

            const canvasElement = document.getElementById('graficaCategorias');
            if (canvasElement) {
                const ctx = canvasElement.getContext('2d');
                
                if (window.miGraficaBarras instanceof Chart) {
                    window.miGraficaBarras.destroy();
                }

                window.miGraficaBarras = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: Object.keys(conteoCategorias),
                        datasets: [{
                            label: 'Datasets por Categoría',
                            data: Object.values(conteoCategorias),
                            backgroundColor: '#004b87',
                            borderRadius: 4
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            x: { beginAtZero: true, ticks: { stepSize: 1 } }
                        }
                    }
                });
            }
        }

        // Bitácora persistente desde SQLite
        const listaAuditoria = document.getElementById('listaAuditoria');
        if (listaAuditoria) {
            try {
                const respLog = await fetch(`${CONFIG.API_BASE_URL}/api/admin/bitacora`, {
                    method: "GET",
                    headers: { "Authorization": `Bearer ${token}` }
                });
                const dataLog = await respLog.json();

                let auditHtml = '';
                if (dataLog.registros && dataLog.registros.length > 0) {
                    dataLog.registros.slice(0, 5).forEach(log => {
                        const hora = new Date(log.fecha_hora).toLocaleTimeString('es-MX', { 
                            hour: '2-digit', 
                            minute: '2-digit' 
                        });
                        auditHtml += `
                            <li>
                                <span class="audit-action"><strong>[${log.usuario}]</strong> ${log.accion}</span>
                                <small class="audit-target">${log.detalles} · ${hora}</small>
                            </li>
                        `;
                    });
                } else {
                    auditHtml = '<li><small class="text-muted">Sin registros de auditoría</small></li>';
                }
                listaAuditoria.innerHTML = auditHtml;
            } catch (errLog) {
                listaAuditoria.innerHTML = '<li><small class="text-danger">Error al cargar bitácora</small></li>';
            }
        }

    } catch (error) {
        console.error("Error al cargar las métricas del dashboard:", error);
    }
}

// Ingesta de nuevos datasets
async function manejarSubidaDataset(evento) {
    evento.preventDefault(); 
    
    const mensajeEstado = document.getElementById('mensajeEstado');
    mensajeEstado.className = 'admin-mensaje msg-info';
    mensajeEstado.textContent = "Subiendo archivo y procesando IA...";

    const titulo = document.getElementById('inputTitulo').value;
    const descripcion = document.getElementById('inputDescripcion').value;
    const dependencia = document.getElementById('selectDependencia').value;
    const categoria = document.getElementById('inputCategoria') 
        ? document.getElementById('inputCategoria').value 
        : dependencia;
    const archivoInput = document.getElementById('inputArchivo');
    
    const formData = new FormData();
    formData.append("titulo", titulo);
    formData.append("descripcion", descripcion);
    formData.append("dependencia", dependencia);
    formData.append("categoria", categoria);
    formData.append("archivo", archivoInput.files[0]);

    try {
        const respuesta = await fetch(`/api/admin/subir`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` },
            body: formData 
        });

        const data = await respuesta.json();

        if (respuesta.ok) {
            mensajeEstado.className = 'admin-mensaje msg-success';
            mensajeEstado.textContent = `¡Éxito! Dataset publicado (ID: ${data.id})`;
            document.getElementById('formSubirDataset').reset(); 
            poblarOpcionesDinamicas();
            renderizarDashboard();
        } else {
            mensajeEstado.className = 'admin-mensaje msg-danger';
            mensajeEstado.textContent = `Error: ${data.detail}`;
        }

    } catch (error) {
        mensajeEstado.className = 'admin-mensaje msg-danger';
        mensajeEstado.textContent = "Error de conexión con el servidor.";
    }
}

// Llenar selectores dinámicos
async function poblarOpcionesDinamicas() {
    try {
        const respuesta = await fetch(`/api/admin/datasets`, {
            method: "GET",
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await respuesta.json();
        if (!data.resultados) return;

        const selectDep = document.getElementById('selectDependencia');
        const selectEditDep = document.getElementById('editDependencia');
        const datalistCat = document.getElementById('listaCategoriasSugeridas');

        const dependencias = [...new Set(data.resultados.map(d => d.dependencia).filter(Boolean))].sort();
        const categorias = [...new Set(data.resultados.map(d => d.categoria).filter(Boolean))].sort();

        if (selectDep) {
            selectDep.innerHTML = '<option value="">Selecciona una dependencia...</option>';
            dependencias.forEach(dep => {
                selectDep.innerHTML += `<option value="${dep}">${dep}</option>`;
            });
        }

        if (selectEditDep) {
            selectEditDep.innerHTML = '<option value="">Selecciona una dependencia...</option>';
            dependencias.forEach(dep => {
                selectEditDep.innerHTML += `<option value="${dep}">${dep}</option>`;
            });
        }

        if (datalistCat) {
            datalistCat.innerHTML = '';
            categorias.forEach(cat => {
                datalistCat.innerHTML += `<option value="${cat}">`;
            });
        }

    } catch (error) {
        console.error("Error al poblar dependencias y categorías:", error);
    }
}

// Cargar catálogo y activar paginación con lista base
async function cargarCatalogoAdmin() {
    const tbody = document.getElementById('tablaCuerpoDatasets');
    if (!tbody) return;
    
    tbody.innerHTML = '<tr><td colspan="4" class="text-center">Cargando catálogo...</td></tr>';
    
    try {
        const respuesta = await fetch(`/api/admin/datasets`, {
            method: "GET",
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await respuesta.json();
        
        datasetsCatalogo = data.resultados || [];
        
        // Mantener término de búsqueda si el input tiene contenido
        const inputBuscar = document.getElementById('inputBuscarAdmin');
        const termino = inputBuscar ? inputBuscar.value.toLowerCase().trim() : "";
        
        if (termino) {
            datasetsFiltrados = datasetsCatalogo.filter(item => 
                item.titulo.toLowerCase().includes(termino) || 
                item.dependencia.toLowerCase().includes(termino)
            );
        } else {
            datasetsFiltrados = [...datasetsCatalogo];
        }

        paginaActualAdmin = 1;
        renderizarTablaPaginada();

    } catch (error) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center msg-danger">Error al conectar con la base de datos.</td></tr>';
    }
}

function renderizarTablaPaginada() {
    const tbody = document.getElementById('tablaCuerpoDatasets');
    const contenedorPaginacion = document.getElementById('paginacionAdmin');
    if (!tbody) return;

    tbody.innerHTML = '';

    if (datasetsFiltrados.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center">No se encontraron datasets coincidentes.</td></tr>';
        if (contenedorPaginacion) contenedorPaginacion.style.display = 'none';
        return;
    }

    const totalPaginas = Math.ceil(datasetsFiltrados.length / ITEMS_POR_PAGINA_ADMIN);
    if (paginaActualAdmin > totalPaginas) paginaActualAdmin = totalPaginas;

    const inicio = (paginaActualAdmin - 1) * ITEMS_POR_PAGINA_ADMIN;
    const fin = inicio + ITEMS_POR_PAGINA_ADMIN;
    const datosPagina = datasetsFiltrados.slice(inicio, fin);

    datosPagina.forEach(item => {
        const fila = `
            <tr>
                <td><strong>${item.titulo}</strong></td>
                <td>${item.dependencia}</td>
                <td>${item.fecha}</td>
                <td class="text-center" style="display: flex; gap: 8px; justify-content: center;">
                    <button class="btn-editar-dataset btn-secondary" 
                        data-id="${item.id}" 
                        data-titulo="${item.titulo}" 
                        data-descripcion="${item.descripcion || ''}" 
                        data-dependencia="${item.dependencia}" 
                        data-categoria="${item.categoria}">Editar</button>
                    <button class="btn-borrar-dataset btn-danger" data-id="${item.id}">Borrar</button>
                </td>
            </tr>
        `;
        tbody.innerHTML += fila;
    });

    actualizarControlesPaginacionAdmin(totalPaginas);
}

function actualizarControlesPaginacionAdmin(totalPaginas) {
    const contenedorPaginacion = document.getElementById('paginacionAdmin');
    const contenedorNumeros = document.getElementById('numerosPaginacionAdmin');
    const btnAnt = document.getElementById('btnAdminPagAnterior');
    const btnSig = document.getElementById('btnAdminPagSiguiente');

    if (!contenedorPaginacion) return;

    if (totalPaginas <= 1) {
        contenedorPaginacion.style.display = 'none';
        return;
    }

    contenedorPaginacion.style.display = 'flex';
    btnAnt.disabled = paginaActualAdmin === 1;
    btnSig.disabled = paginaActualAdmin === totalPaginas;

    if (contenedorNumeros) {
        contenedorNumeros.innerHTML = '';
        for (let i = 1; i <= totalPaginas; i++) {
            const btnNum = document.createElement('button');
            btnNum.type = 'button';
            btnNum.textContent = i;
            btnNum.className = `btn-num-pag ${i === paginaActualAdmin ? 'active' : ''}`;
            btnNum.addEventListener('click', () => {
                paginaActualAdmin = i;
                renderizarTablaPaginada();
            });
            contenedorNumeros.appendChild(btnNum);
        }
    }
}

// Cargar Buzón Ciudadano y activar paginación
async function cargarMensajesAdmin() {
    const tbody = document.getElementById('tablaCuerpoMensajes');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="5" class="text-center">Cargando mensajes...</td></tr>';

    try {
        const respuesta = await fetch(`${CONFIG.API_BASE_URL}/api/admin/mensajes`, {
            method: "GET",
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await respuesta.json();

        mensajesBuzon = data.mensajes || [];
        paginaActualMensajes = 1;
        renderizarTablaMensajesPaginada();

    } catch (error) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center msg-danger">Error al conectar con la base de datos.</td></tr>';
    }
}

function renderizarTablaMensajesPaginada() {
    const tbody = document.getElementById('tablaCuerpoMensajes');
    const contenedorPaginacion = document.getElementById('paginacionMensajes');
    if (!tbody) return;

    tbody.innerHTML = '';

    if (mensajesBuzon.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">No hay mensajes registrados.</td></tr>';
        if (contenedorPaginacion) contenedorPaginacion.style.display = 'none';
        return;
    }

    const totalPaginas = Math.ceil(mensajesBuzon.length / ITEMS_POR_PAGINA_MENSAJES);
    if (paginaActualMensajes > totalPaginas) paginaActualMensajes = totalPaginas;

    const inicio = (paginaActualMensajes - 1) * ITEMS_POR_PAGINA_MENSAJES;
    const fin = inicio + ITEMS_POR_PAGINA_MENSAJES;
    const datosPagina = mensajesBuzon.slice(inicio, fin);

    datosPagina.forEach(item => {
        const fechaFormateada = new Date(item.fecha_envio).toLocaleDateString('es-MX', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });

        const fila = `
            <tr>
                <td><strong>${item.nombre}</strong></td>
                <td><a href="mailto:${item.email}" style="color: var(--blue-primary, #004b87);">${item.email}</a></td>
                <td>${item.mensaje}</td>
                <td>${fechaFormateada}</td>
                <td class="text-center">
                    <button class="btn-borrar-mensaje btn-danger" data-id="${item.id}">Borrar</button>
                </td>
            </tr>
        `;
        tbody.innerHTML += fila;
    });

    actualizarControlesPaginacionMensajes(totalPaginas);
}

function actualizarControlesPaginacionMensajes(totalPaginas) {
    const contenedorPaginacion = document.getElementById('paginacionMensajes');
    const contenedorNumeros = document.getElementById('numerosPaginacionMensajes');
    const btnAnt = document.getElementById('btnMensajesPagAnterior');
    const btnSig = document.getElementById('btnMensajesPagSiguiente');

    if (!contenedorPaginacion) return;

    if (totalPaginas <= 1) {
        contenedorPaginacion.style.display = 'none';
        return;
    }

    contenedorPaginacion.style.display = 'flex';
    btnAnt.disabled = paginaActualMensajes === 1;
    btnSig.disabled = paginaActualMensajes === totalPaginas;

    if (contenedorNumeros) {
        contenedorNumeros.innerHTML = '';
        for (let i = 1; i <= totalPaginas; i++) {
            const btnNum = document.createElement('button');
            btnNum.type = 'button';
            btnNum.textContent = i;
            btnNum.className = `btn-num-pag ${i === paginaActualMensajes ? 'active' : ''}`;
            btnNum.addEventListener('click', () => {
                paginaActualMensajes = i;
                renderizarTablaMensajesPaginada();
            });
            contenedorNumeros.appendChild(btnNum);
        }
    }
}

// Eliminar mensaje ciudadano
async function eliminarMensajeAdmin(idMensaje) {
    const confirmacion = confirm("¿Deseas eliminar este mensaje ciudadano? Esta acción no se puede deshacer.");
    if (!confirmacion) return;

    try {
        const respuesta = await fetch(`${CONFIG.API_BASE_URL}/api/admin/mensajes/${idMensaje}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${token}` }
        });

        if (respuesta.ok) {
            cargarMensajesAdmin();
            renderizarDashboard();
        } else {
            const data = await respuesta.json();
            alert(`Error: ${data.detail || 'No se pudo eliminar el mensaje.'}`);
        }
    } catch (error) {
        alert("Error de conexión al intentar eliminar el mensaje.");
    }
}

// Descargar reporte CSV de la bitácora administrativa
async function exportarBitacora() {
    try {
        const respuesta = await fetch(`/api/admin/bitacora/exportar`, {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (!respuesta.ok) {
            alert("No se pudo generar el reporte de auditoría.");
            return;
        }

        const blob = await respuesta.blob();
        const urlDescarga = window.URL.createObjectURL(blob);
        const enlace = document.createElement('a');
        enlace.href = urlDescarga;
        enlace.download = `bitacora_auditoria_${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(enlace);
        enlace.click();
        enlace.remove();
        window.URL.revokeObjectURL(urlDescarga);

    } catch (error) {
        alert("Error de conexión al exportar la bitácora.");
    }
}

// Cargar funcionarios activos en la tabla
async function cargarUsuariosAdmin() {
    const tbody = document.getElementById('tablaCuerpoUsuarios');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="3" class="text-center">Cargando cuentas...</td></tr>';

    try {
        const resp = await fetch(`/api/admin/usuarios`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await resp.json();

        tbody.innerHTML = '';
        if (!data.usuarios || data.usuarios.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-center">Sin usuarios adicionales.</td></tr>';
            return;
        }

        data.usuarios.forEach(u => {
            tbody.innerHTML += `
                <tr>
                    <td><strong>${u.username}</strong></td>
                    <td><span class="badge-pub">${u.rol.toUpperCase()}</span></td>
                    <td class="text-center">
                        <button class="btn-borrar-usuario btn-danger" data-id="${u.id}">Baja</button>
                    </td>
                </tr>
            `;
        });
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-center msg-danger">Error al cargar cuentas.</td></tr>';
    }
}

// Enviar formulario de alta de nuevo funcionario
async function manejarCrearUsuario(e) {
    e.preventDefault();
    const msg = document.getElementById('msgUsuarioEstado');
    const username = document.getElementById('inputNuevoUsuario').value;
    const password = document.getElementById('inputNuevoPassword').value;
    const rol = document.getElementById('selectNuevoRol').value;

    try {
        const resp = await fetch(`/api/admin/usuarios`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ username, password, rol })
        });

        const data = await resp.json();
        if (resp.ok) {
            msg.className = "admin-mensaje msg-success";
            msg.textContent = "¡Funcionario registrado!";
            document.getElementById('formCrearUsuario').reset();
            cargarUsuariosAdmin();
            renderizarDashboard();
        } else {
            msg.className = "admin-mensaje msg-danger";
            msg.textContent = data.detail || "Error al crear cuenta.";
        }
    } catch (err) {
        msg.className = "admin-mensaje msg-danger";
        msg.textContent = "Error de red.";
    }
}

// Eliminar acceso de funcionario
async function eliminarUsuarioAdmin(id) {
    if (!confirm("¿Seguro que deseas dar de baja este acceso?")) return;

    try {
        const resp = await fetch(`/api/admin/usuarios/${id}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await resp.json();

        if (resp.ok) {
            cargarUsuariosAdmin();
            renderizarDashboard();
        } else {
            alert(data.detail || "Error al eliminar.");
        }
    } catch (e) {
        alert("Error de conexión.");
    }
}

// Modal de edición de datasets
function abrirModalEdicion(id, titulo, descripcion, dependencia, categoria) {
    document.getElementById('editDatasetId').value = id;
    document.getElementById('editTitulo').value = titulo;
    document.getElementById('editDescripcion').value = descripcion;
    document.getElementById('editDependencia').value = dependencia;
    document.getElementById('editCategoria').value = categoria;
    
    document.getElementById('modalEditar').style.display = 'flex';
}

async function manejarEdicionDataset(evento) {
    evento.preventDefault();
    
    const id = document.getElementById('editDatasetId').value;
    const titulo = document.getElementById('editTitulo').value;
    const descripcion = document.getElementById('editDescripcion').value;
    const dependencia = document.getElementById('editDependencia').value;
    const categoria = document.getElementById('editCategoria').value;

    try {
        const respuesta = await fetch(`/api/admin/datasets/${id}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ titulo, descripcion, dependencia, categoria })
        });

        if (respuesta.ok) {
            document.getElementById('modalEditar').style.display = 'none';
            alert("¡Dataset actualizado exitosamente!");
            cargarCatalogoAdmin();
            poblarOpcionesDinamicas();
            renderizarDashboard();
        } else {
            const data = await respuesta.json();
            alert(`Error al actualizar: ${data.detail || 'Desconocido'}`);
        }
    } catch (error) {
        alert("Error de conexión con el servidor al intentar actualizar.");
    }
}

async function eliminarDataset(idDataset) {
    const confirmacion = confirm("¿Estás seguro de que deseas eliminar este dataset de forma permanente? Esta acción no se puede deshacer.");
    if (!confirmacion) return;

    try {
        const respuesta = await fetch(`/api/admin/datasets/${idDataset}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${token}` }
        });

        if (respuesta.ok) {
            cargarCatalogoAdmin();
            poblarOpcionesDinamicas();
            renderizarDashboard();
        } else {
            const data = await respuesta.json();
            alert(`Error: ${data.detail}`);
        }
    } catch (error) {
        alert("Error de conexión con el servidor al intentar eliminar.");
    }
}

function cerrarSesion() {
    localStorage.removeItem("authToken");
    window.location.href = "/login.html";
}