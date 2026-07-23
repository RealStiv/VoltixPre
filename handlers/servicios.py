# ============================================================
# Smm Panel Bot - Servicios y Pedidos
# Author: learningbots79 (https://github.com/learningbots79) 
# ============================================================

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
import aiohttp
import re
import db
from config import SMM_API_URL, SMM_API_KEY, SMM_API_URL_SECUNDARIO, SMM_API_KEY_SECUNDARIO, ORDER_CHANNEL, OWNER_ID

# Almacén temporal de pedidos en curso
pedido_en_curso = {}

# ------------------- FUNCIONES AUXILIARES -------------------
def extraer_texto(mensaje):
    if mensaje.text: return mensaje.text.strip()
    if mensaje.caption: return mensaje.caption.strip()
    if mensaje.entities:
        for e in mensaje.entities:
            if e.type == "text_link" and e.url: return e.url.strip()
    return ""

def es_enlace_valido(texto):
    patron = re.compile(r"(https?://[^\s]+)")
    return bool(patron.search(texto))

async def obtener_config_actual():
    return await db.obtener_config()

# ------------------- SINCRONIZACIÓN AUTOMÁTICA -------------------
async def sincronizar_desde_proveedor():
    config = await obtener_config_actual()
    resultados = {"categorias_nuevas":0, "servicios_nuevos":0, "actualizados":0, "errores":0}
    proveedores = [(SMM_API_URL, SMM_API_KEY)]
    if SMM_API_URL_SECUNDARIO and SMM_API_KEY_SECUNDARIO:
        proveedores.append((SMM_API_URL_SECUNDARIO, SMM_API_KEY_SECUNDARIO))

    for url, clave in proveedores:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
                async with s.post(url, data={"key": clave, "action": "services"}) as r:
                    datos = await r.json()
                    if not isinstance(datos, list): continue

                    for item in datos:
                        cat_nombre = str(item.get("category", "Sin Categoría")).strip().title()
                        id_ext = str(item.get("service"))
                        nombre = str(item.get("name", "Sin Nombre")).strip()
                        costo = float(str(item.get("rate", 0)).replace(",", "."))
                        margen = float(config.get("margen_global", 100)) / 100
                        precio_final = round(costo * (1 + margen), 4)

                        cat_creada = await db.guardar_categoria(cat_nombre)
                        if cat_creada: resultados["categorias_nuevas"] += 1

                        datos_servicio = {
                            "codigo": f"SVC-{id_ext}",
                            "nombre": nombre,
                            "id_proveedor": int(id_ext),
                            "categoria": cat_nombre,
                            "costo_1000": costo,
                            "precio_1000": precio_final,
                            "estado": "Activo",
                            "destacado": False,
                            "minimo": int(item.get("min", 10)),
                            "maximo": int(item.get("max", 100000)),
                            "ultima_actualizacion": datetime.now().strftime("%d/%m/%Y %H:%M")
                        }

                        res = await db.guardar_o_actualizar_servicio(datos_servicio)
                        if res == "nuevo": resultados["servicios_nuevos"] +=1
                        elif res == "actualizado": resultados["actualizados"] +=1
                    break
        except Exception as e:
            resultados["errores"] +=1
            print(f"Error sincronizando: {e}")
    return resultados

async def actualizar_estados_pedidos():
    config = await obtener_config_actual()
    pendientes = await db.obtener_pedidos_actualizar()
    if not pendientes: return 0
    actualizados = 0
    for ped in pendientes:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(SMM_API_URL, data={"key":SMM_API_KEY, "action":"status", "order": ped["id_api"]}) as r:
                    estado_api = await r.json()
                    nuevo_estado = estado_api.get("status", ped["estado"])
                    await db.actualizar_estado_pedido(ped["_id"], nuevo_estado)
                    actualizados +=1
        except: continue
    return actualizados

# ------------------- FLUJO DE USUARIO -------------------
async def verificar_espera_pedido(uid):
    config = await obtener_config_actual()
    horas = float(config.get("tiempo_espera_pedido", 2))
    ultimo = await db.fecha_ultimo_pedido(uid)
    if not ultimo: return False
    limite = ultimo + timedelta(hours=horas)
    return datetime.now() < limite

