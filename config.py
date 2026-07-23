# ============================================================
# Smm Panel Bot - Configuración
# Author: learningbots79 (https://github.com/learningbots79) 
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()

# ------------------ DATOS FIJOS ------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "panel_smm_bot")

OWNER_ID = int(os.getenv("OWNER_ID", 0))
FORCE_CHANNEL = os.getenv("FORCE_CHANNEL", "")

SMM_SITE = os.getenv("SMM_SITE", "mysmmshop.com")
SMM_API_URL = os.getenv("SMM_API_URL", "https://mysmmshop.com/api/v2")
SMM_API_KEY = os.getenv("SMM_API_KEY", "")
SMM_API_URL_SECUNDARIO = os.getenv("SMM_API_URL_SECUNDARIO", "")
SMM_API_KEY_SECUNDARIO = os.getenv("SMM_API_KEY_SECUNDARIO", "")

INTERVALO_SINCRONIZACION = int(os.getenv("INTERVALO_SINCRONIZACION", 259200))
DIAS_ELIMINAR_PEDIDOS = int(os.getenv("DIAS_ELIMINAR_PEDIDOS", 90))

REFERRER_BONUS = float(os.getenv("REFERRER_BONUS", 10))
DAILY_BONUS = float(os.getenv("DAILY_BONUS", 10))
QR_IMAGE = os.getenv("QR_IMAGE", "")
ORDER_CHANNEL = os.getenv("ORDER_CHANNEL", "")
ENLACE_TU_TIENDA = os.getenv("ENLACE_TU_TIENDA", "")
