document.addEventListener("DOMContentLoaded", () => {
    const formLogin = document.getElementById("formLogin");
    const mensajeError = document.getElementById("mensajeErrorLogin");

    if (formLogin) {
        formLogin.addEventListener("submit", async (e) => {
            e.preventDefault();
            mensajeError.textContent = "Verificando credenciales...";

            const usuario = document.getElementById("inputUsuario").value;
            const password = document.getElementById("inputPassword").value;

            try {
                const respuesta = await fetch(`${CONFIG.API_BASE_URL}/api/login`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({ usuario, password })
                });

                if (!respuesta.ok) {
                    throw new Error("Usuario o contraseña incorrectos.");
                }

                const data = await respuesta.json();
                
                // Guardamos el JWT en el localStorage
                localStorage.setItem("authToken", data.access_token);
                
                // Redirigimos al panel de administración
                window.location.href = "/admin.html";

            } catch (error) {
                mensajeError.textContent = error.message;
            }
        });
    }
});