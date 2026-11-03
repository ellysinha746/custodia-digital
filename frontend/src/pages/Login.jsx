import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import { olvidarUsuario } from "../permisos";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const { data } = await api.post("/auth/login", { email, password });
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      olvidarUsuario(); // Sprint 5: que se vuelva a leer el rol del usuario que entra
      navigate("/casos");
    } catch (err) {
      // Sprint 5: un usuario desactivado recibe 403 con su propio mensaje
      setError(err.response?.status === 403 ? err.response.data.detail : "Email o contraseña incorrectos.");
    }
  };

  return (
    <div style={{ maxWidth: 360, margin: "80px auto", fontFamily: "sans-serif" }}>
      <h2>Cadena de Custodia</h2>
      <p>Inicia sesión para continuar</p>
      <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12 }}>
        <input
          type="email"
          placeholder="Correo"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Contraseña"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <button type="submit">Ingresar</button>
        {error && <span style={{ color: "crimson" }}>{error}</span>}
      </form>
    </div>
  );
}