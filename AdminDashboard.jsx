// src/AdminDashboard.jsx
import React, { useEffect, useState } from "react";
import axios from "axios";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from "recharts";

function AdminDashboard({ usuario }) {
  const [ventasMensuales, setVentasMensuales] = useState([]);

  useEffect(() => {
    axios.get("http://localhost:8000/ventas/mensuales")
      .then(res => setVentasMensuales(res.data));
  }, []);

  return (
    <div style={{ margin: "20px" }}>
      <h2>Dashboard Admin - {usuario.nombre}</h2>
      <LineChart width={600} height={300} data={ventasMensuales}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="mes" />
        <YAxis />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="total_mes" stroke="#8884d8" />
      </LineChart>
    </div>
  );
}

export default AdminDashboard;
