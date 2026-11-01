# Pruebas del buzón ciudadano (app/api/contact.py)

MENSAJE = {"nombre": "María López", "email": "maria@ejemplo.com", "mensaje": "¿Publicarán los horarios de las rutas?"}


def test_ciudadano_envia_mensaje_y_el_panel_lo_ve(sesion):
    assert sesion(None).post("/api/contacto", json=MENSAJE).status_code == 201
    mensajes = sesion("editor").get("/api/admin/mensajes").json()["mensajes"]
    assert MENSAJE["mensaje"] in [m["mensaje"] for m in mensajes]


def test_correo_invalido_da_422(sin_sesion):
    assert sin_sesion.post("/api/contacto", json={**MENSAJE, "email": "no-es-correo"}).status_code == 422


def test_mensaje_corto_da_422(sin_sesion):
    assert sin_sesion.post("/api/contacto", json={**MENSAJE, "mensaje": "hola"}).status_code == 422


def test_listar_mensajes_requiere_sesion(sin_sesion):
    assert sin_sesion.get("/api/admin/mensajes").status_code == 401


def test_solo_admin_borra_mensajes(sesion):
    sesion(None).post("/api/contacto", json={**MENSAJE, "mensaje": "Mensaje que se va a borrar."})
    id_mensaje = next(m["id"] for m in sesion("editor").get("/api/admin/mensajes").json()["mensajes"] if m["mensaje"] == "Mensaje que se va a borrar.")

    assert sesion("editor").delete(f"/api/admin/mensajes/{id_mensaje}").status_code == 403
    assert sesion("admin").delete(f"/api/admin/mensajes/{id_mensaje}").status_code == 200
    assert sesion("admin").delete(f"/api/admin/mensajes/{id_mensaje}").status_code == 404
