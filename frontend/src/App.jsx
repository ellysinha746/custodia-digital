import { Routes, Route } from "react-router-dom";
import Login from "./pages/Login";
import Casos from "./pages/Casos";
import CasoDetalle from "./pages/CasoDetalle";
import Auditoria from "./pages/Auditoria";
import Papelera from "./pages/Papelera";
import Alertas from "./pages/Alertas";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Login />} />
      <Route path="/casos" element={<Casos />} />
      <Route path="/casos/:id" element={<CasoDetalle />} />
      <Route path="/auditoria" element={<Auditoria />} />
      <Route path="/papelera" element={<Papelera />} />
      <Route path="/alertas" element={<Alertas />} />
    </Routes>
  );
}