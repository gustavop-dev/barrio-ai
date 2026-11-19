FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY --from=equipo grafo.yaml ./equipos/grafo.yaml
COPY manage.py ./
# Pango for WeasyPrint (lienzo.py: the free infographic canvas, rendered without a browser; its font is the bundled
# Ubuntu.ttf). ~17 MB with fontconfig; no Chromium.
RUN apt-get update && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev && useradd --uid 10001 --create-home app && mkdir staticfiles media && chown app:app staticfiles media
COPY assets/tiktoken ./assets/tiktoken
ENV TIKTOKEN_CACHE_DIR="/app/assets/tiktoken"
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
RUN python -c "import tiktoken; assert tiktoken.get_encoding('cl100k_base').encode('LinkedIn')"
# The commit this image was built from (CI passes it); /health shows it so the OTA workflow knows the deploy landed.
ARG BARRIO_REVISION=""
ENV BARRIO_REVISION=$BARRIO_REVISION
CMD ["gunicorn", "linkedin_backend.wsgi:application", "--bind", "0.0.0.0:8787", "--workers", "2", "--timeout", "300", "--access-logfile", "-"]
