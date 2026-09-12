document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById('formContacto');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = document.getElementById('btnEnviarContacto');
        const msg = document.getElementById('msgContactoEstado');
        
        btn.disabled = true;
        msg.style.display = 'block';
        msg.className = 'admin-mensaje msg-info';
        msg.textContent = 'Enviando mensaje...';

        const payload = {
            nombre: document.getElementById('nombreContacto').value,
            email: document.getElementById('emailContacto').value,
            mensaje: document.getElementById('mensajeContacto').value
        };

        try {
            const resp = await fetch(`${CONFIG.API_BASE_URL}/api/contacto`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (resp.ok) {
                msg.className = 'admin-mensaje msg-success';
                msg.textContent = '¡Mensaje recibido con éxito! El equipo de transparencia lo revisará pronto.';
                form.reset();
            } else {
                const err = await resp.json();
                msg.className = 'admin-mensaje msg-danger';
                msg.textContent = `Error: ${err.detail || 'No se pudo enviar el mensaje.'}`;
            }
        } catch (e) {
            msg.className = 'admin-mensaje msg-danger';
            msg.textContent = 'Error de conexión con el servidor.';
        } finally {
            btn.disabled = false;
        }
    });
});