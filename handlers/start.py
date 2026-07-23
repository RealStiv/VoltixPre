# ============================================================
# Smm Panel Bot
# Author: learningbots79 (https://github.com/learningbots79) 
# Support: https://t.me/LearningBotsCommunity
# Channel: https://t.me/learning_bots
# YouTube: https://youtube.com/@learning_bots
# License: Open-source (keep credits, no resale)
# ============================================================

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Message
from pyrogram.errors import FloodWait, RPCError, PeerIdInvalid
from datetime import datetime, timedelta
import asyncio
import logging
from config import (
    REFERRER_BONUS, OWNER_USERNAME, FORCE_CHANNEL, QR_IMAGE, DAILY_BONUS,
    OWNER_ID, MONEDA, ENLACE_TU_TIENDA, INTERVALO_SINCRONIZACION
)
import db
from handlers.services import fetch_all_services
import aiohttp

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(asctime)s - %(message)s')
logger = logging.getLogger(__name__)   

CHANNEL = FORCE_CHANNEL.replace("@", "")
broadcast_state = {}

# ============================================================
# Funciones auxiliares
# ============================================================
async def notify_user(client, user_id, msg):
    try:
        await client.send_message(user_id, msg)
    except:
        pass

async def check_force_sub(client, user_id):
    try:
        user = await client.get_chat_member(FORCE_CHANNEL, user_id)
        return user.status not in ["left", "kicked"]
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await check_force_sub(client, user_id)
    except PeerIdInvalid:
        return "INVALID_CHANNEL"
    except RPCError as e:
        if "chat_admin_required" in str(e).lower() or "not enough rights" in str(e).lower():
            return False
        return False

async def tiempo_faltante_seg(segundos):
    d = segundos // 86400
    h = (segundos % 86400) // 3600
    m = (segundos % 3600) // 60
    texto = []
    if d: texto.append(f"{d} días")
    if h: texto.append(f"{h} horas")
    if m: texto.append(f"{m} minutos")
    return ", ".join(texto) or "Menos de 1 minuto"

async def sincronizar_servicios_bd():
    datos_api = await fetch_all_services()
    if not datos_api:
        return 0, 0, 0
    nuevos_cat = nuevos_serv = actualizados = 0
    for item in datos_api:
        cat_nombre = str(item.get("category", "Sin Categoría")).strip().title()
        id_ext = str(item["service"])
        nombre = str(item["name"]).strip()
        costo = float(str(item["rate"]).replace(",", "."))
        from config import MARGEN_GLOBAL
        ganancia = costo * (MARGEN_GLOBAL / 100)
        precio_final = round(costo + ganancia, 4)

        creado = await db.guardar_categoria(cat_nombre)
        if creado: nuevos_cat +=1

        codigo = f"SVC-{id_ext}"
        resultado = await db.guardar_servicio({
            "codigo": codigo,
            "nombre": nombre,
            "id_proveedor": int(id_ext),
            "categoria": cat_nombre,
            "costo_1000": costo,
            "precio_1000": precio_final,
            "ganancia_1000": round(ganancia, 4),
            "estado": "Activo",
            "destacado": False,
            "minimo": 10,
            "maximo": 10000,
            "vistas": 0,
            "ultima_actualizacion": datetime.now().strftime("%d/%m/%Y %H:%M")
        })
        if resultado == "nuevo": nuevos_serv +=1
        else: actualizados +=1
    return nuevos_cat, nuevos_serv, actualizados

# ============================================================
# Menús
# ============================================================
async def menu_principal_general(user_nombre):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Mi Saldo", callback_data="cb_balance"),
         InlineKeyboardButton("🛒 Catálogo", callback_data="cb_services")],
        [InlineKeyboardButton("👤 Mi Perfil", callback_data="cb_perfil"),
         InlineKeyboardButton("📦 Mis Pedidos", callback_data="cb_mis_pedidos")],
        [InlineKeyboardButton("🗣 Invitar Amigos", callback_data="cb_invite"),
         InlineKeyboardButton("📊 Estadísticas", callback_data="cb_stats")],
        [InlineKeyboardButton("🎉 Reclamar Bono", callback_data="cb_bonus"),
         InlineKeyboardButton("🔗 Compartir Tienda", callback_data="cb_compartir")],
        [InlineKeyboardButton("🆘 Soporte", url=f"https://t.me/{OWNER_USERNAME}")]
    ])

async def menu_administrador():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Sincronizar Ahora", callback_data="admin_sincronizar"),
         InlineKeyboardButton("⏱️ Próxima Sincronización", callback_data="admin_proxima_sinc")],
        [InlineKeyboardButton("📊 Ganancias Totales", callback_data="admin_ganancias"),
         InlineKeyboardButton("👥 Ver Todos", callback_data="admin_ver_usuarios")],
        [InlineKeyboardButton("🚫 Bloquear Usuario", callback_data="admin_bloquear"),
         InlineKeyboardButton("📢 Mensaje General", callback_data="broadcast")],
        [InlineKeyboardButton("🗑️ Limpiar Pedidos", callback_data="admin_limpiar")]
    ])

