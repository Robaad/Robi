import logging

import yaml
from mistralai import Mistral
from telegram import BotCommand, BotCommandScopeChat
from telegram.error import BadRequest
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# ── Brain V3: arquitectura Plan-and-Execute ──────────────────────────────────
from brain_v3 import (
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

# Comandos accesibles para usuarios restringidos
COMANDOS_RESTRINGIDOS_PERMITIDOS = {"/generarpartitura", "/ip", "/studio"}


def _allowed_users() -> list[int]:
    return config.get("telegram", {}).get("allowed_users", [])


def _allowed_restricted_users() -> list[int]:
    return config.get("telegram", {}).get("allowed_restricted_users", [])


def _usuario_autorizado(chat_id: int) -> bool:
    return chat_id in _allowed_users() or chat_id in _allowed_restricted_users()


def _comando_permitido(chat_id: int, command_text: str) -> bool:
    if chat_id not in _allowed_restricted_users():
        return True
    if not command_text:
        return False
    comando = command_text.split()[0].lower().split("@")[0]
    return comando in COMANDOS_RESTRINGIDOS_PERMITIDOS


async def _denegar_acceso(update):
    await update.message.reply_text("⛔ No estás autorizado para usar Robi.")


async def _denegar_comando(update):
    await update.message.reply_text(
        "❌ No tienes permiso para usar este comando.\n"
        "✅ Comandos disponibles para tu usuario: /generarpartitura, /ip y /studio."
    )


# ── Wrappers de autorización ─────────────────────────────────────────────────

async def start_wrapper(update, context):
    if not _usuario_autorizado(update.effective_chat.id):
        await _denegar_acceso(update)
        return
    if not _comando_permitido(update.effective_chat.id, "/start"):
        await _denegar_comando(update)
        return
    await start_command(update, context)


async def text_wrapper(update, context):
    if not _usuario_autorizado(update.effective_chat.id):
        await _denegar_acceso(update)
        return
    await handle_text(update, context, client, config)


async def voice_wrapper(update, context):
    if not _usuario_autorizado(update.effective_chat.id):
        await _denegar_acceso(update)
        return
    await handle_voice(update, context, client, config)


async def command_wrapper(update, context):
    if not _usuario_autorizado(update.effective_chat.id):
        await _denegar_acceso(update)
        return
    await handle_command(update, context, client, config)


async def studio_wrapper(update, context):
    chat_id = update.effective_chat.id
    if not _usuario_autorizado(chat_id):
        await _denegar_acceso(update)
        return
    if not _comando_permitido(chat_id, "/studio"):
        await _denegar_comando(update)
        return
    await crear_studio_command(update, context, client, config)


async def studiodiario_wrapper(update, context):
    chat_id = update.effective_chat.id
    if not _usuario_autorizado(chat_id):
        await _denegar_acceso(update)
        return
    if not _comando_permitido(chat_id, "/studiodiario"):
        await _denegar_comando(update)
        return
    await crear_studiodiario_command(update, context, client, config)


async def generarpartitura_wrapper(update, context):
    chat_id = update.effective_chat.id
    if not _usuario_autorizado(chat_id):
        await _denegar_acceso(update)
        return
    if not _comando_permitido(chat_id, "/generarpartitura"):
        await _denegar_comando(update)
        return
    await generar_partitura_command(update, context)


# ── App builder ───────────────────────────────────────────────────────────────

def build_app():
    try:
        calendar_ok = init_calendar()
    except Exception as e:
        logging.warning("⚠️ Google Calendar deshabilitado: %s", e)
        calendar_ok = False

    async def post_init(application):
        await configurar_comandos(application)

        comandos_restringidos = [
            BotCommand("generarpartitura", "🎵 Generar lectura a vista para fagot"),
            BotCommand("ip",     "Consultar IP pública"),
            BotCommand("studio", "Generar informe/estudio"),
        ]
        for chat_id in _allowed_restricted_users():
            try:
                await application.bot.set_my_commands(
                    comandos_restringidos,
                    scope=BotCommandScopeChat(chat_id=chat_id),
                )
            except BadRequest as e:
                logging.warning("⚠️ Menú restringido fallido para un usuario: %s", e)

        programar_studio_diario(application, client, config)
        logging.info("✅ Brain V3 (Plan-and-Execute) activo")
        logging.info("✅ Menú de comandos configurado")
        logging.info("✅ Programación /studiodiario activa")

    app = (
        ApplicationBuilder()
        .token(config["telegram"]["bot_token"])
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start_wrapper))
    app.add_handler(CommandHandler(["studio", "sudio"], studio_wrapper))
    app.add_handler(CommandHandler(["studiodiario"], studiodiario_wrapper))
    app.add_handler(CommandHandler("generarpartitura", generarpartitura_wrapper))
    app.add_handler(
        CommandHandler(
            [
                "oportunidades", "inversiones", "seguimiento", "evaluar",
                "ip", "deep", "noticias", "resumen_semanal", "resumensemanal",
                "calendario",
            ],
            command_wrapper,
        )
    )
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_wrapper))
    app.add_handler(MessageHandler(filters.VOICE, voice_wrapper))

    logging.info("🚀 Robi despertando con Brain V3 (Calendar: %s)", "ACTIVO" if calendar_ok else "OFF")
    return app


if __name__ == "__main__":
    logging.info("🚀 Robi despertando")
    build_app().run_polling()