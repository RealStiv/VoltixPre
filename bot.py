# ============================================================
# Smm Panel Bot
# Author: learningbots79 (https://github.com/learningbots79) 
# Support: https://t.me/LearningBotsCommunity
# Channel: https://t.me/learning_bots
# YouTube: https://youtube.com/@learning_bots
# License: Open-source (keep credits, no resale)
# ============================================================

import logging
import os
import asyncio
from datetime import datetime, timedelta
import db
from handlers import all_handlers, tarea_sincronizacion_automatica, tareas_mantenimiento
from pyrogram import Client
from config import BOT_TOKEN, INTERVALO_SINCRONIZACION

logging.basicConfig(level=logging.INFO)

app = Client(
    "panel_bot",
    bot_token=BOT_TOKEN
)

async def iniciar_tareas_en_segundo_plano():
    """Ejecuta procesos automáticos sin detener el bot"""
    print("⏳ Realizando sincronización inicial...")
    await tarea_sincronizacion_automatica()
    
    while True:
        await tarea_sincronizacion_automatica()
        await tareas_mantenimiento()
        print(f"✅ Ciclo completado, próxima revisión en: {INTERVALO_SINCRONIZACION//3600} horas")
        await asyncio.sleep(INTERVALO_SINCRONIZACION)

async def main():
    all_handlers(app)
    print("✅ Bot está iniciando....")
    await app.start()
    asyncio.create_task(iniciar_tareas_en_segundo_plano())
    print("🚀 Sistema operativo completo con funciones automáticas activas")
    await asyncio.idle()

if __name__ == "__main__":
    asyncio.run(main())
