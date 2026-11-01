# Pruebas de autenticación y administración de funcionarios (app/api/auth.py, app/api/users.py)

import os


def test_login_correcto_crea_cookie_httponly(sin_sesion):
    r = sin_sesion.post("/api/login", json={"usuario": os.environ["ADMIN_USER"], "password": os.environ["ADMIN_PASSWORD"]})
    assert r.status_code == 200
    assert "access_token" not in r.text # El token no viaja en el cuerpo
    cookie = r.headers["set-cookie"]
    assert "access_token=" in cookie and "HttpOnly" in cookie


def test_login_con_contrasena_incorrecta_da_401(sin_sesion):
    r = sin_sesion.post("/api/login", json={"usuario": os.environ["ADMIN_USER"], "password": "incorrecta"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Usuario o contraseña incorrectos"


def test_usuario_inexistente_da_el_mismo_401(sin_sesion):
    r = sin_sesion.post("/api/login", json={"usuario": "no_existe", "password": "incorrecta"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Usuario o contraseña incorrectos" # No revela qué usuarios existen


def test_mas_de_5_intentos_de_login_por_minuto_da_429(sin_sesion):
    codigos = [sin_sesion.post("/api/login", json={"usuario": "x", "password": "y"}).status_code for _ in range(6)]
    assert codigos == [401] * 5 + [429]


def test_token_alterado_da_401(sin_sesion):
    sin_sesion.cookies.set("access_token", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.firma-falsa")
    assert sin_sesion.get("/api/auth/me").status_code == 401


def test_me_devuelve_usuario_y_rol(como_editor):
    assert como_editor.get("/api/auth/me").json() == {"username": "editor_pruebas", "rol": "editor"}


def test_admin_crea_y_borra_funcionario(como_admin):
    r = como_admin.post("/api/admin/usuarios", json={"username": "temporal", "password": "Temporal_2026", "rol": "editor"})
    assert r.status_code == 201

    usuarios = como_admin.get("/api/admin/usuarios").json()["usuarios"]
    nuevo = next(u for u in usuarios if u["username"] == "temporal")
    assert "password_hash" not in nuevo

    assert como_admin.delete(f"/api/admin/usuarios/{nuevo['id']}").status_code == 200
    assert como_admin.delete(f"/api/admin/usuarios/{nuevo['id']}").status_code == 404


def test_usuario_repetido_da_409(como_admin):
    r = como_admin.post("/api/admin/usuarios", json={"username": "editor_pruebas", "password": "Otra_2026", "rol": "editor"})
    assert r.status_code == 409


def test_rol_fuera_de_la_lista_da_422(como_admin):
    r = como_admin.post("/api/admin/usuarios", json={"username": "superusuario", "password": "Clave_2026", "rol": "superadmin"})
    assert r.status_code == 422


def test_admin_no_puede_borrar_su_propia_cuenta(como_admin):
    mi_id = next(u["id"] for u in como_admin.get("/api/admin/usuarios").json()["usuarios"] if u["username"] == os.environ["ADMIN_USER"])
    r = como_admin.delete(f"/api/admin/usuarios/{mi_id}")
    assert r.status_code == 400


def test_editor_no_administra_usuarios(como_editor):
    assert como_editor.get("/api/admin/usuarios").status_code == 403
    r = como_editor.post("/api/admin/usuarios", json={"username": "colado", "password": "Clave_2026", "rol": "admin"})
    assert r.status_code == 403


def test_logout_borra_la_cookie(como_editor):
    r = como_editor.post("/api/logout")
    assert r.status_code == 200
    assert 'access_token=""' in r.headers["set-cookie"] or "Max-Age=0" in r.headers["set-cookie"]
