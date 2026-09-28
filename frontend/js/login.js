document.addEventListener("DOMContentLoaded", () => {
    const formLogin = document.getElementById("formLogin");
    const mensajeError = document.getElementById("mensajeErrorLogin");
    const inputPassword = document.getElementById("inputPassword");
    const btnTogglePassword = document.getElementById("btnTogglePassword");

    const svgOjoAbierto = `
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"></path>
            <circle cx="12" cy="12" r="3"></circle>
        </svg>
    `;

    const svgOjoCerrado = `
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"></path>
            <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"></path>
            <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"></path>
            <line x1="2" y1="2" x2="22" y2="22"></line>
        </svg>
    `;

    if (btnTogglePassword && inputPassword) {
        btnTogglePassword.addEventListener("click", () => {
            const oculto = inputPassword.type === "password";
            inputPassword.type = oculto ? "text" : "password";
            btnTogglePassword.innerHTML = oculto ? svgOjoCerrado : svgOjoAbierto;
            btnTogglePassword.setAttribute("aria-label", oculto ? "Ocultar contraseña" : "Mostrar contraseña");
        });
    }

    if (formLogin) {
        formLogin.addEventListener("submit", async (e) => {
            e.preventDefault();
            mensajeError.textContent = "Verificando credenciales...";

            const usuario = document.getElementById("inputUsuario").value;
            const password = inputPassword ? inputPassword.value : "";

            try {
                const respuesta = await fetch(`/api/login`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ usuario, password }),
                    credentials: "include" // Esencial para que el navegador acepte guardar la cookie HTTP-only
                });

                if (respuesta.status === 429) {
                    throw new Error("Demasiados intentos. Espera un minuto e inténtalo de nuevo.");
                }
                if (respuesta.status === 401) {
                    throw new Error("Usuario o contraseña incorrectos.");
                }
                if (!respuesta.ok) {
                    throw new Error("Error del servidor. Inténtalo más tarde.");
                }

                // Redirigir al panel; la cookie viaja segura de forma automática
                window.location.href = "/admin.html";

            } catch (error) {
                mensajeError.textContent = error instanceof TypeError
                    ? "Error de conexión con el servidor."
                    : error.message;
            }
        });
    }
});