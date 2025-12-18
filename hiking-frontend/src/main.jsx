import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App.jsx";

// Global styles
import "./styles/global.css";

// Context providers
import { UserProvider } from "./context/UserContext";
import { InventoryProvider } from "./context/ItemContext.jsx";
import { HikeProvider } from "./context/HikeContext";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <UserProvider>
        <ItemProvider>
          <HikeProvider>
            <App />
          </HikeProvider>
        </ItemProvider>
      </UserProvider>
    </BrowserRouter>
  </React.StrictMode>
);
