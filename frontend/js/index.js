// Escuchamos el evento 'submit' del formulario completo
const searchForm = document.getElementById('searchForm');
if (searchForm) {
    searchForm.addEventListener('submit', function(evento) {
        evento.preventDefault(); // Evita que la página se recargue
        irABuscar();
    });
}

function irABuscar() {
    const inputElement = document.getElementById('searchInput');
    if (!inputElement) return;
    
    const texto = inputElement.value.trim();
    
    // Si la barra está vacía, lo mandamos al catálogo general
    if (texto === "") {
        window.location.href = "explorar_datos.html";
    } else {
        // Si escribió algo, hacemos la búsqueda con parámetros
        window.location.href = `explorar_datos.html?q=${encodeURIComponent(texto)}`;
    }
}