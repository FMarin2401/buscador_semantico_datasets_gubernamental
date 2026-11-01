# Pruebas de la SC-001: reportes de problemas en un dataset (app/api/reportes.py)

REPORTE = {"tipo": "desactualizado", "descripcion": "Falta la nueva clínica de la colonia Las Joyas.", "email_contacto": "ciudadano@ejemplo.com"}
ID_INEXISTENTE = "00000000-0000-0000-0000-000000000000"


def crear_reporte(cliente, id_dataset, **cambios):
    return cliente.post(f"/api/datasets/{id_dataset}/reportes", json={**REPORTE, **cambios})


def cambiar_estado(cliente, id_reporte, estado):
    return cliente.patch(f"/api/admin/reportes/{id_reporte}", json={"estado": estado})


# --- Crear (público) ---

def test_ciudadano_crea_reporte_sin_sesion(sin_sesion, dataset):
    r = crear_reporte(sin_sesion, dataset)
    assert r.status_code == 201
    assert r.json()["estado"] == "abierto"


def test_correo_es_opcional(sin_sesion, dataset):
    r = crear_reporte(sin_sesion, dataset, email_contacto=None)
    assert r.status_code == 201


def test_reporte_de_dataset_inexistente_da_404(sin_sesion):
    r = crear_reporte(sin_sesion, ID_INEXISTENTE)
    assert r.status_code == 404
    assert r.json()["detail"] == "Dataset no encontrado."


def test_tipo_fuera_de_la_lista_da_422(sin_sesion, dataset):
    assert crear_reporte(sin_sesion, dataset, tipo="spam").status_code == 422


def test_descripcion_corta_da_422(sin_sesion, dataset):
    assert crear_reporte(sin_sesion, dataset, descripcion="mal").status_code == 422


def test_correo_invalido_da_422(sin_sesion, dataset):
    assert crear_reporte(sin_sesion, dataset, email_contacto="no-es-correo").status_code == 422


def test_mas_de_5_reportes_por_minuto_da_429(sin_sesion, dataset):
    codigos = [crear_reporte(sin_sesion, dataset).status_code for _ in range(6)]
    assert codigos == [201] * 5 + [429]


# --- Atender (panel) ---

def test_listar_reportes_requiere_sesion(sin_sesion):
    assert sin_sesion.get("/api/admin/reportes").status_code == 401


def test_flujo_completo_de_estados(sesion, dataset):
    id_reporte = crear_reporte(sesion(None), dataset).json()["id"]

    admin = sesion("admin")
    abiertos = admin.get("/api/admin/reportes", params={"estado": "abierto"}).json()["reportes"]
    assert id_reporte in [r["id"] for r in abiertos]

    r = cambiar_estado(admin, id_reporte, "en_revision")
    assert r.status_code == 200
    assert r.json()["estado"] == "en_revision"
    assert r.json()["atendido_por"] == "admin_pruebas"

    r = cambiar_estado(admin, id_reporte, "resuelto")
    assert r.status_code == 200
    assert r.json()["estado"] == "resuelto"


def test_negativa_un_reporte_resuelto_no_se_puede_reabrir(como_admin, dataset):
    """Prueba negativa principal de la SC-001: se intenta violar la regla y se recibe el error correcto."""
    id_reporte = crear_reporte(como_admin, dataset).json()["id"]
    assert cambiar_estado(como_admin, id_reporte, "resuelto").status_code == 200

    r = cambiar_estado(como_admin, id_reporte, "abierto")

    assert r.status_code == 409
    assert r.json()["detail"] == "Un reporte resuelto no se puede reabrir ni modificar."
    # El reporte sigue resuelto
    resueltos = como_admin.get("/api/admin/reportes", params={"estado": "resuelto"}).json()["reportes"]
    assert id_reporte in [rep["id"] for rep in resueltos]


def test_un_reporte_no_retrocede(como_admin, dataset):
    id_reporte = crear_reporte(como_admin, dataset).json()["id"]
    cambiar_estado(como_admin, id_reporte, "en_revision")
    r = cambiar_estado(como_admin, id_reporte, "abierto")
    assert r.status_code == 409
    assert "no retrocede" in r.json()["detail"]


def test_mismo_estado_da_409(como_admin, dataset):
    id_reporte = crear_reporte(como_admin, dataset).json()["id"]
    assert cambiar_estado(como_admin, id_reporte, "abierto").status_code == 409


def test_estado_fuera_de_la_lista_da_422(como_admin, dataset):
    id_reporte = crear_reporte(como_admin, dataset).json()["id"]
    assert cambiar_estado(como_admin, id_reporte, "cerrado").status_code == 422


def test_cambiar_estado_de_reporte_inexistente_da_404(como_admin):
    assert cambiar_estado(como_admin, 999999, "resuelto").status_code == 404


def test_editor_atiende_pero_no_borra(sesion, dataset):
    editor = sesion("editor")
    id_reporte = crear_reporte(editor, dataset).json()["id"]

    assert cambiar_estado(editor, id_reporte, "en_revision").status_code == 200
    r = editor.delete(f"/api/admin/reportes/{id_reporte}")
    assert r.status_code == 403

    admin = sesion("admin")
    assert admin.delete(f"/api/admin/reportes/{id_reporte}").status_code == 200
    assert admin.delete(f"/api/admin/reportes/{id_reporte}").status_code == 404


def test_cambio_de_estado_queda_en_bitacora(como_admin, dataset):
    id_reporte = crear_reporte(como_admin, dataset).json()["id"]
    cambiar_estado(como_admin, id_reporte, "resuelto")
    eventos = como_admin.get("/api/admin/bitacora").json()["registros"]
    assert any(e["accion"] == "Reporte" and f"Reporte {id_reporte} " in e["detalles"] for e in eventos)


# --- Vista e integridad referencial ---

def test_resumen_lee_la_vista_con_pendientes(como_admin, dataset):
    ids = [crear_reporte(como_admin, dataset).json()["id"] for _ in range(3)]
    cambiar_estado(como_admin, ids[0], "resuelto")

    resumen = como_admin.get("/api/admin/reportes/resumen-datasets").json()["datasets"]
    fila = next(d for d in resumen if d["id"] == dataset)
    assert fila["total_reportes"] == 3
    assert fila["reportes_pendientes"] == 2


def test_borrar_dataset_borra_sus_reportes(como_admin, dataset):
    id_reporte = crear_reporte(como_admin, dataset).json()["id"]
    assert como_admin.delete(f"/api/admin/datasets/{dataset}").status_code == 200

    todos = como_admin.get("/api/admin/reportes").json()["reportes"]
    assert id_reporte not in [r["id"] for r in todos]
