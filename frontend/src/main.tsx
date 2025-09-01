import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import { BrowserRouter, Routes, Route } from "react-router";
import App from "./App.tsx";
import { ThemeProvider } from "./providers/ThemeProvider.tsx";

createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <StrictMode>
      <ThemeProvider>
        <Routes>
          <Route index element={<App />} />
          {/* <Route path="about" element={<About />} />

        <Route path="login" element={<Login />} /> */}
        </Routes>
      </ThemeProvider>
    </StrictMode>
  </BrowserRouter>
);
