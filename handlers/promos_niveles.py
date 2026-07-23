# ============================================================
# Smm Panel Bot - Promociones y Niveles
# Author: learningbots79 (https://github.com/learningbots79) 
# ============================================================

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime
import random
import string
import db
from config import OWNER_ID

# Estados temporales
estado_admin = {}

def generar_codigo(longitud=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=longitud))

# ================ CÓDIGOS PROMOCIONALES ================
async def menu_codigos(_, callback):
    texto = """🎟 **GESTIÓN DE CÓDIGOS**
Crea códigos para regalar saldo o dar descuentos"""
    botones = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Crear Nuevo", callback_data="crear_codigo")],
        [InlineKeyboardButton("📜 Ver Activos", callback_data="ver_codigos")],
        [InlineKeyboardButton("❌ Eliminar", callback_data="eliminar_codigo_m"),
         InlineKeyboardButton("🔙 Volver", callback_data="volver_admin")]
    ])
    await callback.message.edit_text(texto, reply_markup=botones)

async def procesar_crear_codigo(client, message):
    uid = message.from_user.id
    if uid not in estado_admin or estado_admin[uid].get("paso") != "creando_codigo":
        return False
    datos = estado_admin[uid]
    texto = message.text.strip()

    if datos["etapa"] == "tipo":
        if texto.lower() not in ["saldo", "descuento"]:
            await message.reply("❌ Escribe solo: **saldo** o **descuento**")
            return True
        datos["tipo"] = texto.lower()
        datos["etapa"] = "valor"
        await message.reply("✏️ Escribe el valor: monto de saldo o porcentaje:")

    elif datos["etapa"] == "valor":
        if not texto.replace(".","",1).isdigit():
            await message.reply("❌ Solo números:")
            return True
        datos["valor"] = float(texto)
        datos["etapa"] = "usos"
        await message.reply("🔢 ¿Cuántas veces se puede usar? (ej: 10 o 9999 para ilimitado):")

    elif datos["etapa"] == "usos":
        if not texto.isdigit():
            await message.reply("❌ Solo números:")
            return True
        usos = int(texto)
        codigo = generar_codigo()
        await db.crear_codigo_promo({
            "codigo": codigo,
            "tipo": datos["tipo"],
            "valor": datos["valor"],
            "max_usos": usos,
            "usado": 0,
            "estado": "ACTIVO",
            "creado": datetime.now().strftime("%d/%m/%Y %H:%M")
        })
        del estado_admin[uid]
        await message.reply(f"""✅ CÓDIGO CREADO:
🎟 `{codigo}`
🔖 Tipo: {datos['tipo']}
💰 Valor: {datos['valor']}
🔄 Usos máx: {usos}""")
    return True

# ================ NIVELES DE USUARIO ================
async def menu_niveles(_, callback):
    lista = await db.obtener_todos_niveles()
    texto = "🏅 **NIVELES DE CLIENTES**\n\n"
    for n in lista:
        texto += f"""Nivel {n['nivel']}:
  ├─ Requiere: {n['gasto_requerido']} gastado
  └─ Descuento: {n['descuento']}%
"""
    botones = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Agregar/Editar", callback_data="editar_nivel"),
         InlineKeyboardButton("🔙 Volver", callback_data="volver_admin")]
    ])
    await callback.message.edit_text(texto, reply_markup=botones)

