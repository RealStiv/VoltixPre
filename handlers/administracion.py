# ============================================================
# Smm Panel Bot - Seguridad, Reportes y Respaldos
# Author: learningbots79 (https://github.com/learningbots79) 
# ============================================================

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
import io
import db
from config import OWNER_ID

estado_admin = {}

# ================ SEGURIDAD Y MANTENIMIENTO ================
async def cambiar_mantenimiento(_, callback):
    config = await db.obtener_config()
    actual = config.get("modo_mantenimiento", False)
    nuevo = not actual
    await db.actualizar_configuracion("modo_mantenimiento", nuevo)
    texto = f"🔧 Modo mantenimiento: {'ACTIVADO' if nuevo else 'DESACTIVADO'}"
    await callback.answer(texto, show_alert=True)
    await callback.message.edit_text(texto, reply_markup=await menu_administracion())

async def menu_administracion():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Bloquear Usuario", callback_data="pedir_bloquear"),
         InlineKeyboardButton("✅ Desbloquear", callback_data="pedir_desbloquear")],
        [InlineKeyboardButton("💰 Modificar Saldo", callback_data="modificar_saldo"),
         InlineKeyboardButton("📜 Historial Acciones", callback_data="ver_auditoria_completa")],
        [InlineKeyboardButton("🔙 Volver", callback_data="volver_admin")]
    ])

# ================ REPORTES Y ESTADÍSTICAS ================
async def generar_reporte(periodo="total"):
    config = await db.obtener_config()
    moneda = config.get("moneda", "USD")

    if periodo == "dia":
        desde = datetime.now().replace(hour=0, minute=0, second=0)
        nombre = "HOY"
    elif periodo == "mes":
        desde = datetime.now().replace(day=1, hour=0, minute=0, second=0)
        nombre = "ESTE MES"
    else:
        desde = datetime(2020,1,1)
        nombre = "TOTAL"

    datos = await db.obtener_datos_reporte(desde)

    return f"""📊 **REPORTE {nombre}**
👥 Usuarios totales: {datos['usuarios']}
🛒 Pedidos realizados: {datos['pedidos']}
💸 Ventas totales: {datos['ingresos']:.2f} {moneda}
💳 Recargas aprobadas: {datos['recargas']:.2f} {moneda}
📈 Ganancia estimada: {datos['ganancia']:.2f} {moneda}"""

# ================ RESPALDOS AUTOMÁTICOS ================
async def crear_respaldo_completo():
    colecciones = ["usuarios", "configuracion", "categorias", "servicios",
                   "pedidos", "recargas", "codigos_promo", "niveles", "auditoria"]
    contenido = f"RESPALDO BOT - {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"

    for col in colecciones:
        documentos = await db.obtener_todo_coleccion(col)
        contenido += f"===== {col.upper()} =====\n"
        for doc in documentos:
            contenido += f"{str(doc)}\n"
        contenido += "\n"

    archivo = io.BytesIO(contenido.encode("utf-8"))
    archivo.name = f"respaldo_{datetime.now().strftime('%d%m%Y_%H%M')}.txt"
    return archivo

