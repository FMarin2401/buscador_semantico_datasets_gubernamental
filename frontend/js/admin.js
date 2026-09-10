// Definir el token global para todas las peticiones
const token = localStorage.getItem("authToken");

// Controlar el historial (Back/Forward Cache) y revelar el panel
window.addEventListener("pageshow", (event) => {
    const tokenActual = localStorage.getItem("authToken");
    if (!tokenActual) {
        window.location.replace("/login.html");
    } else {
        // Si el token es válido, encendemos la interfaz
        const panel = document.querySelector('.admin-layout');
        if (panel) panel.style.display = 'flex';
    }
});

document.addEventListener('DOMContentLoaded', () => {
    // 1. Configurar botones del menú lateral
    const botonesMenu = document.querySelectorAll('button.admin-tab-btn');
    botonesMenu.forEach(boton => {
        boton.addEventListener('click', function() {
            const destino = this.getAttribute('data-target');
            if (destino) cambiarPestana(destino, this);
        });
    });

    // 2. Configurar formulario de subida de datasets
    const formSubir = document.getElementById('formSubirDataset');
    if (formSubir) formSubir.addEventListener('submit', manejarSubidaDataset);

    // 3. Configurar acciones en la tabla de gestión (botón borrar o editar)
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

    // 4. Configurar eventos del Modal de Edición
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

    // 5. Configurar botón de cerrar sesión
    const btnCerrar = document.getElementById('btnCerrarSesion');
    if (btnCerrar) {
        btnCerrar.addEventListener('click', cerrarSesion);
    }

    // 6. Cargar métricas del dashboard al iniciar
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
        renderizarDashboard(); // Recargar métricas al volver al resumen
    }
}

// Renderizar métricas y gráfica de Chart.js en el Dashboard
async function renderizarDashboard() {
    try {
        const respuesta = await fetch(`/api/admin/datasets`, {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });
        const data = await respuesta.json();
        
        if (!data.resultados) return;

        // 1. Actualizar indicador KPI de total publicados
        const kpiTotal = document.getElementById('kpi-total');
        if (kpiTotal) {
            kpiTotal.textContent = data.resultados.length;
        }

        // 2. Calcular y actualizar KPI de dependencias únicas
        const dependenciasUnicas = new Set(data.resultados.map(item => item.dependencia));
        const kpiDep = document.getElementById('kpi-dependencias');
        if (kpiDep) {
            kpiDep.textContent = dependenciasUnicas.size;
        }

        // 3. Agrupar datasets por CATEGORÍA para el gráfico de barras horizontales
        const conteoCategorias = {};
        data.resultados.forEach(item => {
            const cat = item.categoria || "General";
            conteoCategorias[cat] = (conteoCategorias[cat] || 0) + 1;
        });

        // Validar si el elemento canvas existe antes de instanciar Chart.js
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

        // 4. Renderizar Bitácora de Auditoría
        const listaAuditoria = document.getElementById('listaAuditoria');
        if (listaAuditoria) {
            const ultimos = data.resultados.slice(-4).reverse();
            let auditHtml = '';
            
            ultimos.forEach(item => {
                auditHtml += `
                    <li>
                        <span class="audit-action">Dataset registrado</span>
                        <small class="audit-target">${item.titulo.substring(0, 25)}...</small>
                    </li>
                `;
            });
            listaAuditoria.innerHTML = auditHtml || '<li>Sin registros recientes</li>';
        }

    } catch (error) {
        console.error("Error al cargar las métricas del dashboard:", error);
    }
}

// Ingesta y subida de nuevos datasets
async function manejarSubidaDataset(evento) {
    evento.preventDefault(); 
    
    const mensajeEstado = document.getElementById('mensajeEstado');
    mensajeEstado.className = 'admin-mensaje msg-info';
    mensajeEstado.textContent = "Subiendo archivo y procesando IA...";

    const titulo = document.getElementById('inputTitulo').value;
    const descripcion = document.getElementById('inputDescripcion').value;
    const dependencia = document.getElementById('selectDependencia').value;
    const archivoInput = document.getElementById('inputArchivo');
    
    const formData = new FormData();
    formData.append("titulo", titulo);
    formData.append("descripcion", descripcion);
    formData.append("dependencia", dependencia);
    formData.append("archivo", archivoInput.files[0]);

    try {
        const respuesta = await fetch(`/api/admin/subir`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`
            },
            body: formData 
        });

        const data = await respuesta.json();

        if (respuesta.ok) {
            mensajeEstado.className = 'admin-mensaje msg-success';
            mensajeEstado.textContent = `¡Éxito! Dataset publicado (ID: ${data.id})`;
            document.getElementById('formSubirDataset').reset(); 
        } else {
            mensajeEstado.className = 'admin-mensaje msg-danger';
            mensajeEstado.textContent = `Error: ${data.detail}`;
        }

    } catch (error) {
        mensajeEstado.className = 'admin-mensaje msg-danger';
        mensajeEstado.textContent = "Error de conexión con el servidor.";
    }
}

// Cargar tabla del catálogo activo para los administradores
async function cargarCatalogoAdmin() {
    const tbody = document.getElementById('tablaCuerpoDatasets');
    if (!tbody) return;
    
    tbody.innerHTML = '<tr><td colspan="4" class="text-center">Cargando catálogo...</td></tr>';
    
    try {
        const respuesta = await fetch(`/api/admin/datasets`, {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });
        const data = await respuesta.json();
        
        tbody.innerHTML = '';
        
        if (!data.resultados || data.resultados.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center">No hay datasets publicados.</td></tr>';
            return;
        }
        
        data.resultados.forEach(item => {
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
    } catch (error) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center msg-danger">Error al conectar con la base de datos.</td></tr>';
    }
}

// Abrir modal de edición con los datos actuales
function abrirModalEdicion(id, titulo, descripcion, dependencia, categoria) {
    document.getElementById('editDatasetId').value = id;
    document.getElementById('editTitulo').value = titulo;
    document.getElementById('editDescripcion').value = descripcion;
    document.getElementById('editDependencia').value = dependencia;
    document.getElementById('editCategoria').value = categoria;
    
    document.getElementById('modalEditar').style.display = 'flex';
}

// Enviar cambios de edición por PUT
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
            renderizarDashboard();
        } else {
            const data = await respuesta.json();
            alert(`Error al actualizar: ${data.detail || 'Desconocido'}`);
        }
    } catch (error) {
        alert("Error de conexión con el servidor al intentar actualizar.");
    }
}

// Eliminar dataset en cascada (vector y archivo físico)
async function eliminarDataset(idDataset) {
    const confirmacion = confirm("¿Estás seguro de que deseas eliminar este dataset de forma permanente? Esta acción no se puede deshacer.");
    if (!confirmacion) return;

    try {
        const respuesta = await fetch(`/api/admin/datasets/${idDataset}`, {
            method: "DELETE",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (respuesta.ok) {
            cargarCatalogoAdmin();
            renderizarDashboard();
        } else {
            const data = await respuesta.json();
            alert(`Error: ${data.detail}`);
        }
    } catch (error) {
        alert("Error de conexión con el servidor al intentar eliminar.");
    }
}

// Función para cerrar sesión y destruir el JWT
function cerrarSesion() {
    localStorage.removeItem("authToken");
    window.location.href = "/login.html";
}