FROM python:3.11-slim

# Instalamos dependencias del sistema
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    git \
    lilypond \
    fluidsynth \
    fluid-soundfont-gm \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 1. Copiamos requirements
COPY requirements.txt .

# 2. 🔥 ESTA ES LA LÍNEA CLAVE: Instalamos setuptools y actualizamos pip antes
# Esto garantiza que pkg_resources esté disponible para la compilación de Whisper
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 3. Ahora instalamos el resto del archivo
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copiamos el resto del código
COPY . .

CMD ["python", "bot_asistente.py"]