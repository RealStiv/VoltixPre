# ============================================================
# Smm Panel Bot
# Author: learningbots79 (https://github.com/learningbots79) 
# Support: https://t.me/LearningBotsCommunity
# Channel: https://t.me/learning_bots
# YouTube: https://youtube.com/@learning_bots
# License: Open-source (keep credits, no resale)
# ============================================================

from dotenv import load_dotenv
import os

load_dotenv()

# ==================================================
# ⚙️ CONFIGURACIÓN BÁSICA
# ==================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")
OWNER_ID = int(os.getenv("OWNER_ID"))
OWNER_USERNAME = os.getenv("OWNER_USERNAME")
REFERRER_BONUS = int(os.getenv("REFERRER_BONUS", 10))
DAILY_BONUS = int(os.getenv("DAILY_BONUS", 10))
QR_IMAGE = os.getenv("QR_IMAGE")
FORCE_CHANNEL = os.getenv("FORCE_CHANNEL")
ORDER_CHANNEL = os.getenv("ORDER_CHANNEL")

SMM_SITE = {
    "name": os.getenv("SMM_SITE"),            
    "api_url": os.getenv("SMM_API_URL"),         
    "api_key": os.getenv("SMM_API_KEY"),
    "api_url_secundario": os.getenv("SMM_API_URL_SECUNDARIO", ""),
    "api_key_secundario": os.getenv("SMM_API_KEY_SECUNDARIO", ""),       
    "services": {
        "reaction": int(os.getenv("REACTION_SERVICE_ID", 0)),
        "members": int(os.getenv("MEMBERS_SERVICE_ID", 0)),
        "views": int(os.getenv("VIEWS_SERVICE_ID", 0))
    }
}

# ==================================================
# 🆕 CONFIGURACIONES NUEVAS AGREGADAS
# ==================================================
MONEDA = os.getenv("MONEDA", "USD")
TIEMPO_ESPERA_PEDIDO = int(os.getenv("TIEMPO_ESPERA_PEDIDO", 2))
DIAS_ELIMINAR_PEDIDOS = int(os.getenv("DIAS_ELIMINAR_PEDIDOS", 90))
ENVIAR_RESPALDO_CADA__DIAS = int(os.getenv("ENVIAR_RESPALDO_CADA__DIAS", 7))
ENLACE_TU_TIENDA = os.getenv("ENLACE_TU_TIENDA", "")
MARGEN_GLOBAL = int(os.getenv("MARGEN_GLOBAL", 35))

# ⏱️ TIEMPO DE SINCRONIZACIÓN - EN SEGUNDOS
# Ejemplos: 3 min = 180 | 1 hora = 3600 | 3 días = 259200
INTERVALO_SINCRONIZACION = int(os.getenv("INTERVALO_SINCRONIZACION", 259200))

PALABRAS_PROHIBIDAS = [
    "prueba", "test", "fraude", "robado", "ilegal", "hack", "gratis"
]

# ==================================================
# 🛡️ VALIDACIÓN
# ==================================================
def validate_config():
    missing = []

    required_vars = [
        "BOT_TOKEN", "MONGO_URI", "DB_NAME", "OWNER_ID",
        "SMM_API_URL", "SMM_API_KEY",
        "REACTION_SERVICE_ID", "MEMBERS_SERVICE_ID", "VIEWS_SERVICE_ID",
        "ORDER_CHANNEL", "ENLACE_TU_TIENDA"
    ]

    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        raise ValueError(
            f"❌ Faltan variables en el archivo .env: {', '.join(missing)}"
        )
