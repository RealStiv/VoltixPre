# ============================================================
# Smm Panel Bot - Módulo Inicio
# Author: learningbots79 (https://github.com/learningbots79) 
# ============================================================

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait, RPCError, PeerIdInvalid
from datetime import datetime, timedelta
import asyncio
import db
from config import OWNER_ID, FORCE_CHANNEL, QR_IMAGE, REFERRER_BONUS, DAILY_BONUS

CANAL = FORCE_CHANNEL.replace("@", "")

async def verificar_suscripcion(client: Client, user_id: int) -> bool | str:
    try:
        estado = await client.get_chat_member(FORCE_CHANNEL, user_id)
        return estado.status not in ["left", "kicked"]
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await verificar_suscripcion(client, user_id)
    except (PeerIdInvalid, RPCError):
        return False

async def enviar_aviso_usuario(client: Client, user_id: int, texto: str):
    try:
        await client.send_message(user_id, texto)
    except: pass

async def menu_principal(usuario):
    config = await db.obtener_config()
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Ver Servicios", callback_data="ver_categorias"),
         InlineKeyboardButton("🔎 Buscar Servicio", callback_data="buscar_servicio")],
        [InlineKeyboardButton("💰 Mi Saldo", callback_data="ver_saldo"),
         InlineKeyboardButton("💳 Recargar", callback_data="ir_recargar")],
        [InlineKeyboardButton("📦 Mis Pedidos", callback_data="mis_pedidos"),
         InlineKeyboardButton("👤 Mi Perfil", callback_data="mi_perfil")],
        [InlineKeyboardButton("🎟 Código Promoción", callback_data="usar_codigo"),
         InlineKeyboardButton("🎉 Bono Diario", callback_data="pedir_bono")],
        [InlineKeyboardButton("🗣 Invitar Amigos", callback_data="ver_referidos"),
         InlineKeyboardButton("🆘 Soporte", url=f"https://t.me/{config.get('admin_contacto', '')}")]
    ])

async def menu_administrador():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Configuración General", callback_data="menu_config")],
        [InlineKeyboardButton("🔄 Sincronizar Servicios", callback_data="sincronizar_ahora"),
         InlineKeyboardButton("📊 Ver Reportes", callback_data="ver_reportes")],
        [InlineKeyboardButton("🎟 Códigos Promocionales", callback_data="menu_codigos"),
         InlineKeyboardButton("🏅 Niveles de Usuarios", callback_data="menu_niveles")],
        [InlineKeyboardButton("💳 Ver Recargas", callback_data="lista_recargas_pendientes"),
         InlineKeyboardButton("👥 Administrar Usuarios", callback_data="admin_usuarios")],
        [InlineKeyboardButton("📢 Avisos Programados", callback_data="menu_anuncios"),
         InlineKeyboardButton("🔧 Modo Mantenimiento", callback_data="cambiar_mantenimiento")],
        [InlineKeyboardButton("💾 Respaldos", callback_data="menu_respaldos"),
         InlineKeyboardButton("📜 Historial de Acciones", callback_data="ver_auditoria")]
    ])

def register_inicio_handlers(app: Client):

    @app.on_message(filters.command("start") & filters.private)
    async def comando_inicio(client, message):
        usuario = message.from_user
        ref = message.text.split()
        ref_id = int(ref[1]) if len(ref) == 2 and ref[1].isdigit() else None

        suscrito = await verificar_suscripcion(client, usuario.id)
        if suscrito != True:
            return await message.reply(
                "🚫 Debes unirte al canal oficial para usar el bot",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔔 Unirme al Canal", url=f"https://t.me/{CANAL}")],
                    [InlineKeyboardButton("✅ Ya estoy dentro", callback_data="volver_inicio")]
                ])
            )

        es_nuevo = not await db.existe_usuario(usuario.id)
        await db.crear_usuario(usuario.id, usuario.first_name, ref_id if es_nuevo else None)

        if ref_id and ref_id != usuario.id and es_nuevo:
            await db.sumar_saldo(ref_id, REFERRER_BONUS, "Bono por referido")
            await enviar_aviso_usuario(client, ref_id, f"""🎉 ¡Nuevo referido registrado!
💰 Recibiste +{REFERRER_BONUS} de saldo""")

        mensaje = f"""👋 Hola {usuario.first_name}!
Bienvenido a tu tienda de servicios profesional 🚀"""

        if usuario.id == OWNER_ID:
            await message.reply(mensaje, reply_markup=await menu_administrador())
        else:
            await message.reply_photo(QR_IMAGE, caption=mensaje, reply_markup=await menu_principal(usuario))

    @app.on_callback_query(filters.regex("^volver_inicio$"))
    async def cb_inicio(client, callback):
        if not await verificar_suscripcion(client, callback.from_user.id):
            return await callback.answer("Únete primero al canal", show_alert=True)
        usuario = callback.from_user
        if usuario.id == OWNER_ID:
            await callback.message.edit_text("👋 Panel de Administrador", reply_markup=await menu_administrador())
        else:
            await callback.message.delete()
            await callback.message.reply_photo(QR_IMAGE, caption=f"👋 Hola {usuario.first_name}", reply_markup=await menu_principal(usuario))

    @app.on_callback_query(filters.regex("^ver_saldo$"))
    async def cb_saldo(client, callback):
        saldo = await db.obtener_saldo(callback.from_user.id)
        config = await db.obtener_config()
        await callback.answer(f"💰 Tu saldo: {saldo:.2f} {config.get('moneda', 'USD')}", show_alert=True)

    @app.on_callback_query(filters.regex("^pedir_bono$"))
    async def cb_bono(client, callback):
        uid = callback.from_user.id
        ultimo = await db.ultimo_bono(uid)
        proximo = ultimo + timedelta(hours=24) if ultimo else None
        if proximo and datetime.now() < proximo:
            falta = proximo - datetime.now()
            return await callback.answer(f"⏳ Vuelve en {falta.seconds//3600}h {(falta.seconds%3600)//60}m", show_alert=True)
        await db.sumar_saldo(uid, DAILY_BONUS, "Bono diario")
        await db.guardar_hora_bono(uid)
        await callback.answer(f"✅ Recibiste +{DAILY_BONUS} de saldo", show_alert=True)

    print("✅ Módulo de Inicio cargado")
