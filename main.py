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

# Endpoint de prueba
@app.get("/")
def root():
    return {"mensaje": "Backend activo"}

# Modelos
class LoginRequest(BaseModel):
    nombre: str
    password: str

class VentaRequest(BaseModel):
    producto_id: int
    cantidad: int
    total: float

# ========== MODELOS PARA CARRITO CON COMBOS ==========
class ProductoCarrito(BaseModel):
    producto_id: Optional[int] = None  # Puede ser None si es combo
    combo_id: Optional[int] = None     # Nuevo campo para combos
    cantidad: int
    total: float

class VentaCarritoRequest(BaseModel):
    cajero_id: int
    productos: List[ProductoCarrito]

# Endpoints
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

@app.get("/inventario")
def obtener_inventario():
    try:
        result = supabase.table("inventario").select("*").execute()
        print("Inventario:", result)
        return result.data
    except Exception as e:
        print("Error en inventario:", e)
        raise HTTPException(status_code=500, detail="Error interno en inventario")
    
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

# ========== ENDPOINT PARA VENTA CON CARRITO (SOPORTA COMBOS) ==========
@app.post("/venta-carrito")
def registrar_venta_carrito(venta_data: VentaCarritoRequest):
    try:
        # Calcular el total de toda la venta
        total_venta = sum(p.total for p in venta_data.productos)
        
        # 1. Insertar cabecera en ventas_cabecera
        cabecera = supabase.table("ventas_cabecera").insert({
            "fecha": datetime.now().isoformat(),
            "cajero_id": venta_data.cajero_id,
            "total_venta": total_venta
        }).execute()
        
        # Obtener el ID de la venta recién creada
        id_venta = cabecera.data[0]["id_venta"]
        
        # 2. Procesar cada producto/combo en el carrito
        for prod in venta_data.productos:
            if prod.combo_id:
                # Es un COMBO - obtener los productos del combo
                combo_detalle = supabase.table("combo_detalle").select("*").eq("combo_id", prod.combo_id).execute()
                
                for item in combo_detalle.data:
                    producto_id = item["producto_id"]
                    cantidad_combo = prod.cantidad * item["cantidad"]
                    
                    # Obtener precio del producto
                    producto = supabase.table("inventario").select("precio").eq("id", producto_id).execute()
                    if producto.data:
                        precio_unitario = producto.data[0]["precio"]
                        subtotal = cantidad_combo * precio_unitario
                        
                        # Insertar detalle
                        supabase.table("detalle_ventas").insert({
                            "id_venta": id_venta,
                            "producto_id": producto_id,
                            "cantidad": cantidad_combo,
                            "precio_unitario": precio_unitario,
                            "subtotal": subtotal
                        }).execute()
                        
                        # Restar stock
                        supabase.rpc("restar_stock", {
                            "p_producto_id": producto_id,
                            "p_cantidad": cantidad_combo
                        }).execute()
            else:
                # Es un PRODUCTO NORMAL
                precio_unitario = prod.total / prod.cantidad
                
                # Insertar detalle
                supabase.table("detalle_ventas").insert({
                    "id_venta": id_venta,
                    "producto_id": prod.producto_id,
                    "cantidad": prod.cantidad,
                    "precio_unitario": precio_unitario,
                    "subtotal": prod.total
                }).execute()
                
                # Restar stock
                supabase.rpc("restar_stock", {
                    "p_producto_id": prod.producto_id,
                    "p_cantidad": prod.cantidad
                }).execute()
        
        # 3. Devolver inventario actualizado
        inventario_actualizado = supabase.table("inventario").select("*").execute()
        return {
            "mensaje": "Venta con carrito registrada exitosamente",
            "id_venta": id_venta,
            "total": total_venta,
            "inventario": inventario_actualizado.data
        }
    except Exception as e:
        print("Error en /venta-carrito:", e)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.get("/ventas/diarias")
def ventas_diarias():
    try:
        result = supabase.rpc("ventas_diarias").execute()
        print("Ventas diarias:", result)
        return result.data
    except Exception as e:
        print("Error en ventas diarias:", e)
        raise HTTPException(status_code=500, detail="Error interno en ventas diarias")

@app.get("/ventas/mensuales")
def ventas_mensuales():
    try:
        result = supabase.rpc("ventas_mensuales").execute()
        print("Ventas mensuales:", result)
        return result.data
    except Exception as e:
        print("Error en ventas mensuales:", e)
        raise HTTPException(status_code=500, detail="Error interno en ventas mensuales")
    
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
