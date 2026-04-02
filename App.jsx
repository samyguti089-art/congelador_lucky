import React, { useState, useEffect } from "react";
import axios from "axios";
import Login from "./login";
import POS from "./pos";

function App() {
  const [usuario, setUsuario] = useState(null);
  const [inventario, setInventario] = useState([]);
  const [mensajeInventario, setMensajeInventario] = useState("");
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  useEffect(() => {
    const usuarioGuardado = localStorage.getItem("usuario");
    if (usuarioGuardado) {
      setUsuario(JSON.parse(usuarioGuardado));
    }
  }, []);

  const manejarLogin = (user) => {
    setUsuario(user);
    localStorage.setItem("usuario", JSON.stringify(user));
  };

  const actualizarInventario = async (forzarRecarga = false) => {
    try {
      const res = await axios.get("http://127.0.0.1:8000/inventario");
      setInventario(res.data);

      if (forzarRecarga) {
        window.location.reload();
      } else {
        setMensajeInventario("Inventario actualizado correctamente ✔️");
        setTimeout(() => setMensajeInventario(""), 3000);
      }
    } catch (err) {
      console.error("Error actualizando inventario:", err);
      setMensajeInventario("❌ Error al actualizar inventario");
      setTimeout(() => setMensajeInventario(""), 3000);
    }
  };

  useEffect(() => {
    if (usuario && usuario.rol === "cajero") {
      actualizarInventario();
    }
  }, [usuario]);

  const registrarVenta = async (item) => {
  try {
    const res = await axios.post("http://127.0.0.1:8000/venta", {
      producto_id: item.id,
      cantidad: item.cantidad,
      total: item.total
    }, {
      params: { cajero_id: usuario.id }   // 🔹 enviamos el cajero_id como parámetro
    });

    alert(res.data.mensaje);

    if (res.data.inventario) {
      setInventario(res.data.inventario);
      setMensajeInventario("Inventario actualizado después de la venta ✔️");
      setTimeout(() => setMensajeInventario(""), 3000);

      // 🔹 Actualizar trigger para refrescar gráfico
      setRefreshTrigger(prev => prev + 1);
    }
  } catch (err) {
    console.error("Error registrando venta:", err);
    alert("Error al registrar venta");
  }
};


  if (!usuario) {
    return <Login setUsuario={manejarLogin} />;
  }

  if (usuario.rol === "cajero") {
    return (
      <POS
        usuario={usuario}
        inventario={inventario}
        registrarVenta={registrarVenta}
        actualizarInventario={actualizarInventario}
        mensajeInventario={mensajeInventario}
        refreshTrigger={refreshTrigger}
      />
    );
  }

  if (usuario.rol === "admin") {
    return <div>Dashboard del administrador en construcción...</div>;
  }

  return <div>Rol desconocido</div>;
}

export default App;
