# Esquemas y respuestas de error compartidos por los routers. Documentan la API en /docs (Swagger) y /openapi.json

from pydantic import BaseModel, Field


class ErrorRespuesta(BaseModel):
    detail: str = Field(description="Motivo del error, en texto para mostrarlo al usuario", examples=["Reporte no encontrado."])


class MensajeRespuesta(BaseModel):
    mensaje: str = Field(examples=["Operación realizada exitosamente"])


def error(descripcion: str, ejemplo: str) -> dict:
    """Entrada de "responses" para un código de error con su ejemplo propio."""
    return {
        "model": ErrorRespuesta,
        "description": descripcion,
        "content": {"application/json": {"example": {"detail": ejemplo}}},
    }


ERROR_401 = error("No hay sesión activa o expiró. Inicia sesión con POST /api/login", "No se encontró la sesión activa")
ERROR_403 = error("La sesión no es de un administrador", "Acceso denegado: se requiere rol de administrador.")
ERROR_429 = {"description": "Demasiadas peticiones desde la misma IP en el último minuto", "content": {"application/json": {"example": {"error": "Rate limit exceeded: 5 per 1 minute"}}}}
