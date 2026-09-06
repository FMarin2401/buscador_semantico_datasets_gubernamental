// Verificar si existe el token JWT antes de dejar ver el panel
const token = localStorage.getItem("authToken");
if (!token) {
    window.location.href = "/login.html";
}

document.addEventListener('DOMContentLoaded', () => {
    const botonesMenu = document.querySelectorAll('button.admin-tab-btn');
    botonesMenu.forEach(boton => {
        boton.addEventListener('click', function() {
            const destino = this.getAttribute('data-target');
            if (destino) cambiarPestana(destino, this);
        });
    });

    const formSubir = document.getElementById('formSubirDataset');
    if (formSubir) formSubir.addEventListener('submit', manejarSubidaDataset);

    const tablaCuerpo = document.getElementById('tablaCuerpoDatasets');
    if (tablaCuerpo) {
        tablaCuerpo.addEventListener('click', function(e) {
            if (e.target.classList.contains('btn-borrar-dataset')) {
                const idDataset = e.target.getAttribute('data-id');
                eliminarDataset(idDataset);
            }
        });
    }
});

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
    }
}

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

async function cargarCatalogoAdmin() {
    const tbody = document.getElementById('tablaCuerpoDatasets');
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