# ============================================================
# Smm Panel Bot
# Author: learningbots79 (https://github.com/learningbots79) 
# Support: https://t.me/LearningBotsCommunity
# Channel: https://t.me/learning_bots
# YouTube: https://youtube.com/@learning_bots
# License: Open-source (keep credits, no resale)
# ============================================================

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
import aiohttp
from config import SMM_SITE, ORDER_CHANNEL, MARGEN_GLOBAL, MONEDA, PALABRAS_PROHIBIDAS, TIEMPO_ESPERA_PEDIDO
from db import create_order, users, listar_categorias, listar_servicios, sumar_vista_servicio, estado_pedido_usuario, check_balance, actualizar_gasto_usuario, log_accion
from datetime import datetime

# ============================================================
# Almacenamiento temporal
# ============================================================
def init_temp(app: Client):
    if not hasattr(app, "order_temp"):
        app.order_temp = {}

# ============================================================
# Función auxiliar extraer texto
# ============================================================
def _extract_message_text(message: Message) -> str:
    if getattr(message, "text", None):
        return message.text.strip()
    if getattr(message, "caption", None):
        return message.caption.strip()
    if message.entities:
        for ent in message.entities:
            if getattr(ent, "type", "") == "text_link" and getattr(ent, "url", None):
                return ent.url.strip()
    return ""

def tiene_prohibido(texto: str) -> bool:
    minus = texto.lower()
    return any(p in minus for p in PALABRAS_PROHIBIDAS)

def calcular_precio_final(costo: float) -> tuple[float, float]:
    ganancia = costo * (MARGEN_GLOBAL / 100)
    return round(costo + ganancia, 4), round(ganancia, 4)

