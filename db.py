# ============================================================
# Smm Panel Bot - Base de Datos
# Author: learningbots79 (https://github.com/learningbots79) 
# ============================================================

from pymongo import MongoClient
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from config import MONGO_URI, DB_NAME, REFERRER_BONUS

cliente = MongoClient(MONGO_URI)
db = cliente[DB_NAME]

# ---------- COLECCIONES ----------
usuarios = db["usuarios"]
configuracion = db["configuracion"]
categorias = db["categorias"]
servicios = db["servicios"]
pedidos = db["pedidos"]
recargas = db["recargas"]
codigos_promo = db["codigos_promo"]
niveles = db["niveles"]
auditoria = db["auditoria"]

# ---------- INICIO Y CONFIGURACIÓN ----------
async def iniciar_estructura_base():
    if "usuarios" not in await db.list_collection_names():
        await db.create_collection("usuarios")
    await iniciar_configuracion()

async def iniciar_configuracion():
    conf = await configuracion.find_one({"_id": "global"})
    if not conf:
        inicio = {
            "_id": "global",
            "modo_mantenimiento": False,
            "moneda": "USD",
            "margen_global": 100,
            "recarga_minimo": 50,
            "recarga_maximo": 5000,
            "recarga_limite_diario": 10000,
            "metodos_pago": ["USDT TRC20", "Binance", "Transferencia"],
            "datos_pago": {
                "USDT TRC20": "Dirección: TU_DIRECCION",
                "Binance": "Usuario: TU_CUENTA",
                "Transferencia": "Banco: TU_BANCO / Cuenta: NUMERO"
            },
            "tiempo_espera_pedido": 2,
            "admin_contacto": "tu_usuario_telegram"
        }
        await configuracion.insert_one(inicio)

async def obtener_config():
    return await configuracion.find_one({"_id": "global"}) or {}

async def actualizar_configuracion(campo, valor):
    await configuracion.update_one({"_id": "global"}, {"$set": {campo: valor}}, upsert=True)

async def guardar_accion(accion, detalle, usuario=0):
    await auditoria.insert_one({
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "usuario": usuario,
        "accion": accion,
        "detalle": detalle
    })

# ---------- USUARIOS ----------
async def existe_usuario(uid):
    return await usuarios.count_documents({"_id": uid}) > 0

async def crear_usuario(uid, nombre, invitador=None):
    if await existe_usuario(uid): return
    await usuarios.insert_one({
        "_id": uid, "nombre": nombre, "saldo": 0, "gasto_total": 0,
        "invitado_por": invitador, "fecha_registro": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "ultimo_bono": None, "bloqueado": False, "motivo_bloqueo": ""
    })
    if invitador and invitador != uid:
        await sumar_saldo(invitador, REFERRER_BONUS, "Bono por referido")

async def obtener_usuario(uid):
    return await usuarios.find_one({"_id": uid})

async def obtener_saldo(uid):
    u = await usuarios.find_one({"_id": uid})
    return u.get("saldo", 0) if u else 0

async def sumar_saldo(uid, monto, motivo=""):
    await usuarios.update_one({"_id": uid}, {"$inc": {"saldo": monto}})
    if monto < 0:
        await usuarios.update_one({"_id": uid}, {"$inc": {"gasto_total": abs(monto)}})
    await guardar_accion("Movimiento saldo", f"Usuario {uid} | {monto} | {motivo}")

async def ultimo_bono(uid):
    u = await usuarios.find_one({"_id": uid})
    return u.get("ultimo_bono") if u else None

async def guardar_hora_bono(uid):
    await usuarios.update_one({"_id": uid}, {"$set": {"ultimo_bono": datetime.now()}})

async def cambiar_estado_bloqueo(uid, estado, motivo=""):
    await usuarios.update_one({"_id": uid}, {"$set": {"bloqueado": estado, "motivo_bloqueo": motivo}})

# ---------- SERVICIOS Y CATEGORIAS ----------
async def guardar_categoria(nombre):
    if await categorias.count_documents({"nombre": nombre}) == 0:
        await categorias.insert_one({"nombre": nombre})
        return True
    return False

async def listar_categorias_activas():
    lista = await categorias.find().sort("nombre",1).to_list(None)
    return [c["nombre"] for c in lista]

async def guardar_o_actualizar_servicio(datos):
    existe = await servicios.find_one({"codigo": datos["codigo"]})
    if existe:
        await servicios.update_one({"_id": existe["_id"]}, {"$set": datos})
        return "actualizado"
    await servicios.insert_one(datos)
    return "nuevo"

async def servicios_por_categoria(nombre):
    return await servicios.find({"categoria": nombre, "estado":"Activo"}).sort("nombre",1).to_list(None)

