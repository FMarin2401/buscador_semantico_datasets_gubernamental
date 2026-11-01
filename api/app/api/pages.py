import os

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

# Carpeta del frontend, si esta imagen lo incluye: "frontend" en la imagen de Azure (un solo contenedor) y
# "../frontend" al correr la API a mano desde api/. En docker compose no existe ninguna: ahí el frontend
# lo sirve su propio contenedor (nginx) y la API solo atiende /api y la documentación.
FRONTEND_DIR = next((d for d in ("frontend", "../frontend") if os.path.isdir(d)), None)

# Fuera de /docs: son páginas HTML, no parte de la API
router = APIRouter(tags=["Páginas Web"], include_in_schema=False)
templates = Jinja2Templates(directory=FRONTEND_DIR or "frontend")

@router.get("/")
async def vista_inicio(request: Request):
    return templates.TemplateResponse(request, "index.html")

@router.get("/explorar_datos.html")
async def vista_datos(request: Request):
    return templates.TemplateResponse(request, "explorar_datos.html")

@router.get("/gobierno_abierto.html")
async def vista_gobierno_abierto(request: Request):
    return templates.TemplateResponse(request, "gobierno_abierto.html")

@router.get("/apis.html")
async def vista_apis(request: Request):
    return templates.TemplateResponse(request, "apis.html")

@router.get("/guia_usuario.html")
async def vista_guia(request: Request):
    return templates.TemplateResponse(request, "guia_usuario.html")

@router.get("/contacto.html")
async def vista_contacto(request: Request):
    return templates.TemplateResponse(request, "contacto.html")

@router.get("/preguntas_frecuentes.html")
async def vista_preguntas(request: Request):
    return templates.TemplateResponse(request, "preguntas_frecuentes.html")

@router.get("/aviso_privacidad.html")
async def vista_aviso_privacidad(request: Request):
    return templates.TemplateResponse(request, "aviso_privacidad.html")

@router.get("/terminos_uso.html")
async def vista_terminos_uso(request: Request):
    return templates.TemplateResponse(request, "terminos_uso.html")

@router.get("/politicas_datos_abiertos.html")
async def vista_politicas_datos_abiertos(request: Request):
    return templates.TemplateResponse(request, "politicas_datos_abiertos.html")

@router.get("/login.html")
async def vista_login(request: Request):
    return templates.TemplateResponse(request, "login.html")

@router.get("/admin.html")
async def vista_admin(request: Request):
    return templates.TemplateResponse(request,"admin.html")