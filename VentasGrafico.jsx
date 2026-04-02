import React, { useEffect, useState } from "react";
import { Doughnut } from "react-chartjs-2";
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from "chart.js";
import axios from "axios";

ChartJS.register(ArcElement, Tooltip, Legend);

function VentasGrafico({ usuario, refreshTrigger }) {
  const [ventasDia, setVentasDia] = useState([]);

  useEffect(() => {
    const cargarVentas = async () => {
      try {
        const res = await axios.get("http://127.0.0.1:8000/ventas-dia", {
          params: { cajero_id: usuario.id }
        });
        setVentasDia(res.data || []);
      } catch (err) {
        console.error("Error cargando ventas del día:", err);
      }
    };

    cargarVentas();
  }, [usuario, refreshTrigger]);

  // 🔹 Totales
  const totalUnidades = ventasDia.reduce((acc, v) => acc + (v.cantidad || 0), 0);
  const totalDinero = ventasDia.reduce((acc, v) => acc + (v.valor || 0), 0);

  const data = {
    labels: ventasDia.map(v => v.producto),
    datasets: [
      {
        data: ventasDia.map(v => v.cantidad),
        backgroundColor: [
          "#FF6384",
          "#36A2EB",
          "#FFCE56",
          "#4BC0C0",
          "#9966FF",
          "#FF9F40"
        ]
      }
    ]
  };

  // 🔹 Plugin con estilo moderno
  const centerTextPlugin = {
    id: "centerText",
    beforeDraw: (chart) => {
      const { width, height } = chart;
      const ctx = chart.ctx;
      ctx.restore();

      // Estilo para unidades
      ctx.font = "bold 16px Arial";
      ctx.fillStyle = "#333";
      ctx.textBaseline = "middle";
      const texto1 = `Unidades: ${totalUnidades}`;
      const textX1 = Math.round((width - ctx.measureText(texto1).width) / 2);
      const textY1 = height / 2 - 15;
      ctx.fillText(texto1, textX1, textY1);

      // Estilo para dinero
      ctx.font = "bold 18px Arial";
      ctx.fillStyle = "#007bff"; // azul moderno
      const texto2 = `💰 $${totalDinero}`;
      const textX2 = Math.round((width - ctx.measureText(texto2).width) / 2);
      const textY2 = height / 2 + 15;
      ctx.fillText(texto2, textX2, textY2);

      ctx.save();
    }
  };

  return (
    <div style={{ width: "420px", margin: "20px auto", textAlign: "center" }}>
      <h3 style={{ fontFamily: "Arial, sans-serif", color: "#444" }}>📊 Ventas del día</h3>
      {ventasDia.length > 0 ? (
        <Doughnut data={data} plugins={[centerTextPlugin]} />
      ) : (
        <p style={{ color: "#888" }}>No hay ventas registradas hoy</p>
      )}
    </div>
  );
}

export default VentasGrafico;
