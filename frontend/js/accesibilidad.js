document.addEventListener("DOMContentLoaded", () => {
    const btnAumentar = document.getElementById("btnAumentar");
    const btnDisminuir = document.getElementById("btnDisminuir");
    const btnMenu = document.getElementById("btnMenuMovil");
    const navLinks = document.querySelector(".nav-links");
    
    let currentSize = parseFloat(localStorage.getItem("portalFontSize")) || 100;
    
    function applyFontSize(size) {
        document.documentElement.style.fontSize = size + "%";
        localStorage.setItem("portalFontSize", size);
    }
    
    if (currentSize !== 100) {
        applyFontSize(currentSize);
    }
    
    if (btnAumentar) {
        btnAumentar.addEventListener("click", () => {
            if (currentSize < 140) {
                currentSize += 10;
                applyFontSize(currentSize);
            }
        });
    }
    
    if (btnDisminuir) {
        btnDisminuir.addEventListener("click", () => {
            if (currentSize > 90) {
                currentSize -= 10;
                applyFontSize(currentSize);
            }
        });
    }

    if (btnMenu && navLinks) {
        btnMenu.addEventListener("click", () => {
            // Alternar la clase activo
            navLinks.classList.toggle("activo");
            
            // Cambiar el ícono (Hamburguesa a X)
            const estaAbierto = navLinks.classList.contains("activo");
            btnMenu.innerHTML = estaAbierto ? "✕" : "☰";
            btnMenu.setAttribute("aria-expanded", estaAbierto);
        });
    }

});