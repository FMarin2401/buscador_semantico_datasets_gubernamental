# Contenedor del frontend: renderiza las plantillas Jinja2 a HTML estático y las sirve con nginx,
# que además reenvía /api y la documentación al contenedor de la API (ver nginx.conf).

# Etapa 1: plantillas -> HTML
FROM python:3.12-slim AS render
RUN pip install --no-cache-dir jinja2==3.1.6
WORKDIR /src
COPY . .
RUN python render.py /dist

# Etapa 2: servidor web
FROM nginx:1.27.5-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=render /dist/ /usr/share/nginx/html/
COPY css/ /usr/share/nginx/html/css/
COPY js/ /usr/share/nginx/html/js/
COPY assets/ /usr/share/nginx/html/assets/
EXPOSE 80