async def obtener_servicio(codigo):
    return await servicios.find_one({"codigo": codigo})

async def buscar_servicios(palabra):
    return await servicios.find({
        "nombre": {"$regex": palabra, "$options":"i"}, "estado":"Activo"
    }).limit(10).to_list(None)

# ---------- PEDIDOS ----------
async def crear_pedido(datos):
    await pedidos.insert_one(datos)

async def pedidos_de_usuario(uid):
    return await pedidos.find({"user_id": uid}).sort("fecha",-1).limit(8).to_list(None)

async def obtener_pedidos_actualizar():
    return await pedidos.find({"estado": {"$nin":["Completado","Cancelado"]}}).to_list(None)

async def actualizar_estado_pedido(id_ped, estado):
    await pedidos.update_one({"_id": ObjectId(id_ped)}, {"$set": {"estado": estado}})

async def fecha_ultimo_pedido(uid):
    p = await pedidos.find_one({"user_id": uid}, sort=[("fecha",-1)])
    return datetime.strptime(p["fecha"], "%d/%m/%Y %H:%M") if p else None

# ---------- RECARGAS ----------
async def crear_solicitud_recarga(user_id, metodo, monto, comprobante_id):
    nueva = {
        "user_id": user_id, "metodo": metodo, "monto": monto,
        "comprobante_id": comprobante_id, "estado": "PENDIENTE",
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "revisado_por": None
    }
    await recargas.insert_one(nueva)
    return nueva

async def obtener_recarga_por_id(id_str):
    return await recargas.find_one({"_id": ObjectId(id_str)})

async def actualizar_estado_recarga(id_str, estado, revisado):
    await recargas.update_one(
        {"_id": ObjectId(id_str)},
        {"$set": {"estado": estado, "revisado_por": revisado}}
    )
    if estado == "APROBADO":
        sol = await obtener_recarga_por_id(id_str)
        await sumar_saldo(sol["user_id"], sol["monto"], "Recarga aprobada")

async def total_recargas_hoy(uid, fecha):
    lista = await recargas.find({"user_id": uid, "fecha": {"$regex": f"^{fecha}"}, "estado":"APROBADO"}).to_list(None)
    return sum(r["monto"] for r in lista)

async def listar_recargas(filtro):
    return await recargas.find(filtro).sort("fecha",-1).to_list(None)

# ---------- CÓDIGOS PROMO ----------
async def crear_codigo_promo(datos):
    await codigos_promo.insert_one(datos)

async def obtener_codigos_activos():
    return await codigos_promo.find({"estado":"ACTIVO"}).to_list(None)

async def canjear_codigo(uid, codigo):
    cod = await codigos_promo.find_one({"codigo": codigo, "estado":"ACTIVO"})
    if not cod: return "no_existe"
    ya_usado = await db.auditoria.count_documents({"accion":"Código usado", "detalle":f"{codigo} | {uid}"})
    if ya_usado: return "ya_usado"
    if cod["usado"] >= cod["max_usos"]: return "agotado"

    await codigos_promo.update_one({"_id": cod["_id"]}, {"$inc": {"usado":1}})
    await guardar_accion("Código usado", f"{codigo} | {uid}")

    if cod["tipo"] == "saldo":
        await sumar_saldo(uid, cod["valor"], f"Código {codigo}")
        return "aplicado_saldo"
    return "aplicado_desc"

# ---------- NIVELES ----------
async def guardar_nivel(datos):
    await niveles.update_one({"nivel": datos["nivel"]}, {"$set": datos}, upsert=True)

async def obtener_todos_niveles():
    return await niveles.find().sort("nivel",1).to_list(None)

# ---------- REPORTES Y OTROS ----------
async def obtener_datos_reporte(desde):
    fecha_texto = desde.strftime("%d/%m/%Y")
    total_usu = await usuarios.count_documents({})
    total_ped = await pedidos.count_documents({})
    ing = await pedidos.aggregate([
        {"$match": {"fecha": {"$regex": f"^{fecha_texto}"}}},
        {"$group": {"_id":None, "total":{"$sum":"$monto"}}}
    ]).to_list(None)
    rec = await recargas.aggregate([
        {"$match": {"estado":"APROBADO"}},
        {"$group": {"_id":None, "total":{"$sum":"$monto"}}}
    ]).to_list(None)
    return {
        "usuarios": total_usu,
        "pedidos": total_ped,
        "ingresos": ing[0]["total"] if ing else 0,
        "recargas": rec[0]["total"] if rec else 0,
        "ganancia": 0
    }

async def obtener_ultimas_acciones(cantidad=15):
    return await auditoria.find().sort("fecha",-1).limit(cantidad).to_list(None)

async def obtener_todo_coleccion(nombre):
    return await db[nombre].find().to_list(None)
