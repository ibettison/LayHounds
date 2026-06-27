import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import "@/App.css";

import Admin from "@/pages/Admin";
import Licence from "@/pages/Licence";
import Simulator from "@/pages/Simulator";

export default function App() {
  return (
    <BrowserRouter>
      <Toaster theme="light" position="bottom-right" richColors expand={false} closeButton={false} toastOptions={{ style: { maxWidth: 360 } }} />
      <Routes>
        <Route path="/" element={<Simulator />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="/licence" element={<Licence />} />
        <Route path="/app" element={<Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
