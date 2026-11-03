import { Routes, Route } from "react-router-dom";
import Login from "./pages/Login";
import Casos from "./pages/Casos";
import CasoDetalle from "./pages/CasoDetalle";
import Auditoria from "./pages/Auditoria";
import Papelera from "./pages/Papelera";
import Alertas from "./pages/Alertas";
import Dashboard from "./pages/Dashboard";
import Usuarios from "./pages/Usuarios";
import Peritos from "./pages/Peritos";
import PerfilPerito from "./pages/PerfilPerito";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Login />} />
      <Route path="/casos" element={<Casos />} />
      <Route path="/casos/:id" element={<CasoDetalle />} />
      <Route path="/auditoria" element={<Auditoria />} />
      <Route path="/papelera" element={<Papelera />} />
      <Route path="/alertas" element={<Alertas />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/usuarios" element={<Usuarios />} />
      <Route path="/peritos" element={<Peritos />} />
      <Route path="/peritos/:id" element={<PerfilPerito />} />
      <Route path="/perfil" element={<PerfilPerito />} />
    </Routes>
  );
}