FROM python:3.11-slim

# Instalamos dependencias del sistema
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 🔹 Copiamos primero requirements para aprovechar caché de Docker
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# 🔹 Ahora copiamos el código (cambia más frecuentemente)
COPY . .

CMD ["python", "bot_asistente.py"]