from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client
import os
from dotenv import load_dotenv
from datetime import date, datetime
from typing import List, Optional

# Cargar variables de entorno
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
MODO = os.getenv("MODO", "pos")  # 'pos' o 'fabrica'

if not url or not key:
    raise RuntimeError("SUPABASE_URL o SUPABASE_KEY no están configurados")

supabase = create_client(url, key)

app = FastAPI()

# ============================================================
# CORS
# ============================================================
origins = [
    "https://congelador-lucky-fronted.vercel.app",           # Tienda
    "https://congelador-lucky-fronted-fabrica.vercel.app",   # Fábrica ✅
    "http://localhost:5173",
    "http://127.0.0.1:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# ENDPOINT DE PRUEBA
# ============================================================
@app.get("/")
def root():
    return {"mensaje": f"Backend activo (modo: {MODO})"}

# ============================================================
# MODELOS
# ============================================================
class LoginRequest(BaseModel):
    nombre: str
    password: str

class ProductoCarrito(BaseModel):
    producto_id: Optional[int] = None
    combo_id: Optional[int] = None
    cantidad: int
    total: float
    descripcion: Optional[str] = None

class VentaCarritoRequest(BaseModel):
    cajero_id: int
    productos: List[ProductoCarrito]
    metodo_pago: str = "efectivo"
    cambio: float = 0.0
    monto_efectivo: float = 0.0
    monto_transferencia: float = 0.0

class DespachoCreate(BaseModel):
    producto_id: int
    cantidad: int
    fecha: Optional[str] = None
    observaciones: Optional[str] = None
    usuario_id: int

class CuadreCajaCreate(BaseModel):
    fecha: date
    cajero_id: int
    base: float
    total_ventas_sistema: float
    total_efectivo_sistema: float
    total_transferencia_sistema: float
    efectivo_contado: float
    transferencia_contada: float
    diferencia_efectivo: float
    diferencia_transferencia: float
    observaciones: Optional[str] = None

class MenudoCreate(BaseModel):
    cajero_id: int
    monto: float
    registrado_por: Optional[int] = None
    observaciones: Optional[str] = None

@app.post("/login")
def login(request: LoginRequest):
    try:
        result = supabase.rpc("validar_login", {
            "p_nombre": request.nombre,
            "p_password": request.password
        }).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")

        usuario = result.data[0]
        return {
            "id": usuario["id"],
            "nombre": usuario["nombre"],
            "rol": usuario["rol"]
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        print("Error en login:", e)
        raise HTTPException(status_code=500, detail="Error interno en login")
# ============================================================
# INVENTARIO
# ============================================================
@app.get("/inventario")
def obtener_inventario():
    try:
        result = supabase.table("inventario").select("*").execute()
        return result.data
    except Exception as e:
        print("Error en inventario:", e)
        raise HTTPException(status_code=500, detail="Error interno en inventario")

# ============================================================
# VENTAS ACUMULADAS
# ============================================================
@app.get("/ventas/acumuladas")
def obtener_ventas_acumuladas(fecha_inicio: str, fecha_fin: str):
    try:
        result = supabase.rpc("ventas_acumuladas", {
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin
        }).execute()
        return result.data
    except Exception as e:
        print("Error en /ventas/acumuladas:", e)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# VENTA CON CARRITO (según MODO)
# ============================================================
@app.post("/venta-carrito")
def registrar_venta_carrito(venta_data: VentaCarritoRequest):
    try:
        productos_json = [
            {
                "producto_id": p.producto_id,
                "combo_id": p.combo_id,
                "cantidad": p.cantidad,
                "total": p.total,
                "descripcion": p.descripcion
            }
            for p in venta_data.productos
        ]

        # Elegir la función RPC según el modo
        if MODO == "fabrica":
            rpc_name = "registrar_venta_sin_inventario"
        else:
            rpc_name = "registrar_venta_con_combos"

        result = supabase.rpc(rpc_name, {
            "p_cajero_id": venta_data.cajero_id,
            "p_productos": productos_json,
            "p_metodo_pago": venta_data.metodo_pago,
            "p_cambio": venta_data.cambio,
            "p_monto_efectivo": venta_data.monto_efectivo or 0,
            "p_monto_transferencia": venta_data.monto_transferencia or 0
        }).execute()

        data = result.data
        if isinstance(data, list):
            data = data[0] if data else {}

        return {
            "mensaje": "Venta registrada exitosamente",
            "id_venta": data.get("id_venta"),
            "total": data.get("total_venta"),
            "inventario": supabase.table("inventario").select("*").execute().data
        }
    except Exception as e:
        print("Error en /venta-carrito:", e)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# VENTAS DEL DÍA (por cajero)
# ============================================================
@app.get("/ventas-dia")
def ventas_dia(cajero_id: int):
    try:
        hoy = date.today().strftime("%Y-%m-%d")
        inicio_dia = f"{hoy} 00:00:00"
        fin_dia = f"{hoy} 23:59:59"

        cabeceras = supabase.table("ventas_cabecera") \
            .select("id_venta") \
            .eq("cajero_id", cajero_id) \
            .gte("fecha", inicio_dia) \
            .lte("fecha", fin_dia) \
            .execute()

        if not cabeceras.data:
            return []

        ids = [c["id_venta"] for c in cabeceras.data]

        detalles = supabase.table("detalle_ventas") \
            .select("producto_id, cantidad, subtotal") \
            .in_("id_venta", ids) \
            .execute()

        inventario = supabase.table("inventario").select("id, nombre, precio").execute()
        mapa_productos = {p["id"]: {"nombre": p["nombre"], "precio": p["precio"]} for p in inventario.data}

        resumen = {}
        for d in detalles.data:
            pid = d["producto_id"]
            if pid is None:
                continue
            nombre = mapa_productos.get(pid, {"nombre": "Desconocido", "precio": 0})["nombre"]
            if pid not in resumen:
                resumen[pid] = {"producto": nombre, "cantidad": 0, "valor": 0.0}
            resumen[pid]["cantidad"] += int(d["cantidad"])
            resumen[pid]["valor"] += float(d["subtotal"])

        return list(resumen.values())

    except Exception as e:
        print("Error en ventas-dia:", e)
        raise HTTPException(status_code=500, detail="Error interno en ventas-dia")

# ============================================================
# DESPACHOS (solo en modo POS)
# ============================================================
@app.post("/despacho")
def registrar_despacho(despacho: DespachoCreate):
    if MODO == "fabrica":
        raise HTTPException(status_code=400, detail="Despachos no disponibles en modo fábrica")

    try:
        fecha = despacho.fecha if despacho.fecha else datetime.now().strftime("%Y-%m-%d")
        
        result = supabase.table("despachos").insert({
            "producto_id": despacho.producto_id,
            "cantidad": despacho.cantidad,
            "fecha": fecha,
            "observaciones": despacho.observaciones,
            "usuario_id": despacho.usuario_id,
            "estado": "cerrado",
            "fecha_cierre": datetime.now().isoformat()
        }).execute()
        
        supabase.rpc("sumar_stock", {
            "p_producto_id": despacho.producto_id,
            "p_cantidad": despacho.cantidad
        }).execute()
        
        return {
            "mensaje": "Despacho registrado correctamente",
            "despacho": result.data[0]
        }
    except Exception as e:
        print("Error en /despacho:", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/despachos")
def obtener_despachos(fecha: Optional[str] = None):
    if MODO == "fabrica":
        return []

    try:
        if fecha:
            query = supabase.table("despachos") \
                .select("*") \
                .eq("fecha", fecha) \
                .order("fecha_cierre", desc=True)
        else:
            query = supabase.table("despachos") \
                .select("*") \
                .order("fecha", desc=True) \
                .limit(50)
        
        result = query.execute()
        return result.data
    except Exception as e:
        print("Error en /despachos:", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/despachos/resumen")
def resumen_despachos(fecha_inicio: str, fecha_fin: str):
    if MODO == "fabrica":
        return []
    try:
        result = supabase.rpc("resumen_despachos", {
            "fecha_desde": fecha_inicio,
            "fecha_hasta": fecha_fin
        }).execute()
        return result.data
    except Exception as e:
        print("Error en /despachos/resumen:", e)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# CUADRE DE CAJA
# ============================================================
@app.post("/cuadre/guardar")
def guardar_cuadre(cuadre: CuadreCajaCreate):
    try:
        usuario = supabase.table("usuarios").select("id").eq("id", cuadre.cajero_id).execute()
        if not usuario.data:
            raise HTTPException(status_code=404, detail="Cajero no encontrado")

        if cuadre.base is None or cuadre.base < 0:
            raise HTTPException(status_code=400, detail="La base del día es obligatoria y debe ser mayor o igual a 0")

        result = supabase.table("cuadres_caja").insert({
            "fecha": cuadre.fecha.isoformat(),
            "cajero_id": cuadre.cajero_id,
            "base": cuadre.base,
            "total_ventas_sistema": cuadre.total_ventas_sistema,
            "total_efectivo_sistema": cuadre.total_efectivo_sistema,
            "total_transferencia_sistema": cuadre.total_transferencia_sistema,
            "efectivo_contado": cuadre.efectivo_contado,
            "transferencia_contada": cuadre.transferencia_contada,
            "diferencia_efectivo": cuadre.diferencia_efectivo,
            "diferencia_transferencia": cuadre.diferencia_transferencia,
            "diferencia": cuadre.diferencia_efectivo + cuadre.diferencia_transferencia,
            "observaciones": cuadre.observaciones,
            "estado": "cerrado"
        }).execute()
        
        return {
            "mensaje": "Cuadre de caja guardado exitosamente",
            "cuadre": result.data[0]
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        print("Error guardando cuadre:", e)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# OBTENER CUADRES
# ============================================================
@app.get("/cuadres")
def obtener_cuadres(fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None):
    try:
        query = supabase.table("cuadres_caja").select("*").order("fecha", desc=True)
        
        if fecha_inicio:
            query = query.gte("fecha", fecha_inicio)
        if fecha_fin:
            query = query.lte("fecha", fecha_fin)
        
        result = query.execute()
        return result.data
    except Exception as e:
        print("Error obteniendo cuadres:", e)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# MENUDO
# ============================================================
@app.post("/menudo")
def registrar_menudo(menudo: MenudoCreate):
    try:
        if menudo.monto <= 0:
            raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")

        result = supabase.table("menudo_registros").insert({
            "cajero_id": menudo.cajero_id,
            "monto": menudo.monto,
            "fecha": date.today().isoformat(),
            "registrado_por": menudo.registrado_por,
            "observaciones": menudo.observaciones
        }).execute()

        return {
            "mensaje": "Menudo registrado correctamente",
            "registro": result.data[0]
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        print("Error en /menudo:", e)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# BASE DEL DÍA
# ============================================================
@app.get("/base-del-dia")
def obtener_base_del_dia(cajero_id: int):
    try:
        ultimo_cuadre = supabase.table("cuadres_caja") \
            .select("base, fecha") \
            .eq("cajero_id", cajero_id) \
            .order("fecha", desc=True) \
            .limit(1) \
            .execute()

        base_inicial = 0
        if ultimo_cuadre.data:
            base_inicial = float(ultimo_cuadre.data[0].get("base") or 0)

        hoy = date.today().isoformat()
        menudo_hoy_result = supabase.table("menudo_registros") \
            .select("monto") \
            .eq("cajero_id", cajero_id) \
            .eq("fecha", hoy) \
            .execute()

        menudo_hoy = sum(float(r["monto"]) for r in (menudo_hoy_result.data or []))

        return {
            "base_inicial": base_inicial,
            "menudo_hoy": menudo_hoy,
            "base_total": base_inicial + menudo_hoy
        }
    except Exception as e:
        print("Error en /base-del-dia:", e)
        raise HTTPException(status_code=500, detail=str(e))
