import axios from "axios";
import { useState } from "react";

function Login({ setUsuario }) {
  const [nombre, setNombre] = useState("");
  const [password, setPassword] = useState("");

  const handleLogin = async () => {
    try {
      const res = await axios.post("http://localhost:8000/login", {
        nombre,
        password,
      });
      console.log("Respuesta backend:", res.data);
      setUsuario(res.data); // aquí guardas el usuario en App.jsx
    } catch (err) {
      console.error("Error en login:", err.response?.data || err.message);
      alert("Credenciales inválidas");
    }
  };

  return (
    <div>
      <input
        type="text"
        placeholder="Usuario"
        value={nombre}
        onChange={(e) => setNombre(e.target.value)}
      />
      <input
        type="password"
        placeholder="Contraseña"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <button onClick={handleLogin}>Ingresar</button>
    </div>
  );
}

export default Login;
