import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import { BrowserRouter, Routes, Route } from "react-router";
import App from "./App.tsx";

createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <StrictMode>
      <Routes>
        <Route index element={<App />} />
        {/* <Route path="about" element={<About />} />

        <Route path="login" element={<Login />} /> */}
      </Routes>
    </StrictMode>
  </BrowserRouter>
);
