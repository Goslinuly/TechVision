FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Deps first for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway/Hetzner set $PORT; default to 8000 locally.
ENV PORT=8000
EXPOSE 8000
# sh -c so ${PORT} expands from the runtime env (Railway injects PORT);
# :-8000 keeps it valid if the platform doesn't set it.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
