import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import "@/App.css";

import Landing from "@/pages/Landing";
import Simulator from "@/pages/Simulator";
import Terms from "@/pages/Terms";
import Privacy from "@/pages/Privacy";
import Refund from "@/pages/Refund";
import { CheckoutSuccess, CheckoutCancel } from "@/pages/Checkout";

export default function App() {
  return (
    <BrowserRouter>
      <Toaster theme="light" position="bottom-right" richColors expand={false} closeButton={false} toastOptions={{ style: { maxWidth: 360 } }} />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<Simulator />} />
        <Route path="/terms" element={<Terms />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/refund" element={<Refund />} />
        <Route path="/checkout/success" element={<CheckoutSuccess />} />
        <Route path="/checkout/cancel" element={<CheckoutCancel />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
