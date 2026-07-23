# ============================================================
# Smm Panel Bot
# Author: learningbots79 (https://github.com/learningbots79) 
# Support: https://t.me/LearningBotsCommunity
# Channel: https://t.me/learning_bots
# YouTube: https://youtube.com/@learning_bots
# License: Open-source (keep credits, no resale)
# ============================================================

import logging
import motor.motor_asyncio
from config import MONGO_URI, DB_NAME, MARGEN_GLOBAL
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(asctime)s - %(message)s')

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

# ====================== COLECCIONES ======================
users = db["users"]
orders = db["orders"]
activity = db["activity"]
categories = db["categories"]
services = db["services"]
sorteos = db["sorteos"]
plantillas = db["plantillas"]
registro_cambios = db["registro_cambios"]
configuracion = db["configuracion"]

# ====================== INICIO DE ESTRUCTURA ======================
async def iniciar_estructura_base():
    """Crea los valores iniciales si no existen"""
    conf = await configuracion.find_one({"_id": "global"})
    if not conf:
        await configuracion.insert_one({
            "_id": "global",
            "margen_global": MARGEN_GLOBAL,
            "ultima_sincronizacion": None,
            "proxima_sincronizacion": None,
            "ultimo_respaldo_enviado": None,
            "plantilla_factura": "RECIBO N°{factura}\nFecha: {fecha}\nServicio: {servicio}\nCantidad: {cantidad}\nTotal: {total} {moneda}\nGracias por tu compra.",
            "ultimo_numero_factura": 0
        })

# ====================== FUNCIONES DE REGISTRO ======================
async def log_accion(accion: str, detalle: str, autor: str = "Sistema"):
    await registro_cambios.insert_one({
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "accion": accion,
        "detalle": detalle,
        "realizado_por": autor
    })

async def log_activity(user_id: int, action: str):
    await activity.insert_one({
        "user_id": user_id,
        "action": action,
        "time": datetime.utcnow()
    })

# ====================== USUARIOS ======================
async def user_exists(user_id: int) -> bool:
    return await users.find_one({"_id": user_id}) is not None

async def add_user(user_id: int, name: str, referred_by: int | None = None):
    await users.update_one(
        {"_id": user_id},
        {"$setOnInsert": {
            "_id": user_id,
            "name": name,
            "balance": 0,
            "orders": 0,
            "referred_by": referred_by,
            "refs": 0,
            "last_bonus": None,
            "fecha_registro": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "total_gastado": 0,
            "bloqueado": False,
            "motivo_bloqueo": None,
            "tiene_pedido_pendiente": False
        }},
        upsert=True
    )

async def bloquear_usuario(user_id: int, motivo: str):
    await users.update_one(
        {"_id": user_id},
        {"$set": {"bloqueado": True, "motivo_bloqueo": motivo}}
    )
    await log_accion("Usuario bloqueado", f"ID: {user_id} | Motivo: {motivo}")

async def desbloquear_usuario(user_id: int):
    await users.update_one(
        {"_id": user_id},
        {"$set": {"bloqueado": False, "motivo_bloqueo": None}}
    )
    await log_accion("Usuario desbloqueado", f"ID: {user_id}")

async def add_balance(user_id: int, amount: float):
    await users.update_one(
        {"_id": user_id},
        {"$inc": {"balance": amount}},
        upsert=True
    )

async def check_balance(user_id: int) -> float:
    user = await users.find_one({"_id": user_id})
    return user.get("balance", 0) if user else 0

async def add_ref(user_id: int):
    await users.update_one({"_id": user_id}, {"$inc": {"refs": 1}})

async def get_referrals(user_id: int) -> int:
    user = await users.find_one({"_id": user_id}, {"refs": 1})
    return user.get("refs", 0) if user else 0

async def total_users() -> int:
    return await users.count_documents({})

async def get_last_bonus(user_id: int):
    user = await users.find_one({"_id": user_id}, {"last_bonus": 1})
    return user.get("last_bonus") if user else None

async def set_last_bonus(user_id: int):
    await users.update_one(
        {"_id": user_id},
        {"$set": {"last_bonus": datetime.utcnow()}},
        upsert=True
    )

async def actualizar_gasto_usuario(user_id: int, monto: float):
    await users.update_one(
        {"_id": user_id},
        {"$inc": {"total_gastado": monto, "orders": 1}}
    )

async def estado_pedido_usuario(user_id: int, estado: bool):
    await users.update_one(
        {"_id": user_id},
        {"$set": {"tiene_pedido_pendiente": estado}}
    )

