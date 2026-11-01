from fastapi import Request
from slowapi import Limiter


def obtener_ip_cliente(request: Request) -> str:
    """
    IP con la que se cuenta el rate limit: el ÚLTIMO valor de X-Forwarded-For, que es el que agrega el proxy
    más cercano a la app. Si algún proxy conserva la cabecera que manda el cliente, los valores anteriores
    los puede inventar el cliente; con el primero (lo que hace Uvicorn con --forwarded-allow-ips=*) bastaría
    una IP distinta en cada intento para saltarse el límite.
    El ingress de Azure Container Apps reemplaza la cabecera con la IP real (verificado en los logs), así que ahí
    trae un solo valor; tomar el último protege si la app se despliega detrás de otro proxy.
    Sin la cabecera (desarrollo local) se usa la IP de la conexión.
    """
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[-1].strip()
    return request.client.host if request.client else "desconocida"


limiter = Limiter(key_func=obtener_ip_cliente)