async def start_menu(message, user):
    if user.id == OWNER_ID:
        texto = f"""╔══════════════════════════════════╗
║    🔐 PANEL DE ADMINISTRADOR       ║
╚══════════════════════════════════╝
👋 Bienvenido de vuelta {user.first_name}
⏱️ Sincronización cada: {await tiempo_faltante_seg(INTERVALO_SINCRONIZACION)}"""
        await message.reply(texto, reply_markup=await menu_administrador())
    else:
        texto = f"👋 Hola {user.first_name}! Bienvenido a tu tienda de servicios 🚀"
        await message.reply(texto, reply_markup=await menu_principal_general(user.first_name))

# ============================================================
# Registro de funciones
# ============================================================
def register_start_handlers(app: Client):

    @app.on_message(filters.command("start") & filters.private)
    async def start_command(client, message):
        user = message.from_user
        args = message.text.split()
        ref_id = None

        estado_canal = await check_force_sub(client, user.id)
        if estado_canal != True:
            await message.reply(
                "🚫 Primero debes unirte a nuestro canal oficial para usar el bot!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔔 Unirme al Canal", url=f"https://t.me/{CHANNEL}")],
                    [InlineKeyboardButton("✅ Ya estoy dentro", callback_data="cb_start")]
                ])
            )
            return

        if len(args) == 2:
            try: ref_id = int(args[1])
            except: ref_id = None

        es_nuevo = not await db.user_exists(user.id)
        await db.add_user(user.id, user.first_name, referred_by=ref_id if es_nuevo else None)

        if ref_id and ref_id != user.id and es_nuevo:
            await db.add_balance(ref_id, REFERRER_BONUS)
            await notify_user(client, ref_id, f"🎉 ¡Nuevo referido!\n💰 Recibiste {REFERRER_BONUS} {MONEDA}")

        await start_menu(message, user)

    @app.on_callback_query(filters.regex("^cb_start$"))
    async def cb_start_menu(client, callback):
        if not await check_force_sub(client, callback.from_user.id):
            await callback.answer("⚠️ Primero únete al canal oficial", show_alert=True)
            return
        try: await callback.message.delete()
        except: pass
        await start_menu(callback.message, callback.from_user)

    # ------------------ SALDO Y COMANDOS ADMIN ------------------
    @app.on_callback_query(filters.regex("^cb_balance$"))
    async def ver_saldo(client, callback):
        saldo = await db.check_balance(callback.from_user.id)
        await callback.answer(f"💰 Tu saldo actual: {saldo:.2f} {MONEDA}", show_alert=True)

    @app.on_message(filters.command("addbal") & filters.user(OWNER_ID))
    async def agregar_saldo(client, message):
        try: _, uid, monto = message.text.split()
                uid = int(uid); monto = float(monto)
                await db.users.update_one({"_id": uid}, {"$inc": {"balance": monto}})
                await message.reply(f"✅ Agregado: +{monto} {MONEDA} al usuario {uid}")
        except: await message.reply("❌ Formato: /addbal ID_USUARIO CANTIDAD")

    @app.on_message(filters.command("subbal") & filters.user(OWNER_ID))
    async def quitar_saldo(client, message):
        try: _, uid, monto = message.text.split()
                uid = int(uid); monto = float(monto)
                await db.users.update_one({"_id": uid}, {"$inc": {"balance": -monto}})
                await message.reply(f"✅ Descontado: -{monto} {MONEDA} al usuario {uid}")
        except: await message.reply("❌ Formato: /subbal ID_USUARIO CANTIDAD")

    @app.on_message(filters.command("setbal") & filters.user(OWNER_ID))
    async def poner_saldo(client, message):
        try: _, uid, monto = message.text.split()
                uid = int(uid); monto = float(monto)
                await db.users.update_one({"_id": uid}, {"$set": {"balance": monto}})
                await message.reply(f"✅ Saldo establecido: {monto} {MONEDA} para {uid}")
        except: await message.reply("❌ Formato: /setbal ID_USUARIO CANTIDAD")

    # ------------------ OTRAS OPCIONES ------------------
    @app.on_callback_query(filters.regex("^cb_perfil$"))
    async def mi_perfil(client, callback):
        datos = await db.users.find_one({"_id": callback.from_user.id})
        if not datos: return
        texto = f"""👤 TU PERFIL
📝 Nombre: {datos.get('name', '')}
📅 Ingreso: {datos.get('fecha_registro', '')}
🛒 Pedidos realizados: {datos.get('orders', 0)}
💸 Total gastado: {datos.get('total_gastado', 0):.2f} {MONEDA}
💰 Saldo disponible: {datos.get('balance', 0):.2f} {MONEDA}"""
        await callback.answer()
        await callback.message.edit_text(texto, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="cb_start")]]))

    @app.on_callback_query(filters.regex("^cb_invite$"))
    async def invitar(client, callback):
        referidos = await db.get_referrals(callback.from_user.id)
        enlace = f"https://t.me/{client.me.username}?start={callback.from_user.id}"
        texto = f"""🗣 PROGRAMA DE REFERIDOS
🎁 Por cada amigo: +{REFERRER_BONUS} {MONEDA}
👥 Total invitados: {referidos}

🔗 Tu enlace para compartir:
{enlace}"""
        await callback.message.edit_text(texto, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="cb_start")]]))

    @app.on_callback_query(filters.regex("^cb_stats$"))
    async def estadisticas_general(client, callback):
        total_usuarios = await db.total_users()
        texto = f"""📊 ESTADÍSTICAS DEL BOT
👥 Personas registradas: {total_usuarios}"""
        await callback.answer(texto, show_alert=True)

    @app.on_callback_query(filters.regex("^cb_bonus$"))
    async def bono_diario(client, callback):
        uid = callback.from_user.id
        ultimo = await db.get_last_bonus(uid)
        if ultimo:
            proximo = ultimo + timedelta(hours=24)
            if datetime.now() < proximo:
                falta = proximo - datetime.now()
                h = falta.seconds // 3600
                m = (falta.seconds % 3600) // 60
                return await callback.answer(f"⏳ Ya lo tomaste, vuelve en {h}h {m}m", show_alert=True)
        await db.add_balance(uid, DAILY_BONUS)
        await db.set_last_bonus(uid)
        await callback.answer(f"✅ Recibiste {DAILY_BONUS} {MONEDA} de regalo", show_alert=True)

    @app.on_callback_query(filters.regex("^cb_compartir$"))
    async def compartir(client, callback):
        await callback.message.edit_text(f"""🔗 Comparte tu tienda con todos:
👉 {ENLACE_TU_TIENDA or f'https://t.me/{client.me.username}'}""",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="cb_start")]]))

    # ------------------ ADMINISTRADOR ------------------
    @app.on_callback_query(filters.regex("^admin_sincronizar$"))
    async def sincronizar_admin(client, callback):
        await callback.answer("⏳ Actualizando servicios...", show_alert=True)
        cat, serv, act = await sincronizar_servicios_bd()
        await db.guardar_fecha_sincronizacion(
            datetime.now().strftime("%d/%m/%Y %H:%M"),
            (datetime.now()+timedelta(seconds=INTERVALO_SINCRONIZACION)).strftime("%d/%m/%Y %H:%M")
        )
        await callback.message.reply(f"""✅ SINCRONIZACIÓN LISTA
🗂️ Nuevas categorías: {cat}
➕ Servicios nuevos: {serv}
🔄 Actualizados: {act}""")

    @app.on_callback_query(filters.regex("^admin_proxima_sinc$"))
    async def proxima_sinc(client, callback):
        conf = await db.configuracion.find_one({"_id": "global"})
        proxima = conf.get("proxima_sincronizacion", "Pendiente")
        ultima = conf.get("ultima_sincronizacion", "Nunca")
        await callback.answer(f"⏱️ Última: {ultima}\n🔜 Próxima: {proxima}", show_alert=True)

    @app.on_callback_query(filters.regex("^admin_limpiar$"))
    async def limpiar_pedidos_admin(client, callback):
        from config import DIAS_ELIMINAR_PEDIDOS
        eliminados = await db.limpiar_pedidos_antiguos(DIAS_ELIMINAR_PEDIDOS)
        await callback.answer(f"🧹 Eliminados: {eliminados} pedidos antiguos", show_alert=True)

    @app.on_callback_query(filters.regex("^broadcast$"))
    async def iniciar_difusion(client, callback):
        broadcast_state[OWNER_ID] = True
        await callback.message.reply("📢 Ahora envíame el mensaje o archivo que quieras enviar a todos.")

    @app.on_message(filters.user(OWNER_ID) & filters.private)
    async def procesar_difusion(client, message):
        if not broadcast_state.get(OWNER_ID): return
        broadcast_state.pop(OWNER_ID)
        enviados = fallidos = 0
        async for usuario in db.users.find({}):
            try:
                if message.text: await client.send_message(usuario["_id"], message.text)
                elif message.photo: await client.send_photo(usuario["_id"], message.photo.file_id, caption=message.caption or "")
                enviados +=1
            except: fallidos +=1
        await message.reply(f"📢 Difusión terminada:\n✅ {enviados} enviados\n❌ {fallidos} fallidos")

    print("✅ Módulo de Inicio cargado correctamente")