# ====================== PEDIDOS ======================
async def create_order(user_id: int, service_id: str, link: str, quantity: int, amount: float, costo: float, ganancia: float, api_order_id: int = None):
    nuevo_pedido = {
        "user_id": user_id,
        "service_id": service_id,
        "link": link,
        "quantity": quantity,
        "amount": amount,
        "costo": costo,
        "ganancia": ganancia,
        "api_order_id": api_order_id,
        "status": "pending",
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
    }
    await orders.insert_one(nuevo_pedido)
    await estado_pedido_usuario(user_id, True)
    return nuevo_pedido

async def update_order_status(api_order_id: int, new_status: str):
    await orders.update_one({"api_order_id": api_order_id}, {"$set": {"status": new_status}})

async def get_user_orders(user_id: int):
    cursor = orders.find({"user_id": user_id}).sort("time", -1)
    return await cursor.to_list(None)

async def get_order_by_api(api_order_id: int):
    return await orders.find_one({"api_order_id": api_order_id})

async def limpiar_pedidos_antiguos(dias: int):
    limite = datetime.now() - timedelta(days=dias)
    resultado = await orders.delete_many({"fecha": {"$lt": limite.strftime("%d/%m/%Y %H:%M")}})
    return resultado.deleted_count

# ====================== SERVICIOS Y CATEGORÍAS ======================
async def guardar_categoria(nombre: str):
    existe = await categories.find_one({"nombre": nombre})
    if not existe:
        await categories.insert_one({
            "nombre": nombre,
            "descripcion": "",
            "fecha_creacion": datetime.now().strftime("%d/%m/%Y %H:%M")
        })
        return True
    return False

async def guardar_servicio(datos_serv: dict):
    existe = await services.find_one({"codigo": datos_serv["codigo"]})
    if existe:
        await services.update_one({"codigo": datos_serv["codigo"]}, {"$set": datos_serv})
        return "actualizado"
    else:
        await services.insert_one(datos_serv)
        return "nuevo"

async def listar_categorias():
    cursor = categories.find()
    return await cursor.to_list(None)

async def listar_servicios(filtro: dict = None):
    filtro = filtro or {}
    cursor = services.find(filtro).sort("nombre", 1)
    return await cursor.to_list(None)

async def sumar_vista_servicio(codigo: str):
    await services.update_one({"codigo": codigo}, {"$inc": {"vistas": 1}})

# ====================== FACTURAS Y CONFIGURACIÓN ======================
async def obtener_siguiente_factura():
    conf = await configuracion.find_one({"_id": "global"})
    numero = conf.get("ultimo_numero_factura", 0) + 1
    await configuracion.update_one({"_id": "global"}, {"$set": {"ultimo_numero_factura": numero}})
    return numero

async def guardar_fecha_sincronizacion(ultima: str, proxima: str):
    await configuracion.update_one(
        {"_id": "global"},
        {"$set": {"ultima_sincronizacion": ultima, "proxima_sincronizacion": proxima}}
    )
# ====================== CONFIGURACIÓN EDITABLE ======================
async def iniciar_configuracion():
    conf = await configuracion.find_one({"_id": "global"})
    if not conf:
        inicio = {
            "_id": "global",
            "minimo_recarga": 50,
            "maximo_recarga": 5000,
            "metodos_pago": ["USDT TRC20", "Binance", "Transferencia"],
            "datos_pago": {
                "USDT TRC20": "Dirección: TU_DIRECCION",
                "Binance": "Usuario: TU_CUENTA",
                "Transferencia": "Banco: TU_BANCO / Cuenta: NUMERO"
            },
            "margen_global": 100,
            "moneda": "USD",
            "minimo_cantidad": 10,
            "maximo_cantidad": 10000,
            "estado": "activo"
        }
        await configuracion.insert_one(inicio)

async def obtener_config():
    conf = await configuracion.find_one({"_id": "global"})
    return conf or {}

async def actualizar_config(campo, valor):
    await configuracion.update_one(
        {"_id": "global"},
        {"$set": {campo: valor}},
        upsert=True
    )

async def agregar_metodo_pago(nombre, datos):
    await configuracion.update_one(
        {"_id": "global"},
        {"$addToSet": {"metodos_pago": nombre}, "$set": {f"datos_pago.{nombre}": datos}}
    )

async def eliminar_metodo_pago(nombre):
    await configuracion.update_one(
        {"_id": "global"},
        {"$pull": {"metodos_pago": nombre}, "$unset": {f"datos_pago.{nombre}": ""}}
    )