def register_administracion_handlers(app: Client):

    # ---- Menús principales ----
    @app.on_callback_query(filters.regex("^ver_reportes$") & filters.user(OWNER_ID))
    async def menu_reportes(_, callback):
        botones = InlineKeyboardMarkup([
            [InlineKeyboardButton("📆 Hoy", callback_data="rep_dia"),
             InlineKeyboardButton("📅 Este Mes", callback_data="rep_mes")],
            [InlineKeyboardButton("📊 Total General", callback_data="rep_total")],
            [InlineKeyboardButton("🔙 Volver", callback_data="volver_admin")]
        ])
        await callback.message.edit_text("📊 Elige el período:", reply_markup=botones)

    @app.on_callback_query(filters.regex(r"^rep_(dia|mes|total)$") & filters.user(OWNER_ID))
    async def mostrar_reporte(_, callback):
        tipo = callback.data.replace("rep_","")
        texto = await generar_reporte(tipo)
        await callback.message.edit_text(texto, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Atrás", callback_data="ver_reportes")]
        ]))

    @app.on_callback_query(filters.regex("^modo_mantenimiento$") & filters.user(OWNER_ID))
    async def _mante(c,q): await cambiar_mantenimiento(c,q)

    @app.on_callback_query(filters.regex("^admin_usuarios$") & filters.user(OWNER_ID))
    async def _menuu(c,q): await q.message.edit_text("⚙️ Gestión de usuarios", reply_markup=await menu_administracion())

    # ---- Respaldos ----
    @app.on_callback_query(filters.regex("^menu_respaldos$") & filters.user(OWNER_ID))
    async def menu_respaldos(_, callback):
        botones = InlineKeyboardMarkup([
            [InlineKeyboardButton("💾 Hacer Respaldo Ahora", callback_data="generar_respaldo")],
            [InlineKeyboardButton("🔙 Volver", callback_data="volver_admin")]
        ])
        await callback.message.edit_text("💾 Respaldos de toda la base de datos", reply_markup=botones)

    @app.on_callback_query(filters.regex("^generar_respaldo$") & filters.user(OWNER_ID))
    async def enviar_respaldo(client, callback):
        await callback.answer("⏳ Generando respaldo...", show_alert=True)
        archivo = await crear_respaldo_completo()
        await client.send_document(OWNER_ID, archivo, caption="✅ Respaldo completo generado")
        await callback.message.delete()

    # ---- Acciones de usuario y procesador ----
    @app.on_callback_query(filters.regex(r"^(pedir_bloquear|pedir_desbloquear|modificar_saldo)$") & filters.user(OWNER_ID))
    async def iniciar_proceso(_, callback):
        accion = callback.data
        estado_admin[callback.from_user.id] = {"paso": accion, "etapa": "id"}
        await callback.message.edit_text("✏️ Escribe el ID del usuario:")

    @app.on_callback_query(filters.regex("^ver_auditoria_completa$") & filters.user(OWNER_ID))
    async def ver_logs(_, callback):
        registros = await db.obtener_ultimas_acciones(15)
        texto = "📜 Últimas acciones:\n"
        for r in registros:
            texto += f"[{r['fecha']}] {r['accion']} - {r['detalle']}\n"
        await callback.message.edit_text(texto, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Volver", callback_data="admin_usuarios")]
        ]))

    @app.on_callback_query(filters.regex("^volver_admin$") & filters.user(OWNER_ID))
    async def volver_menu_admin(_, callback):
        await callback.message.edit_text("👋 Panel de Administrador", reply_markup=await menu_administrador())

    @app.on_message(filters.private & ~filters.command("start") & filters.user(OWNER_ID))
    async def procesar_acciones_admin(client, message):
        uid = message.from_user.id
        if uid not in estado_admin: return
        datos = estado_admin[uid]
        texto = message.text.strip()

        if datos["etapa"] == "id":
            if not texto.isdigit():
                await message.reply("❌ Solo números de ID:")
                return
            datos["usuario_objetivo"] = int(texto)
            if datos["paso"] == "pedir_bloquear":
                datos["etapa"] = "motivo"
                await message.reply("✏️ Escribe el motivo del bloqueo:")
            elif datos["paso"] == "modificar_saldo":
                datos["etapa"] = "cantidad"
                await message.reply("✏️ Monto: +50 para agregar, -20 para quitar:")
            else:
                await db.cambiar_estado_bloqueo(int(texto), False)
                await message.reply("✅ Usuario desbloqueado")
                del estado_admin[uid]

        elif datos["etapa"] == "motivo":
            await db.cambiar_estado_bloqueo(datos["usuario_objetivo"], True, texto)
            await message.reply("✅ Usuario bloqueado")
            del estado_admin[uid]

        elif datos["etapa"] == "cantidad":
            if not texto.replace(".","",1).replace("-","",1).isdigit():
                await message.reply("❌ Monto inválido:")
                return
            monto = float(texto)
            await db.sumar_saldo(datos["usuario_objetivo"], monto, "Ajuste manual administrador")
            await message.reply(f"✅ Saldo modificado en: {monto}")
            del estado_admin[uid]

    print("✅ Módulo Administración y Seguridad cargado")
