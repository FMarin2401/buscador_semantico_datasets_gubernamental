# SC-001: los ciudadanos reportan problemas en un dataset y el equipo municipal los atiende desde el panel.
# Ver docs/solicitudes_cambio.md

import logging
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import verificar_token, requiere_admin
from app.api.esquemas import MensajeRespuesta, ERROR_401, ERROR_403, ERROR_429, error
from app.db_core.auditoria import registrar_evento_auditoria
from app.db_core.connection import get_db
from app.db_core.models import DatasetModel, ReporteDatasetModel, UsuarioModel, ahora_utc
from app.limiter import limiter

router = APIRouter(tags=["Reportes de datasets (SC-001)"])
logger = logging.getLogger(__name__)

TipoReporte = Literal["datos_incorrectos", "desactualizado", "archivo_danado", "otro"]
EstadoReporte = Literal["abierto", "en_revision", "resuelto"]

# Regla de negocio: un reporte avanza abierto -> en_revision -> resuelto (o directo de abierto a resuelto)
# y nunca retrocede. Un reporte resuelto queda cerrado.
TRANSICIONES = {
    "abierto": {"en_revision", "resuelto"},
    "en_revision": {"resuelto"},
    "resuelto": set(),
}


# --- Esquemas ---

class NuevoReporte(BaseModel):
    tipo: TipoReporte = Field(description="Clase de problema")
    descripcion: str = Field(min_length=10, max_length=1000, description="Qué está mal y dónde")
    email_contacto: Optional[EmailStr] = Field(default=None, description="Opcional, para avisar al ciudadano cuando se atienda")

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "tipo": "desactualizado",
        "descripcion": "La lista de clínicas no incluye la nueva clínica de la colonia Las Joyas.",
        "email_contacto": "ciudadano@ejemplo.com",
    }]})


class ReporteCreado(BaseModel):
    id: int
    estado: EstadoReporte
    mensaje: str

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "id": 12, "estado": "abierto", "mensaje": "Reporte recibido. El equipo municipal lo revisará.",
    }]})


class ReporteDetalle(BaseModel):
    id: int
    id_dataset: str
    dataset: str = Field(description="Título del dataset reportado")
    tipo: TipoReporte
    descripcion: str
    email_contacto: Optional[str]
    estado: EstadoReporte
    fecha_creacion: datetime = Field(description="UTC")
    fecha_actualizacion: Optional[datetime] = Field(description="UTC; última vez que cambió de estado")
    atendido_por: Optional[str] = Field(description="Funcionario que hizo el último cambio de estado")

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "id": 12,
        "id_dataset": "5167d1f6-a031-5658-8bae-ffe0879ce129",
        "dataset": "Clínicas de Salud",
        "tipo": "desactualizado",
        "descripcion": "La lista de clínicas no incluye la nueva clínica de la colonia Las Joyas.",
        "email_contacto": "ciudadano@ejemplo.com",
        "estado": "en_revision",
        "fecha_creacion": "2026-11-01T18:30:00",
        "fecha_actualizacion": "2026-11-01T19:05:00",
        "atendido_por": "admin_leon",
    }]})


class ListaReportes(BaseModel):
    reportes: list[ReporteDetalle]


class CambioEstado(BaseModel):
    estado: EstadoReporte

    model_config = ConfigDict(json_schema_extra={"examples": [{"estado": "en_revision"}]})


class ResumenDataset(BaseModel):
    id: str
    titulo: str
    categoria: str
    dependencia: str
    total_descargas: int
    total_reportes: int
    reportes_pendientes: int = Field(description="Reportes abiertos o en revisión")
    ultimo_reporte: Optional[datetime]


class ListaResumen(BaseModel):
    datasets: list[ResumenDataset]




def a_detalle(reporte: ReporteDatasetModel) -> ReporteDetalle:
    return ReporteDetalle(
        id=reporte.id,
        id_dataset=reporte.id_dataset,
        dataset=reporte.dataset.titulo if reporte.dataset else "",
        tipo=reporte.tipo,
        descripcion=reporte.descripcion,
        email_contacto=reporte.email_contacto,
        estado=reporte.estado,
        fecha_creacion=reporte.fecha_creacion,
        fecha_actualizacion=reporte.fecha_actualizacion,
        atendido_por=reporte.atendido_por.username if reporte.atendido_por else None,
    )


def obtener_reporte(db: Session, id_reporte: int) -> ReporteDatasetModel:
    reporte = db.get(ReporteDatasetModel, id_reporte)
    if not reporte:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reporte no encontrado.")
    return reporte


# --- Endpoints ---

