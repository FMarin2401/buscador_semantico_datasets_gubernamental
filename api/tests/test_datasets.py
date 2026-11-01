# Pruebas del CRUD de datasets, la descarga y la búsqueda semántica (app/api/manipulate_datasets.py, app/api/search.py)

import json

from tests.conftest import csv_unico, publicar

ID_INEXISTENTE = "00000000-0000-0000-0000-000000000000"
EDICION = {
    "titulo": "Título editado",
    "descripcion": "Descripción editada del dataset de prueba.",
    "dependencia": "Dirección General de Movilidad",
    "categoria": "Movilidad",
}


# --- Crear ---

def test_publicar_dataset(como_editor):
    r = publicar(como_editor, titulo="Paraderos de prueba")
    assert r.status_code == 201
    id_dataset = r.json()["id"]
    catalogo = como_editor.get("/api/admin/datasets").json()["resultados"]
    assert "Paraderos de prueba" in [d["titulo"] for d in catalogo if d["id"] == id_dataset]


def test_publicar_requiere_sesion(sin_sesion):
    assert publicar(sin_sesion).status_code == 401


def test_negativa_mismo_archivo_dos_veces_da_409(como_admin):
    """Regla de negocio: el mismo archivo (mismo SHA-256) no se publica dos veces, aunque cambien los metadatos."""
    contenido = csv_unico()
    assert publicar(como_admin, titulo="Original", contenido=contenido).status_code == 201

    r = publicar(como_admin, titulo="Copia con otro nombre", contenido=contenido, nombre="otro.csv")

    assert r.status_code == 409
    assert "Duplicado" in r.json()["detail"]


def test_categoria_no_oficial_da_422(como_admin):
    r = publicar(como_admin, categoria="Deportes Extremos")
    assert r.status_code == 422
    assert "Categoría no válida" in r.json()["detail"]


def test_archivo_que_no_es_csv_da_400(como_admin):
    r = publicar(como_admin, contenido=b"\x89PNG\r\n\x1a\n\x00\x00binario", nombre="imagen.csv")
    assert r.status_code == 400


def test_extension_distinta_de_csv_da_400(como_admin):
    assert publicar(como_admin, nombre="datos.xlsx").status_code == 400


# --- Editar ---

def test_editar_dataset(como_editor, dataset):
    r = como_editor.put(f"/api/admin/datasets/{dataset}", json=EDICION)
    assert r.status_code == 200
    catalogo = como_editor.get("/api/admin/datasets").json()["resultados"]
    assert next(d for d in catalogo if d["id"] == dataset)["titulo"] == "Título editado"


def test_editar_inexistente_da_404(como_admin):
    assert como_admin.put(f"/api/admin/datasets/{ID_INEXISTENTE}", json=EDICION).status_code == 404


def test_editar_con_id_que_no_es_uuid_da_422(como_admin):
    assert como_admin.put("/api/admin/datasets/no-es-uuid", json=EDICION).status_code == 422


# --- Borrar ---

def test_editor_no_puede_borrar_dataset(como_editor, dataset):
    r = como_editor.delete(f"/api/admin/datasets/{dataset}")
    assert r.status_code == 403


def test_admin_borra_dataset(como_admin, dataset):
    assert como_admin.delete(f"/api/admin/datasets/{dataset}").status_code == 200
    assert como_admin.delete(f"/api/admin/datasets/{dataset}").status_code == 404
    assert como_admin.get(f"/api/descargar/{dataset}").status_code == 404


# --- Descargar y vista previa (públicos) ---

def test_descargar_en_todos_los_formatos_suma_descargas(sin_sesion, dataset):
    for formato in ("csv", "json", "xml", "geojson"):
        assert sin_sesion.get(f"/api/descargar/{dataset}", params={"formato": formato}).status_code == 200

    geojson = json.loads(sin_sesion.get(f"/api/descargar/{dataset}", params={"formato": "geojson"}).content)
    assert geojson["features"][0]["geometry"]["type"] == "Point"

    catalogo = sin_sesion.get("/api/catalogos").json()["resultados"]
    assert next(d for d in catalogo if d["id"] == dataset)["descargas"] == 5


def test_formato_invalido_da_422_y_no_cuenta(sin_sesion, dataset):
    assert sin_sesion.get(f"/api/descargar/{dataset}", params={"formato": "pdf"}).status_code == 422
    catalogo = sin_sesion.get("/api/catalogos").json()["resultados"]
    assert next(d for d in catalogo if d["id"] == dataset)["descargas"] == 0


def test_vista_previa(sin_sesion, dataset):
    r = sin_sesion.get(f"/api/datasets/{dataset}/vista-previa")
    assert r.status_code == 200
    assert r.json()["columnas"] == ["folio", "colonia", "latitud", "longitud"]
    assert r.json()["total_filas"] == 3


# --- Búsqueda semántica ---

def test_busqueda_semantica_encuentra_por_significado(sesion):
    r = publicar(
        sesion("admin"),
        titulo="Rutas de recolección de basura",
        descripcion="Horarios y recorridos de los camiones recolectores de residuos por colonia.",
        dependencia="Dirección General de Limpia",
        categoria="Medio Ambiente",
    )
    assert r.status_code == 201
    # La consulta no comparte palabras clave con el título ("rutas", "recolección"): se encuentra por significado
    r = sesion(None).get("/api/buscar", params={"prompt": "a qué hora pasa el camión de la basura"})
    assert r.status_code == 200
    titulos = [d["dataset_recomendado"] for d in r.json()["resultados"]]
    assert "Rutas de recolección de basura" in titulos


def test_busqueda_sin_relacion_no_devuelve_el_dataset(sesion):
    """El umbral de distancia descarta los datasets que no tienen que ver con la consulta."""
    r = publicar(
        sesion("admin"),
        titulo="Puntos de reciclaje",
        descripcion="Contenedores para separar vidrio, papel, cartón y plástico en parques y plazas.",
        dependencia="Dirección General de Medio Ambiente",
        categoria="Medio Ambiente",
    )
    assert r.status_code == 201
    r = sesion(None).get("/api/buscar", params={"prompt": "receta de pastel de chocolate"})
    assert r.status_code == 200
    assert "Puntos de reciclaje" not in [d["dataset_recomendado"] for d in r.json()["resultados"]]


def test_busqueda_de_un_caracter_da_422(sin_sesion):
    assert sin_sesion.get("/api/buscar", params={"prompt": "a"}).status_code == 422


def test_categorias_oficiales(sin_sesion):
    from app.catalogo import CATEGORIAS
    assert sin_sesion.get("/api/categorias").json()["categorias"] == CATEGORIAS
