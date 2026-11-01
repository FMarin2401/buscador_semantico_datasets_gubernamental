# Verifica que /openapi.json documente cada endpoint: descripción, esquemas, ejemplos y códigos de respuesta.
# Si se agrega un endpoint sin documentar, esta prueba falla.

import pytest

METODOS = ("get", "post", "put", "patch", "delete")


@pytest.fixture(scope="module")
def especificacion(cliente):
    return cliente.get("/openapi.json").json()


def operaciones(especificacion):
    for ruta, metodos in especificacion["paths"].items():
        for metodo, op in metodos.items():
            if metodo in METODOS:
                yield f"{metodo.upper()} {ruta}", op


def resolver(especificacion, esquema):
    if "$ref" in esquema:
        nombre = esquema["$ref"].split("/")[-1]
        return especificacion["components"]["schemas"][nombre]
    return esquema


def tiene_ejemplo(especificacion, esquema):
    esquema = resolver(especificacion, esquema)
    if esquema.get("examples") or esquema.get("example"):
        return True
    return any(prop.get("examples") or prop.get("example") for prop in esquema.get("properties", {}).values())


def test_no_hay_paginas_html_en_la_api(especificacion):
    assert not [r for r in especificacion["paths"] if r.endswith(".html") or r == "/"]


def test_cada_endpoint_tiene_resumen_y_descripcion(especificacion):
    faltan = [nombre for nombre, op in operaciones(especificacion) if not op.get("summary") or not op.get("description")]
    assert not faltan, f"Sin resumen o descripción: {faltan}"


def test_cada_respuesta_exitosa_tiene_esquema(especificacion):
    faltan = []
    for nombre, op in operaciones(especificacion):
        exitosa = next(v for codigo, v in op["responses"].items() if codigo.startswith("2"))
        contenido = exitosa.get("content", {})
        json_ = contenido.get("application/json", {}).get("schema")
        archivo = any(tipo != "application/json" for tipo in contenido) # Descargas: CSV, XML, GeoJSON
        if not archivo and not (json_ and resolver(especificacion, json_).get("properties")):
            faltan.append(nombre)
    assert not faltan, f"Sin esquema de respuesta: {faltan}"


def test_cada_cuerpo_de_entrada_tiene_ejemplo(especificacion):
    faltan = []
    for nombre, op in operaciones(especificacion):
        for contenido in op.get("requestBody", {}).get("content", {}).values():
            if not tiene_ejemplo(especificacion, contenido["schema"]):
                faltan.append(nombre)
    assert not faltan, f"Cuerpo de entrada sin ejemplo: {faltan}"


def test_endpoints_protegidos_documentan_401_y_la_cookie(especificacion):
    faltan = []
    for nombre, op in operaciones(especificacion):
        if op.get("security"):
            if "401" not in op["responses"]:
                faltan.append(nombre)
            assert op["security"] == [{"APIKeyCookie": []}], nombre
    assert not faltan, f"Protegidos sin 401 documentado: {faltan}"


def test_cada_endpoint_con_entradas_documenta_algun_error(especificacion):
    faltan = []
    for nombre, op in operaciones(especificacion):
        recibe_datos = op.get("parameters") or op.get("requestBody")
        errores = [c for c in op["responses"] if c.startswith(("4", "5"))]
        if recibe_datos and not errores:
            faltan.append(nombre)
    assert not faltan, f"Sin códigos de error: {faltan}"


def test_la_api_tiene_descripcion_y_grupos_descritos(especificacion):
    assert especificacion["info"]["description"].strip()
    assert all(grupo.get("description") for grupo in especificacion["tags"])