def servicios_botones(lista):
    filas = []
    for s in lista:
        filas.append([InlineKeyboardButton(
            f"{s['nombre']} | {s['precio_1000']:.2f}",
            callback_data=f"sel_svc_{s['codigo']}"
        )])
    return filas

def register_servicios_handlers(app: Client):

    @app.on_callback_query(filters.regex("^ver_categorias$"))
    async def listar_categorias(client, callback):
        cats = await db.listar_categorias_activas()
        botones = []
        for c in cats:
            botones.append([InlineKeyboardButton(c, callback_data=f"cat_{c}")])
        botones.append([InlineKeyboardButton("🔙 Menú Principal", callback_data="volver_inicio")])
        await callback.message.edit_text("📂 Elige la categoría:", reply_markup=InlineKeyboardMarkup(botones))

    @app.on_callback_query(filters.regex(r"^cat_.+"))
    async def listar_servicios_categoria(client, callback):
        nombre = callback.data.replace("cat_","",1)
        lista = await db.servicios_por_categoria(nombre)
        config = await obtener_config_actual()
        moneda = config.get("moneda","USD")
        texto = f"📦 **{nombre}**\nPrecio cada 1000 unidades en {moneda}:"
        botones = servicios_botones(lista)
        botones.append([InlineKeyboardButton("🔙 Volver", callback_data="ver_categorias")])
        await callback.message.edit_text(texto, reply_markup=InlineKeyboardMarkup(botones))

    @app.on_callback_query(filters.regex(r"^sel_svc_.+"))
    async def iniciar_pedido(client, callback):
        if await verificar_espera_pedido(callback.from_user.id):
            return await callback.answer("⏳ Debes esperar después de tu último pedido", show_alert=True)
        config = await obtener_config_actual()
        codigo = callback.data.replace("sel_svc_","",1)
        svc = await db.obtener_servicio(codigo)
        pedido_en_curso[callback.from_user.id] = {
            "codigo": codigo,
            "nombre": svc["nombre"],
            "id_api": svc["id_proveedor"],
            "precio": svc["precio_1000"],
            "min": svc["minimo"],
            "max": svc["maximo"],
            "paso": "enlace"
        }
        await callback.message.edit_text(
            f"📦 **{svc['nombre']}**\nMin: {svc['minimo']} | Máx: {svc['maximo']}\n💵 Precio: {svc['precio_1000']:.2f} {config.get('moneda','USD')}/1k\n\n🔗 Envía el enlace:"
        )

    @app.on_callback_query(filters.regex("^buscar_servicio$"))
    async def pedir_busqueda(client, callback):
        pedido_en_curso[callback.from_user.id] = {"paso": "buscando"}
        await callback.message.edit_text("🔎 Escribe una palabra del servicio que buscas:")

    @app.on_message(filters.private & ~filters.command("start"))
    async def procesar_pasos(client, message):
        uid = message.from_user.id
        if uid not in pedido_en_curso: return
        datos = pedido_en_curso[uid]
        config = await obtener_config_actual()

        if datos["paso"] == "buscando":
            coincidencias = await db.buscar_servicios(message.text.strip())
            if not coincidencias:
                await message.reply("❌ No se encontraron resultados.")
            else:
                botones = servicios_botones(coincidencias)
                botones.append([InlineKeyboardButton("🔙 Atrás", callback_data="volver_inicio")])
                await message.reply("✅ Resultados:", reply_markup=InlineKeyboardMarkup(botones))
            del pedido_en_curso[uid]

        elif datos["paso"] == "enlace":
            link = extraer_texto(message)
            if not link or not es_enlace_valido(link):
                return await message.reply("❌ Enlace no válido, intenta nuevamente:")
            datos["enlace"] = link
            datos["paso"] = "cantidad"
            await message.reply(f"🔢 Cantidad entre {datos['min']} y {datos['max']}:")

        elif datos["paso"] == "cantidad":
            if not message.text.isdigit():
                return await message.reply("❌ Solo números:")
            cant = int(message.text)
            if not (datos["min"] <= cant <= datos["max"]):
                return await message.reply(f"❌ Rango inválido: entre {datos['min']} y {datos['max']}")
            total = round((cant / 1000) * datos["precio"], 4)
            saldo = await db.obtener_saldo(uid)
            datos.update({"cantidad": cant, "total": total})
            await message.reply(
                f"""🧾 CONFIRMACIÓN
📦 {datos['nombre']}
🔗 {datos['enlace']}
🔢 Cantidad: {cant}
💰 Total: {total:.2f} {config.get('moneda','USD')}""",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Confirmar", callback_data="fin_pedido")],
                    [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_pedido")]
                ])
            )

    @app.on_callback_query(filters.regex("^fin_pedido$"))
    async def enviar_pedido(client, callback):
        uid = callback.from_user.id
        datos = pedido_en_curso.get(uid)
        if not datos: return await callback.answer("Sesión expirada", show_alert=True)

        saldo = await db.obtener_saldo(uid)
        if saldo < datos["total"]:
            return await callback.answer("❌ Saldo insuficiente", show_alert=True)

        await db.sumar_saldo(uid, -datos["total"], "Pago de pedido")
        id_api = 0
        error_api = ""
        for url, key in [(SMM_API_URL, SMM_API_KEY), (SMM_API_URL_SECUNDARIO, SMM_API_KEY_SECUNDARIO)]:
            if not url: continue
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.post(url, data={
                        "key":key, "action":"add", "service":datos["id_api"],
                        "link":datos["enlace"], "quantity":datos["cantidad"]
                    }) as r:
                        res = await r.json()
                        if "order" in res:
                            id_api = res["order"]
                            break
                        elif "error" in res: error_api = res["error"]
            except Exception as e: error_api = str(e)

        await db.crear_pedido({
            "user_id": uid, "codigo_servicio": datos["codigo"], "nombre_servicio": datos["nombre"],
            "enlace": datos["enlace"], "cantidad": datos["cantidad"], "monto": datos["total"],
            "id_api": id_api, "estado": "Procesando", "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
        })

        if ORDER_CHANNEL:
            try: await client.send_message(ORDER_CHANNEL, f"📦 NUEVO PEDIDO\n👤 {uid}\n📦 {datos['nombre']}\n💰 {datos['total']}")
            except: pass

        texto = "✅ Pedido enviado correctamente" if id_api else f"⚠️ Guardado, proveedor: {error_api}"
        await callback.message.edit_text(texto)
        del pedido_en_curso[uid]

    @app.on_callback_query(filters.regex("^cancelar_pedido$"))
    async def cancelar(client, callback):
        if callback.from_user.id in pedido_en_curso:
            del pedido_en_curso[callback.from_user.id]
        await callback.message.edit_text("❌ Operación cancelada")

    @app.on_callback_query(filters.regex("^mis_pedidos$"))
    async def listar_mios(client, callback):
        lista = await db.pedidos_de_usuario(callback.from_user.id)
        if not lista: return await callback.answer("No tienes pedidos aún", show_alert=True)
        texto = "📦 Tus últimos pedidos:\n"
        for p in lista[:8]:
            texto += f"- {p['nombre_servicio']} | {p['estado']} | {p['fecha']}\n"
        await callback.answer(texto, show_alert=True)

    @app.on_callback_query(filters.regex("^sincronizar_ahora$") & filters.user(OWNER_ID))
    async def sinc_manual(client, callback):
        await callback.answer("⏳ Actualizando todo...", show_alert=True)
        res = await sincronizar_desde_proveedor()
        await callback.message.reply(f"""✅ SINCRONIZACIÓN
🗂️ Categorías nuevas: {res['categorias_nuevas']}
📦 Servicios nuevos: {res['servicios_nuevos']}
🔄 Actualizados: {res['actualizados']}
⚠️ Errores: {res['errores']}""")

    print("✅ Módulo de Servicios cargado")
