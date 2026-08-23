FROM python:3.12-alpine
WORKDIR /app
COPY web/dist /app/web/dist
COPY web-server /app/web-server
COPY templates /app/templates
ENV PLAUDE_BIND=0.0.0.0
ENV PLAUDE_PORT=8080
ENV PLAUDE_DATA_DIR=/data
ENV PLAUDE_STATIC_DIR=/app/web/dist
EXPOSE 8080
CMD ["python", "/app/web-server/server.py"]
