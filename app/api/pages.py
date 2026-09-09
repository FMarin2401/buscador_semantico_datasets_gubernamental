from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["Páginas Web"])
templates = Jinja2Templates(directory="frontend")

@router.get("/")
async def vista_inicio(request: Request):
    return templates.TemplateResponse(request, "index.html")

@router.get("/explorar_datos.html")
async def vista_datos(request: Request):
    return templates.TemplateResponse(request, "explorar_datos.html")

@router.get("/gobierno_abierto.html")
async def vista_gobierno_abierto(request: Request):
    return templates.TemplateResponse(request, "gobierno_abierto.html")

@router.get("/contacto.html")
async def vista_contacto(request: Request):
    return templates.TemplateResponse(request, "contacto.html")

@router.get("/noticias.html")
async def vista_noticias(request: Request):
    return templates.TemplateResponse(request, "noticias.html")

@router.get("/apis.html")
async def vista_apis(request: Request):
    return templates.TemplateResponse(request, "apis.html")

@router.get("/guia_usuario.html")
async def vista_guia(request: Request):
    return templates.TemplateResponse(request, "guia_usuario.html")

@router.get("/preguntas_frecuentes.html")
async def vista_preguntas(request: Request):
    return templates.TemplateResponse(request, "preguntas_frecuentes.html")

@router.get("/aviso_privacidad.html")
async def vista_aviso_privacidad(request: Request):
    return templates.TemplateResponse(request, "aviso_privacidad.html")

@router.get("/terminos_uso.html")
async def vista_terminos_uso(request: Request):
    return templates.TemplateResponse(request, "terminos_uso.html")

@router.get("/politicas.html")
async def vista_politicas_datos_abiertos(request: Request):
    return templates.TemplateResponse(request, "politicas.html")

@router.get("/login.html")
async def vista_login(request: Request):
    return templates.TemplateResponse(request, "login.html")

@router.get("/admin.html")
async def vista_admin(request: Request):
    return templates.TemplateResponse(request,"admin.html")