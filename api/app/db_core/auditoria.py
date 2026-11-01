# Este archivo registra los eventos administrativos en la bitácora relacional

from sqlalchemy.orm import Session

from app.db_core.models import BitacoraAuditoriaModel, UsuarioModel


def registrar_evento_auditoria(db: Session, usuario: str, accion: str, detalles: str):
    """
    Agrega el evento a la sesión sin confirmarlo: quien llama hace el commit junto con el cambio que se registra,
    así el cambio y su evento se guardan o se descartan juntos.
    """
    usuario_id = db.query(UsuarioModel.id).filter(UsuarioModel.username == usuario).scalar()
    db.add(BitacoraAuditoriaModel(usuario=usuario, usuario_id=usuario_id, accion=accion, detalles=detalles))
