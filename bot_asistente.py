import logging

import yaml
from mistralai import Mistral
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from brain_v2 import (
    configurar_comandos,
    crear_studio_command,
    crear_studiodiario_command,
    handle_command,
    handle_text,
    handle_voice,
    programar_studio_diario,
    start_command,
)
from tools_system import init_calendar
from generador_partitura import generar_partitura_command

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

client = Mistral(api_key=config["mistral"]["api_key"])


async def text_wrapper(update, context):
    await handle_text(update, context, client, config)


async def voice_wrapper(update, context):
    await handle_voice(update, context, client, config)


async def command_wrapper(update, context):
    await handle_command(update, context, client, config)


async def studio_wrapper(update, context):
    await crear_studio_command(update, context, client, config)


async def studiodiario_wrapper(update, context):
    await crear_studiodiario_command(update, context, client, config)


def build_app():
    try:
        calendar_ok = init_calendar()
    except Exception as e:
        logging.warning("⚠️ Google Calendar deshabilitado: %s", e)
        calendar_ok = False

    async def post_init(application):
        await configurar_comandos(application)
        programar_studio_diario(application, client, config)
        logging.info("✅ Menú de comandos configurado")
        logging.info("✅ Programación /studiodiario activa")

    app = (
        ApplicationBuilder()
        .token(config["telegram"]["bot_token"])
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler(["studio", "sudio"], studio_wrapper))
    app.add_handler(CommandHandler(["studiodiario"], studiodiario_wrapper))
    app.add_handler(CommandHandler("generarpartitura", generar_partitura_command))
    app.add_handler(
        CommandHandler(
            ["oportunidades", "inversiones", "seguimiento", "evaluar", "ip", "deep"],
            command_wrapper,
        )
    )
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_wrapper))
    app.add_handler(MessageHandler(filters.VOICE, voice_wrapper))

    logging.info("🚀 Robi despertando (Calendar: %s)", "ACTIVO" if calendar_ok else "OFF")
    return app


if __name__ == "__main__":
    logging.info("🚀 Robi despertando")
    build_app().run_polling()