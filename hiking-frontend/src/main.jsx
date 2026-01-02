import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { HikeProvider } from "./context/HikeContext";
import "./styles/global.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <HikeProvider>
        <App />
      </HikeProvider>
    </BrowserRouter>
  </React.StrictMode>
);
