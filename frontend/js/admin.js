// Verificar si existe el token JWT antes de dejar ver el panel
const token = localStorage.getItem("authToken");
if (!token) {
    window.location.href = "/login.html";
}

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

    // 3. Configurar acciones en la tabla de gestión (botón borrar)
    const tablaCuerpo = document.getElementById('tablaCuerpoDatasets');
    if (tablaCuerpo) {
        tablaCuerpo.addEventListener('click', function(e) {
            if (e.target.classList.contains('btn-borrar-dataset')) {
                const idDataset = e.target.getAttribute('data-id');
                eliminarDataset(idDataset);
            }
        });
    }

    // 4. Cargar métricas del dashboard al iniciar
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
        const respuesta = await fetch(`${CONFIG.API_BASE_URL}/api/admin/datasets`);
        const data = await respuesta.json();
        
        if (!data.resultados) return;

        // Actualizar indicador KPI de total publicados
        const kpiTotal = document.getElementById('kpi-total');
        if (kpiTotal) {
            kpiTotal.textContent = data.resultados.length;
        }

        // Agrupar datasets por dependencia para la gráfica
        const conteo = {};
        data.resultados.forEach(item => {
            conteo[item.dependencia] = (conteo[item.dependencia] || 0) + 1;
        });

        // Validar si el elemento canvas existe antes de instanciar Chart.js
        const canvasElement = document.getElementById('graficaDependencias');
        if (!canvasElement) return;

        const ctx = canvasElement.getContext('2d');
        
        // Destruir gráfica previa si ya existía para evitar duplicados al cambiar de pestaña
        if (window.miGraficaDona instanceof Chart) {
            window.miGraficaDona.destroy();
        }

        window.miGraficaDona = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: Object.keys(conteo),
                datasets: [{
                    data: Object.values(conteo),
                    backgroundColor: ['#004b87', '#005eb8', '#4b9cd3', '#81b2e2', '#e6f0fa']
                }]
            },
            options: { 
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
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
        const respuesta = await fetch(`${CONFIG.API_BASE_URL}/api/admin/subir`, {
            method: "POST",
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
        const respuesta = await fetch(`${CONFIG.API_BASE_URL}/api/admin/datasets`);
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
                    <td class="text-center">
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

// Eliminar dataset en cascada (vector y archivo físico)
async function eliminarDataset(idDataset) {
    const confirmacion = confirm("¿Estás seguro de que deseas eliminar este dataset de forma permanente? Esta acción no se puede deshacer.");
    if (!confirmacion) return;

    try {
        const respuesta = await fetch(`${CONFIG.API_BASE_URL}/api/admin/datasets/${idDataset}`, {
            method: "DELETE"
        });

        if (respuesta.ok) {
            cargarCatalogoAdmin();
        } else {
            const data = await respuesta.json();
            alert(`Error: ${data.detail}`);
        }
    } catch (error) {
        alert("Error de conexión con el servidor al intentar eliminar.");
    }
}