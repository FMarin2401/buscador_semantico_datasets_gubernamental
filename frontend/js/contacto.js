document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById('formContacto');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = document.getElementById('btnEnviarContacto');
        const msg = document.getElementById('msgContactoEstado');

        const nombre = document.getElementById('nombreContacto').value.trim();
        const email = document.getElementById('emailContacto').value.trim();
        const mensaje = document.getElementById('mensajeContacto').value.trim();

        // 1. Validaciones del lado del cliente
        if (!nombre || nombre.length < 3) {
            msg.style.display = 'block';
            msg.className = 'admin-mensaje msg-danger';
            msg.textContent = 'Por favor ingresa tu nombre completo (mínimo 3 caracteres).';
            return;
        }

        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            msg.style.display = 'block';
            msg.className = 'admin-mensaje msg-danger';
            msg.textContent = 'Por favor ingresa un correo electrónico válido.';
            return;
        }

        if (!mensaje || mensaje.length < 10) {
            msg.style.display = 'block';
            msg.className = 'admin-mensaje msg-danger';
            msg.textContent = 'El mensaje debe contener al menos 10 caracteres.';
            return;
        }

        btn.disabled = true;
        msg.style.display = 'block';
        msg.className = 'admin-mensaje msg-info';
        msg.textContent = 'Enviando mensaje...';

        const payload = {
            nombre: nombre,
            email: email,
            mensaje: mensaje
        };

        try {
            const resp = await fetch(`/api/contacto`, {
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