async def procesar_nivel(client, message):
    uid = message.from_user.id
    if uid not in estado_admin or estado_admin[uid].get("paso") != "creando_nivel":
        return False
    datos = estado_admin[uid]
    texto = message.text.strip()

    if datos["etapa"] == "numero":
        if not texto.isdigit():
            await message.reply("❌ Número de nivel:")
            return True
        datos["nivel"] = int(texto)
        datos["etapa"] = "gasto"
        await message.reply("💵 ¿Cuánto debe haber gastado para alcanzarlo?:")

    elif datos["etapa"] == "gasto":
        if not texto.replace(".","",1).isdigit():
            await message.reply("❌ Monto:")
            return True
        datos["gasto"] = float(texto)
        datos["etapa"] = "desc"
        await message.reply("📉 Porcentaje de descuento:")

    elif datos["etapa"] == "desc":
        if not texto.replace(".","",1).isdigit():
            await message.reply("❌ Porcentaje:")
            return True
        await db.guardar_nivel({
            "nivel": datos["nivel"],
            "gasto_requerido": datos["gasto"],
            "descuento": float(texto)
        })
        del estado_admin[uid]
        await message.reply("✅ Nivel guardado correctamente")
    return True

def register_promos_niveles_handlers(app: Client):

    # ---- Menús ----
    @app.on_callback_query(filters.regex("^menu_codigos$") & filters.user(OWNER_ID))
    async def _m1(c,q): await menu_codigos(c,q)

    @app.on_callback_query(filters.regex("^menu_niveles$") & filters.user(OWNER_ID))
    async def _m2(c,q): await menu_niveles(c,q)

    # ---- Acciones Admin ----
    @app.on_callback_query(filters.regex("^crear_codigo$") & filters.user(OWNER_ID))
    async def iniciar_creacion(_, callback):
        estado_admin[callback.from_user.id] = {"paso": "creando_codigo", "etapa": "tipo"}
        await callback.message.edit_text("✏️ ¿Qué tipo es? Escribe: **saldo** o **descuento**")

    @app.on_callback_query(filters.regex("^ver_codigos$") & filters.user(OWNER_ID))
    async def listar_codigos(_, callback):
        lista = await db.obtener_codigos_activos()
        if not lista: return await callback.answer("Sin códigos activos", show_alert=True)
        texto = "🎟 Códigos activos:\n"
        for c in lista:
            texto += f"`{c['codigo']}` | {c['tipo']} {c['valor']} | Usados: {c['usado']}/{c['max_usos']}\n"
        await callback.message.edit_text(texto)

    @app.on_callback_query(filters.regex("^editar_nivel$") & filters.user(OWNER_ID))
    async def iniciar_nivel(_, callback):
        estado_admin[callback.from_user.id] = {"paso": "creando_nivel", "etapa": "numero"}
        await callback.message.edit_text("✏️ Número del nivel (ej: 1, 2, 3):")

    # ---- USUARIO: Canjear código ----
    @app.on_callback_query(filters.regex("^usar_codigo$"))
    async def pedir_codigo(_, callback):
        estado_admin[callback.from_user.id] = {"paso": "usando"}
        await callback.message.edit_text("🎟 Escribe el código que tienes:")

    # ---- Procesador general ----
    @app.on_message(filters.private & ~filters.command("start"))
    async def procesar_todo(client, message):
        uid = message.from_user.id
        if uid not in estado_admin: return

        if estado_admin[uid].get("paso") == "creando_codigo":
            if await procesar_crear_codigo(client, message): return
        elif estado_admin[uid].get("paso") == "creando_nivel":
            if await procesar_nivel(client, message): return
        elif estado_admin[uid].get("paso") == "usando":
            codigo = message.text.strip().upper()
            res = await db.canjear_codigo(uid, codigo)
            del estado_admin[uid]
            config = await db.obtener_config()
            moneda = config.get("moneda", "USD")
            if res == "aplicado_saldo":
                await message.reply(f"✅ ¡Agregado a tu saldo!")
            elif res == "aplicado_desc":
                await message.reply(f"✅ Descuento activo para tu próxima compra")
            elif res == "agotado":
                await message.reply("❌ Este código ya se usó todas las veces")
            elif res == "ya_usado":
                await message.reply("⚠️ Tú ya usaste este código antes")
            else:
                await message.reply("❌ Código no válido o inactivo")

    print("✅ Módulo Promociones y Niveles cargado")
