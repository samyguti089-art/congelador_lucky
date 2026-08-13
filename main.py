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

if not url or not key:
    raise RuntimeError("SUPABASE_URL o SUPABASE_KEY no están configurados")

supabase = create_client(url, key)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://congelador-lucky-fronted.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# ENDPOINT DE PRUEBA
# ============================================================
@app.get("/")
def root():
    return {"mensaje": "Backend activo"}

# ============================================================
# MODELOS
# ============================================================
class LoginRequest(BaseModel):
    nombre: str
    password: str

class VentaRequest(BaseModel):
    producto_id: int
    cantidad: int
    total: float

class ProductoCarrito(BaseModel):
    producto_id: Optional[int] = None
    combo_id: Optional[int] = None
    cantidad: int
    total: float

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
    total_ventas_sistema: float
    total_efectivo_sistema: float
    total_transferencia_sistema: float
    efectivo_contado: float
    transferencia_contada: float
    diferencia_efectivo: float
    diferencia_transferencia: float
    observaciones: Optional[str] = None

# ============================================================
# LOGIN
# ============================================================
@app.post("/login")
def login(request: LoginRequest):
    try:
        result = supabase.rpc("validar_login", {
            "p_nombre": request.nombre,
            "p_password": request.password
        }).execute()
        print("Resultado login:", result)

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")

        usuario = result.data[0]
        return {
            "id": usuario["id"],
            "nombre": usuario["nombre"],
            "rol": usuario["rol"]
        }
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
        print("Inventario:", result)
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
# VENTA INDIVIDUAL (legado)
# ============================================================
@app.post("/venta")
def registrar_venta(venta: VentaRequest, cajero_id: int):
    try:
        venta_result = supabase.table("ventas").insert({
            "producto_id": venta.producto_id,
            "cantidad": venta.cantidad,
            "total": venta.total,
            "fecha": datetime.now().isoformat(),
            "cajero_id": cajero_id
        }).execute()
        print("Resultado inserción venta:", venta_result)

        supabase.rpc("restar_stock", {
            "p_producto_id": venta.producto_id,
            "p_cantidad": venta.cantidad
        }).execute()
        
        inventario_actualizado = supabase.table("inventario").select("*").execute()
        return {
            "mensaje": "Venta registrada correctamente",
            "inventario": inventario_actualizado.data
        }
    except Exception as e:
        print("Error en registrar venta:", e)
        raise HTTPException(status_code=500, detail="Error interno en venta")

# ============================================================
# VENTA CON CARRITO (combos + método de pago) CORREGIDO
@app.post("/venta-carrito")
def registrar_venta_carrito(venta_data: VentaCarritoRequest):
    try:
        productos_json = [
            {
                "producto_id": p.producto_id,
                "combo_id": p.combo_id,
                "cantidad": p.cantidad,
                "total": p.total
            }
            for p in venta_data.productos
        ]

        result = supabase.rpc("registrar_venta_con_combos", {
            "p_cajero_id": venta_data.cajero_id,
            "p_productos": productos_json,
            "p_metodo_pago": venta_data.metodo_pago,
            "p_cambio": venta_data.cambio,
            "p_monto_efectivo": venta_data.monto_efectivo or 0,
            "p_monto_transferencia": venta_data.monto_transferencia or 0
        }).execute()

        return {
            "mensaje": "Venta registrada exitosamente",
            "id_venta": result.data["id_venta"],
            "total": result.data["total_venta"],
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

        ventas = supabase.table("ventas") \
            .select("producto_id, cantidad, fecha") \
            .eq("cajero_id", cajero_id) \
            .gte("fecha", inicio_dia) \
            .lte("fecha", fin_dia) \
            .execute()

        if not ventas.data:
            return []

        inventario = supabase.table("inventario").select("id, nombre, precio").execute()
        mapa_productos = {p["id"]: {"nombre": p["nombre"], "precio": p["precio"]} for p in inventario.data}

        resultado = []
        for v in ventas.data:
            producto_info = mapa_productos.get(v["producto_id"], {"nombre": "Desconocido", "precio": 0})
            resultado.append({
                "producto": producto_info["nombre"],
                "cantidad": int(v["cantidad"]),
                "valor": int(v["cantidad"]) * float(producto_info["precio"])
            })

        return resultado
    except Exception as e:
        print("Error en ventas-dia:", e)
        raise HTTPException(status_code=500, detail="Error interno en ventas-dia")

# ============================================================
# DESPACHOS
# ============================================================
@app.post("/despacho")
def registrar_despacho(despacho: DespachoCreate):
    try:
        fecha = despacho.fecha if despacho.fecha else datetime.now().strftime("%Y-%m-%d")
        
        result = supabase.table("despachos").insert({
            "producto_id": despacho.producto_id,
            "cantidad": despacho.cantidad,
            "fecha": fecha,
            "observaciones": despacho.observaciones,
            "usuario_id": despacho.usuario_id
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
    try:
        if fecha:
            query = supabase.table("despachos").select("*").eq("fecha", fecha).order("created_at", desc=True)
        else:
            query = supabase.table("despachos").select("*").order("fecha", desc=True).limit(50)
        
        result = query.execute()
        return result.data
    except Exception as e:
        print("Error en /despachos:", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/despachos/resumen")
def resumen_despachos(fecha_inicio: str, fecha_fin: str):
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
        # Verificar que el cajero existe
        usuario = supabase.table("usuarios").select("id").eq("id", cuadre.cajero_id).execute()
        if not usuario.data:
            raise HTTPException(status_code=404, detail="Cajero no encontrado")

        result = supabase.table("cuadres_caja").insert({
            "fecha": cuadre.fecha.isoformat(),
            "cajero_id": cuadre.cajero_id,
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
# OBTENER CUADRES (para administrador)
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