@router.post(
    "/api/datasets/{id_dataset}/reportes",
    status_code=status.HTTP_201_CREATED,
    response_model=ReporteCreado,
    summary="Reportar un problema en un dataset",
    description="Endpoint público (sin sesión). El reporte se crea en estado `abierto`. Límite: 5 reportes por minuto por IP.",
    responses={404: error("El dataset no existe", "Dataset no encontrado."), 429: ERROR_429},
)
@limiter.limit("5/minute")
def crear_reporte(request: Request, id_dataset: UUID, datos: NuevoReporte, db: Session = Depends(get_db)):
    id_dataset = str(id_dataset)
    if not db.get(DatasetModel, id_dataset):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset no encontrado.")

    reporte = ReporteDatasetModel(
        id_dataset=id_dataset,
        tipo=datos.tipo,
        descripcion=datos.descripcion.strip(),
        email_contacto=datos.email_contacto,
    )
    db.add(reporte)
    db.commit()
    logger.info(f"Nuevo reporte {reporte.id} ({datos.tipo}) sobre el dataset {id_dataset}")
    return ReporteCreado(id=reporte.id, estado=reporte.estado, mensaje="Reporte recibido. El equipo municipal lo revisará.")


@router.get(
    "/api/admin/reportes",
    response_model=ListaReportes,
    summary="Listar los reportes",
    description="Del más reciente al más antiguo. Requiere sesión (administrador o editor).",
    responses={401: ERROR_401},
)
def listar_reportes(
    estado: Optional[EstadoReporte] = Query(None, description="Filtra por estado; sin valor devuelve todos"),
    usuario_autenticado: str = Depends(verificar_token),
    db: Session = Depends(get_db),
):
    consulta = db.query(ReporteDatasetModel)
    if estado:
        consulta = consulta.filter(ReporteDatasetModel.estado == estado) # Usa el índice ix_reportes_estado_fecha
    reportes = consulta.order_by(ReporteDatasetModel.fecha_creacion.desc()).all()
    return ListaReportes(reportes=[a_detalle(r) for r in reportes])


@router.get(
    "/api/admin/reportes/resumen-datasets",
    response_model=ListaResumen,
    summary="Datasets con reportes",
    description="Lee la vista `v_resumen_datasets`: descargas y reportes por dataset, primero los que tienen más reportes pendientes. Requiere sesión.",
    responses={401: ERROR_401},
)
def resumen_datasets(usuario_autenticado: str = Depends(verificar_token), db: Session = Depends(get_db)):
    filas = db.execute(text(
        "SELECT * FROM v_resumen_datasets WHERE total_reportes > 0 "
        "ORDER BY reportes_pendientes DESC, ultimo_reporte DESC"
    )).mappings().all()
    return ListaResumen(datasets=[ResumenDataset(**fila) for fila in filas])


@router.patch(
    "/api/admin/reportes/{id_reporte}",
    response_model=ReporteDetalle,
    summary="Cambiar el estado de un reporte",
    description=(
        "Transiciones permitidas: `abierto` → `en_revision` o `resuelto`; `en_revision` → `resuelto`. "
        "Un reporte no retrocede y uno resuelto ya no se modifica. Requiere sesión (administrador o editor)."
    ),
    responses={
        401: ERROR_401,
        404: error("El reporte no existe", "Reporte no encontrado."),
        409: error("Transición de estado no permitida", "Un reporte resuelto no se puede reabrir ni modificar."),
    },
)
def cambiar_estado_reporte(
    id_reporte: int,
    datos: CambioEstado,
    usuario_autenticado: str = Depends(verificar_token),
    db: Session = Depends(get_db),
):
    reporte = obtener_reporte(db, id_reporte)
    actual = reporte.estado

    if datos.estado == actual:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"El reporte ya está en estado '{actual}'.")
    if actual == "resuelto":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Un reporte resuelto no se puede reabrir ni modificar.")
    if datos.estado not in TRANSICIONES[actual]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se permite pasar de '{actual}' a '{datos.estado}': un reporte no retrocede.",
        )

    reporte.estado = datos.estado
    reporte.fecha_actualizacion = ahora_utc()
    reporte.atendido_por_id = db.query(UsuarioModel.id).filter(UsuarioModel.username == usuario_autenticado).scalar()
    registrar_evento_auditoria(db, usuario_autenticado, "Reporte", f"Reporte {id_reporte} de '{actual}' a '{datos.estado}'")
    db.commit()
    db.refresh(reporte)
    return a_detalle(reporte)


@router.delete(
    "/api/admin/reportes/{id_reporte}",
    response_model=MensajeRespuesta,
    summary="Eliminar un reporte",
    description="Para reportes duplicados o sin sentido. Solo administradores.",
    responses={401: ERROR_401, 403: ERROR_403, 404: error("El reporte no existe", "Reporte no encontrado.")},
)
def eliminar_reporte(id_reporte: int, usuario_autenticado: str = Depends(requiere_admin), db: Session = Depends(get_db)):
    reporte = obtener_reporte(db, id_reporte)
    db.delete(reporte)
    registrar_evento_auditoria(db, usuario_autenticado, "Eliminación Reporte", f"Reporte {id_reporte} ({reporte.tipo})")
    db.commit()
    return MensajeRespuesta(mensaje="Reporte eliminado.")