# ============================================================
# Traer servicios desde API
# ============================================================
async def fetch_all_services():
    payload = {"key": SMM_SITE["api_key"], "action": "services"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(SMM_SITE["api_url"], data=payload, timeout=aiohttp.ClientTimeout(total=25)) as resp:
                data = await resp.json()
                if isinstance(data, list):
                    return data
                return []
    except Exception as e:
        print("❌ Error al obtener servicios:", e)
        return []

# ============================================================
# Mostrar categorías
# ============================================================
async def cb_services(client: Client, callback: CallbackQuery):
    text = f"🛒 **CATÁLOGO DE SERVICIOS**\nElige una categoría:"
    categorias = await listar_categorias()
    btns = []
    for cat in categorias:
        nombre = cat.get("nombre", "Sin nombre")
        btns.append([InlineKeyboardButton(nombre, callback_data=f"cat_{nombre}")])
    btns.append([InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu_principal")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns))
    await callback.answer()

# ============================================================
# Mostrar servicios por categoría
# ============================================================
async def cb_ver_categoria(client: Client, callback: CallbackQuery):
    cat_nombre = callback.data.replace("cat_", "", 1)
    servicios = await listar_servicios({"categoria": cat_nombre, "estado": "Activo"})
    if not servicios:
        await callback.answer("❌ No hay servicios disponibles en esta categoría", show_alert=True)
        return await cb_services(client, callback)

    text = f"📂 **{cat_nombre}**\nElige el servicio:"
    btns = []
    for s in servicios:
        codigo = s.get("codigo")
        nombre = s.get("nombre", "Servicio")
        precio = s.get("precio_1000", 0)
        btns.append([InlineKeyboardButton(f"{nombre} | {precio:.4f} {MONEDA}/1k", callback_data=f"serv_{codigo}")])
    btns.append([InlineKeyboardButton("🔙 Ver Categorías", callback_data="cb_services")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns))
    await callback.answer()

# ============================================================
# Seleccionar servicio
# ============================================================
async def cb_seleccionar_servicio(client: Client, callback: CallbackQuery):
    codigo = callback.data.replace("serv_", "", 1)
    servicios = await listar_servicios({"codigo": codigo})
    if not servicios:
        await callback.answer("❌ Servicio no encontrado", show_alert=True)
        return await cb_services(client, callback)

    serv = servicios[0]
    await sumar_vista_servicio(codigo)
    minimo = serv.get("minimo", 10)
    maximo = serv.get("maximo", 10000)
    costo = serv.get("costo_1000", 0)
    precio, ganancia = calcular_precio_final(costo)

    client.order_temp[callback.from_user.id] = {
        "codigo": codigo,
        "nombre_serv": serv.get("nombre"),
        "id_api": serv.get("id_proveedor"),
        "costo": costo,
        "precio_unitario": precio,
        "ganancia": ganancia,
        "minimo": minimo,
        "maximo": maximo,
        "step": "link"
    }

    texto = f"""📦 **{serv.get('nombre')}**
💵 Precio: {precio:.4f} {MONEDA} / cada 1000
📊 Cantidad mínima: {minimo}
📊 Cantidad máxima: {maximo}

📎 Envía el enlace donde aplicar el servicio:"""
    await callback.message.edit_text(texto)
    await callback.answer()

# ============================================================
# Proceso de pedido paso a paso
# ============================================================
async def handle_order_steps(client: Client, message: Message):
    init_temp(client)
    uid = message.from_user.id
    if uid not in client.order_temp:
        return

    pedido = client.order_temp[uid]
    paso = pedido.get("step")
    texto = _extract_message_text(message)

    # Verificar si tiene pedido pendiente
    usuario = await users.find_one({"_id": uid})
    if usuario and usuario.get("tiene_pedido_pendiente"):
        return await message.reply(f"⏳ Debes esperar {TIEMPO_ESPERA_PEDIDO} horas o hasta que se confirme tu último pedido.")

    if paso == "link":
        if not texto or tiene_prohibido(texto):
            return await message.reply("❌ Enlace no válido o contiene palabras prohibidas. Intenta nuevamente:")
        pedido["link"] = texto
        pedido["step"] = "cantidad"
        return await message.reply(f"🔢 Ingresa la cantidad (entre {pedido['minimo']} y {pedido['maximo']}):")

    if paso == "cantidad":
        if not texto.isdigit():
            return await message.reply("❌ Escribe solo números:")
        cantidad = int(texto)
        if not (pedido["minimo"] <= cantidad <= pedido["maximo"]):
            return await message.reply(f"❌ La cantidad debe ser entre {pedido['minimo']} y {pedido['maximo']}:")
        pedido["cantidad"] = cantidad
        total = (cantidad / 1000) * pedido["precio_unitario"]
        pedido["total"] = round(total, 4)
        pedido["step"] = "confirmar"

        return await message.reply(
            f"""🧾 **CONFIRMACIÓN DE PEDIDO**

📦 Servicio: {pedido['nombre_serv']}
🔗 Enlace: {pedido['link']}
🔢 Cantidad: {cantidad}
💵 Total: {pedido['total']} {MONEDA}

¿Todo correcto?""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirmar", callback_data="conf_pedido")],
                [InlineKeyboardButton("❌ Cancelar", callback_data="canc_pedido")]
            ])
        )

# ============================================================
# Confirmar pedido
# ============================================================
async def cb_confirmar_pedido(client: Client, callback: CallbackQuery):
    uid = callback.from_user.id
    if uid not in client.order_temp:
        return await callback.answer("❌ Sesión expirada", show_alert=True)

    pedido = client.order_temp[uid]
    saldo = await check_balance(uid)

    if saldo < pedido["total"]:
        return await callback.answer(
            f"❌ Saldo insuficiente\nFaltan: {round(pedido['total'] - saldo, 4)} {MONEDA}",
            show_alert=True
        )

    # Descontar saldo
    await users.update_one({"_id": uid}, {"$inc": {"balance": -pedido["total"]}})
    await estado_pedido_usuario(uid, True)

    # Enviar a proveedor
    respuesta_api = {"order": None, "error": None}
    for url, key in [(SMM_SITE["api_url"], SMM_SITE["api_key"]), (SMM_SITE["api_url_secundario"], SMM_SITE["api_key_secundario"])]:
        if not url or not key:
            continue
        try:
            payload = {
                "key": key, "action": "add",
                "service": pedido["id_api"],
                "link": pedido["link"],
                "quantity": pedido["cantidad"]
            }
            async with aiohttp.ClientSession() as s:
                async with s.post(url, data=payload) as r:
                    res = await r.json()
                    if "order" in res:
                        respuesta_api["order"] = res["order"]
                        break
                    elif "error" in res:
                        respuesta_api["error"] = res["error"]
        except Exception as e:
            respuesta_api["error"] = str(e)

    # Guardar en base
    nuevo = await create_order(
        user_id=uid,
        service_id=pedido["codigo"],
        link=pedido["link"],
        quantity=pedido["cantidad"],
        amount=pedido["total"],
        costo=pedido["costo"],
        ganancia=pedido["ganancia"],
        api_order_id=respuesta_api.get("order")
    )

    await actualizar_gasto_usuario(uid, pedido["total"])
    await log_accion("Pedido creado", f"Usuario {uid} - {pedido['nombre_serv']}")

    # Avisar a canal
    try:
        await client.send_message(
            ORDER_CHANNEL,
            f"""📦 **NUEVO PEDIDO**
👤 Usuario: {callback.from_user.first_name} | {uid}
📦 Servicio: {pedido['nombre_serv']}
🔗 Enlace: {pedido['link']}
🔢 Cantidad: {pedido['cantidad']}
💵 Total: {pedido['total']} {MONEDA}
🆔 ID Proveedor: {respuesta_api.get('order', 'Falló')}"""
        )
    except:
        pass

    # Mensaje al usuario
    texto_final = "✅ Pedido realizado correctamente"
    if respuesta_api.get("error"):
        texto_final = f"⚠️ Pedido guardado, hubo problema al conectar con el proveedor: {respuesta_api['error']}"

    await callback.message.edit_text(texto_final)
    del client.order_temp[uid]
    await callback.answer()

# ============================================================
# Cancelar pedido
# ============================================================
async def cb_cancelar_pedido(client: Client, callback: CallbackQuery):
    uid = callback.from_user.id
    if uid in client.order_temp:
        del client.order_temp[uid]
    await callback.message.edit_text("❌ Pedido cancelado")
    await callback.answer()

# ============================================================
# Registrar todo
# ============================================================
def register_services_handlers(app: Client):
    init_temp(app)

    @app.on_callback_query(filters.regex("^cb_services$"))
    async def _1(c,q): await cb_services(c,q)

    @app.on_callback_query(filters.regex(r"^cat_.+"))
    async def _2(c,q): await cb_ver_categoria(c,q)

    @app.on_callback_query(filters.regex(r"^serv_.+"))
    async def _3(c,q): await cb_seleccionar_servicio(c,q)

    @app.on_callback_query(filters.regex("^conf_pedido$"))
    async def _4(c,q): await cb_confirmar_pedido(c,q)

    @app.on_callback_query(filters.regex("^canc_pedido$"))
    async def _5(c,q): await cb_cancelar_pedido(c,q)

    @app.on_message(filters.private & ~filters.command("start"))
    async def _pasos(c,m): await handle_order_steps(c,m)

    print("✅ Módulo de Servicios cargado correctamente")
