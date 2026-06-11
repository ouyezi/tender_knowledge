import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider } from "antd";
import "antd/dist/reset.css";
import App from "./App";
import { KBProvider } from "./layout/KBContext";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider>
      <BrowserRouter>
        <KBProvider>
          <App />
        </KBProvider>
      </BrowserRouter>
    </ConfigProvider>
  </React.StrictMode>,
);
