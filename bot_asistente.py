import yaml
import logging
from telegram.ext import ApplicationBuilder, MessageHandler, filters, CommandHandler
from mistralai import Mistral
import logging

# Configuración básica para que los logs salgan por pantalla
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # <--- Fundamental para ver los .info()
)

# Importar herramientas (se mantienen por si las usas directamente en main, 
# aunque la mayoría ya las gestiona brain.py)
from tools_system import init_calendar
from brain_v2 import (
    handle_text,
    handle_voice,
    handle_command,
    start_command,
    configurar_comandos,
    crear_studio_command,
    recibir_prompt_studio
)

# ---------------- LOGS ----------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ---------------- CONFIG & CLIENTS ----------------
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# Inicializamos el cliente de Mistral una sola vez aquí
client = Mistral(api_key=config["mistral"]["api_key"])

# ---------------- WRAPPERS (LA CLAVE) ----------------
# Como Telegram pasa (update, context) a los handlers, usamos estas mini-funciones
# para "inyectar" el client y el config que Robi necesita para funcionar.

async def text_wrapper(update, context):
    await handle_text(update, context, client, config)

async def voice_wrapper(update, context):
    await handle_voice(update, context, client, config)

async def command_wrapper(update, context):
    # Para comandos tipo /deep NVDA
    await handle_command(update, context, client, config)

# ---------------- MAIN ----------------
if __name__ == "__main__":
    logging.info("🚀 Robi despertando")
    # 1. Inicializar Calendar
    try:
        calendar_ok = init_calendar()
    except Exception as e:
        logging.warning(f"⚠️ Google Calendar deshabilitado: {e}")
        calendar_ok = False

    # 2. Configurar el menú de comandos
    async def post_init(application):
        await configurar_comandos(application)
        logging.info("✅ Menú de comandos configurado")

    # 3. Construir la aplicación
    app = (
        ApplicationBuilder()
        .token(config["telegram"]["bot_token"])
        .post_init(post_init)
        .build()
    )

    # 4. Añadir manejadores usando los wrappers
    # Nota: El orden importa. Los comandos específicos primero.
    app.add_handler(CommandHandler("start", start_command))
    # Crear wrapper para studio que inyecte client y config
    async def studio_wrapper(update, context):
        await crear_studio_command(update, context, client, config)

    app.add_handler(CommandHandler(["studio", "sudio"], studio_wrapper))
    app.add_handler(CommandHandler(["oportunidades", "inversiones", "seguimiento", "evaluar", "ip", "deep"], command_wrapper))
    

    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_wrapper))
    app.add_handler(MessageHandler(filters.VOICE, voice_wrapper))
    
    # 5. Logs y arranque
    logging.info(f"🚀 Robi despertando (Calendar: {'ACTIVO' if calendar_ok else 'OFF'})")
    
    app.run_polling()
