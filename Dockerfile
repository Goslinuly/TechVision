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
# run.py reads $PORT inside Python — no shell expansion, robust to how the
# platform invokes the start command.
CMD ["python", "run.py"]
