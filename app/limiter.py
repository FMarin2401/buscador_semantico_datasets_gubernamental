from fastapi import Request
from slowapi import Limiter


def obtener_ip_cliente(request: Request) -> str:
    """
    IP con la que se cuenta el rate limit.
    En Azure Container Apps el ingress agrega la IP real del cliente al FINAL de X-Forwarded-For.
    Lo que esté antes lo puede escribir el propio cliente, así que no se usa: con la primera IP
    (lo que hace Uvicorn con --forwarded-allow-ips=*) bastaría inventar una IP en cada intento para saltarse el límite.
    Sin la cabecera (desarrollo local) se usa la IP de la conexión.
    """
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[-1].strip()
    return request.client.host if request.client else "desconocida"


limiter = Limiter(key_func=obtener_ip_cliente)
