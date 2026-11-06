FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY manage.py ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev && useradd --uid 10001 --create-home app && mkdir staticfiles && chown app:app staticfiles
COPY assets/tiktoken ./assets/tiktoken
ENV TIKTOKEN_CACHE_DIR="/app/assets/tiktoken"
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
RUN python -c "import tiktoken; assert tiktoken.get_encoding('cl100k_base').encode('LinkedIn')"
CMD ["gunicorn", "linkedin_backend.wsgi:application", "--bind", "0.0.0.0:8787", "--workers", "2", "--timeout", "120", "--access-logfile", "-"]
