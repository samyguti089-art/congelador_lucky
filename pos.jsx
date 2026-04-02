import React, { useState } from "react";
import "./POS.css";
import VentasGrafico from "./VentasGrafico";

function POS({ usuario, inventario, registrarVenta, actualizarInventario, mensajeInventario, refreshTrigger }) {
  const [productoSeleccionado, setProductoSeleccionado] = useState(null);
  const [cantidad, setCantidad] = useState(1);

  if (!inventario || inventario.length === 0) {
    return <p>Cargando inventario...</p>;
  }

  const aumentarCantidad = () => {
    if (productoSeleccionado && cantidad < productoSeleccionado.cantidad) {
      setCantidad(cantidad + 1);
    }
  };

  const disminuirCantidad = () => {
    if (cantidad > 1) {
      setCantidad(cantidad - 1);
    }
  };

  return (
    <div className="pos-container">
      <header className="pos-header">
        <h1>TPV - {usuario.nombre}</h1>
        <button className="refresh-btn" onClick={() => actualizarInventario(true)}>
          🔄 Actualizar inventario
        </button>
      </header>

      {mensajeInventario && (
        <div className="mensaje-inventario">{mensajeInventario}</div>
      )}

      {/* Gráfico de ventas del día */}
      <VentasGrafico usuario={usuario} refreshTrigger={refreshTrigger} />

      <div className="pos-grid">
        {inventario.map((item) => (
          <div key={item.id} className="product-card">
            <h3>{item.nombre}</h3>
            <p className="stock">Stock: {item.cantidad}</p>
            <p className="price">Precio: ${item.precio}</p>
            <button onClick={() => {
              setProductoSeleccionado(item);
              setCantidad(1);
            }}>
              Seleccionar
            </button>
          </div>
        ))}
      </div>

      {productoSeleccionado && (
        <div className="venta-panel">
          <h2>Producto seleccionado</h2>
          <p><strong>{productoSeleccionado.nombre}</strong></p>
          <p>Stock disponible: {productoSeleccionado.cantidad}</p>
          <p>Precio unitario: ${productoSeleccionado.precio}</p>

          <div className="cantidad-selector">
            <button className="cantidad-btn" onClick={disminuirCantidad}>-</button>
            <input
              type="number"
              min="1"
              max={productoSeleccionado.cantidad}
              value={cantidad}
              onChange={(e) => setCantidad(parseInt(e.target.value))}
            />
            <button className="cantidad-btn" onClick={aumentarCantidad}>+</button>
          </div>

          <p className="total">Total: ${cantidad * productoSeleccionado.precio}</p>

          <button
            className="registrar-btn"
            onClick={() => registrarVenta({
              ...productoSeleccionado,
              cantidad,
              total: cantidad * productoSeleccionado.precio
            })}
          >
            Registrar venta
          </button>
        </div>
      )}
    </div>
  );
}

export default POS;
