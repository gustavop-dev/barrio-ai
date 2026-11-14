# The navegador service: one Chromium per LinkedIn account (patchright) drawing on a virtual screen (Xvfb). README.md
# explains it; deploy/compose.prod.yaml runs it only under the `navegador` profile.
FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONPATH=/app
COPY pyproject.toml uv.lock ./
# patchright installs its own Chromium build and the system libraries it needs. Xvfb is the screen the browser draws
# on (it runs headed, as on a desktop), so the headless shell is left out; x11vnc and noVNC only serve the hand login
# (entrada.sh, NAVEGADOR_VNC=1).
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev \
 && apt-get update \
 && apt-get install -y --no-install-recommends xvfb x11vnc novnc websockify \
 && patchright install --with-deps --no-shell chromium \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --uid 10001 --create-home app \
 && mkdir -p /datos /tmp/.X11-unix && chown app:app /datos && chmod 1777 /tmp/.X11-unix
COPY navegador ./navegador
# linkedin_directo (the allowlist and how LinkedIn's answers are judged) lives with the backend; the `directo` build
# context brings that one folder, so the service and the backend check calls with the same code.
COPY --from=directo . ./linkedin_directo/
COPY entrada.sh /usr/local/bin/entrada.sh
ENV NAVEGADOR_HOST=0.0.0.0 NAVEGADOR_DATOS=/datos
USER app
EXPOSE 8790
ENTRYPOINT ["entrada.sh"]
CMD ["python", "-m", "navegador", "servir"]
