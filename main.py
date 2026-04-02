from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client
import os
from dotenv import load_dotenv
from datetime import date, datetime




# Cargar variables de entorno
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    raise RuntimeError("SUPABASE_URL o SUPABASE_KEY no están configurados")

supabase = create_client(url, key)

app = FastAPI()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # puedes restringir a la URL de tu frontend
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
        # Insertar venta con cajero_id
        venta_result = supabase.table("ventas").insert({
            "producto_id": venta.producto_id,
            "cantidad": venta.cantidad,
            "total": venta.total,
            "fecha": datetime.now().isoformat(),
            "cajero_id": cajero_id
        }).execute()
        print("Resultado inserción venta:", venta_result)

        # Restar stock con RPC
        supabase.rpc("restar_stock", {
            "p_producto_id": venta.producto_id,
            "p_cantidad": venta.cantidad
        }).execute()
        
        # Devolver inventario actualizado
        inventario_actualizado = supabase.table("inventario").select("*").execute()
        return {
            "mensaje": "Venta registrada correctamente",
            "inventario": inventario_actualizado.data
        }
    except Exception as e:
        print("Error en registrar venta:", e)
        raise HTTPException(status_code=500, detail="Error interno en venta")

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
                "valor": int(v["cantidad"]) * float(producto_info["precio"])  # 🔹 valor en dinero
            })

        return resultado
    except Exception as e:
        print("Error en ventas-dia:", e)
        raise HTTPException(status_code=500, detail="Error interno en ventas-dia")
