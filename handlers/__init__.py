# ============================================================
# CONEXIÓN DE TODOS LOS MÓDULOS
# ============================================================

from .inicio import register_inicio_handlers
from .servicios import register_servicios_handlers, sincronizar_desde_proveedor, actualizar_estados_pedidos
from .recargas import register_recargas_handlers
from .promos_niveles import register_promos_niveles_handlers
from .administracion import register_administracion_handlers

async def tarea_sincronizacion_automatica():
    await sincronizar_desde_proveedor()
    await actualizar_estados_pedidos()

async def tareas_mantenimiento():
    pass

def all_handlers(app):
    register_inicio_handlers(app)
    register_servicios_handlers(app)
    register_recargas_handlers(app)
    register_promos_niveles_handlers(app)
    register_administracion_handlers(app)
