# ============================================================
# Smm Panel Bot - Recargas Manuales
# Author: learningbots79 (https://github.com/learningbots79) 
# ============================================================

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
from bson.objectid import ObjectId
import db
from config import OWNER_ID

# Estado temporal del proceso de recarga
estado_recarga = {}

async def notificar_admin_solicitud(client: Client, solicitud: dict, datos_usuario: dict):
    config = await db.obtener_config()
    moneda = config.get("moneda", "USD")
    texto = f"""💳 **NUEVA SOLICITUD DE RECARGA**
👤 Usuario: {datos_usuario.get('nombre', 'Sin nombre')}
🆔 ID: {solicitud['user_id']}
🏦 Método: {solicitud['metodo']}
💰 Monto: {solicitud['monto']} {moneda}
📅 Fecha: {solicitud['fecha']}"""

    botones = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Aprobar", callback_data=f"aprob_rec_{solicitud['_id']}")],
        [InlineKeyboardButton("❌ Rechazar", callback_data=f"recha_rec_{solicitud['_id']}")]
    ])

    await client.send_photo(
        chat_id=OWNER_ID,
        photo=solicitud["comprobante_id"],
        caption=texto,
        reply_markup=botones
    )

async def verificar_limite_diario(uid: int, monto: float) -> tuple[bool, float]:
    config = await db.obtener_config()
    limite = float(config.get("recarga_limite_diario", 10000))
    hoy = datetime.now().strftime("%d/%m/%Y")
    total_hoy = await db.total_recargas_hoy(uid, hoy)
    return (total_hoy + monto) <= limite, limite - total_hoy

def register_recargas_handlers(app: Client):

    @app.on_callback_query(filters.regex("^ir_recargar$"))
    async def iniciar_recarga(client, callback):
        uid = callback.from_user.id
        config = await db.obtener_config()
        minimo = float(config.get("recarga_minimo", 50))
        maximo = float(config.get("recarga_maximo", 5000))
        moneda = config.get("moneda", "USD")

        estado_recarga[uid] = {"paso": "monto"}
        await callback.message.edit_text(
            f"""💳 **RECARGA DE SALDO**
💵 Mínimo: {minimo} {moneda}
💵 Máximo: {maximo} {moneda}

✏️ Escribe la cantidad que deseas agregar:"""
        )

    @app.on_callback_query(filters.regex(r"^(aprob|recha)_rec_[\w\d]+$") & filters.user(OWNER_ID))
    async def gestionar_recarga(client, callback):
        accion, _, id_str = callback.data.split("_", 2)
        estado_final = "APROBADO" if accion == "aprob" else "RECHAZADO"
        solicitud = await db.obtener_recarga_por_id(id_str)

        if not solicitud:
            return await callback.answer("❌ Solicitud no encontrada", show_alert=True)

        await db.actualizar_estado_recarga(id_str, estado_final, OWNER_ID)
        config = await db.obtener_config()
        moneda = config.get("moneda", "USD")

        try:
            if estado_final == "APROBADO":
                await db.sumar_saldo(
                    solicitud["user_id"],
                    solicitud["monto"],
                    "Recarga aprobada manualmente"
                )
                await client.send_message(
                    solicitud["user_id"],
                    f"""🎉 **TU RECARGA FUE APROBADA**
💰 Se agregaron: +{solicitud['monto']} {moneda} a tu saldo ✅"""
                )
            else:
                await client.send_message(
                    solicitud["user_id"],
                    f"""⚠️ **TU RECARGA FUE RECHAZADA**
Revisa los datos, el comprobante o intenta con otro método."""
                )
        except Exception as e:
            print(f"No se pudo avisar al usuario: {e}")

        await callback.answer(f"✅ Recarga {estado_final.lower()}", show_alert=True)
        await callback.message.edit_reply_markup(None)

    # Procesamos los pasos que quedan en el manejador general de mensajes
    async def procesar_pasos_recarga(client, message):
        uid = message.from_user.id
        if uid not in estado_recarga:
            return False

        config = await db.obtener_config()
        datos = estado_recarga[uid]
        paso = datos.get("paso")

        if paso == "monto":
            if not message.text.replace(".", "", 1).isdigit():
                await message.reply("❌ Escribe solo un número válido:")
                return True

            monto = float(message.text.strip())
            minimo = float(config.get("recarga_minimo", 50))
            maximo = float(config.get("recarga_maximo", 5000))

            if not (minimo <= monto <= maximo):
                await message.reply(f"❌ El monto debe estar entre {minimo} y {maximo}")
                return True

            permitido, disponible = await verificar_limite_diario(uid, monto)
            if not permitido:
                await message.reply(f"❌ Límite diario superado. Puedes recargar hasta: {disponible}")
                return True

            datos["monto"] = monto
            datos["paso"] = "metodo"

            metodos = config.get("metodos_pago", [])
            botones = []
            for m in metodos:
                botones.append([InlineKeyboardButton(m, callback_data=f"sel_metodo_{m}")])
            await message.reply("🏦 Elige tu método de pago:", reply_markup=InlineKeyboardMarkup(botones))
            return True

        elif paso == "esperando_comprobante":
            if not message.photo:
                await message.reply("📸 Envía aquí la foto clara del comprobante:")
                return True

            archivo = message.photo[-1].file_id
            nueva = await db.crear_solicitud_recarga(
                user_id=uid,
                metodo=datos["metodo"],
                monto=datos["monto"],
                comprobante_id=archivo
            )

            usuario_datos = await db.obtener_usuario(uid)
            await notificar_admin_solicitud(client, nueva, usuario_datos)
            await message.reply("✅ ¡Enviado! Te avisaremos apenas lo revisemos.")
            del estado_recarga[uid]
            return True

        return False

    # Conectamos al flujo principal
    app.add_handler(
        filters.private & ~filters.command("start"),
        procesar_pasos_recarga
    )

    @app.on_callback_query(filters.regex(r"^sel_metodo_.+"))
    async def confirmar_metodo(client, callback):
        uid = callback.from_user.id
        metodo = callback.data.replace("sel_metodo_", "", 1)
        config = await db.obtener_config()
        datos_cuenta = config.get("datos_pago", {}).get(metodo, "")

        estado_recarga[uid]["metodo"] = metodo
        estado_recarga[uid]["paso"] = "esperando_comprobante"

        await callback.message.edit_text(
            f"""🏦 **DATOS PARA PAGAR ({metodo})**
{datos_cuenta}

✅ Ya realizado el pago, envía la foto del comprobante aquí:"""
        )

    @app.on_callback_query(filters.regex("^lista_recargas_pendientes$") & filters.user(OWNER_ID))
    async def ver_pendientes(client, callback):
        lista = await db.listar_recargas({"estado": "PENDIENTE"})
        if not lista:
            return await callback.answer("✅ No hay solicitudes pendientes", show_alert=True)

        texto = "📋 **SOLICITUDES PENDIENTES**\n\n"
        for rec in lista[:10]:
            texto += f"🆔 {rec['_id']} | 👤 {rec['user_id']} | 💰 {rec['monto']}\n"
        await callback.message.edit_text(texto)

    print("✅ Módulo de Recargas cargado")
