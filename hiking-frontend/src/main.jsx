import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { HikeProvider } from "./context/HikeContext";
import { UserProvider } from "./context/UserContext"; // Import this
import { TripProvider } from "./context/TripContext"; // Import this
import "./styles/global.css";
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      {/* UserProvider wraps everything so user data is global */}
      <UserProvider>
        <HikeProvider>
          <TripProvider>
            <App />
          </TripProvider>
        </HikeProvider>
      </UserProvider>
    </BrowserRouter>
  </React.StrictMode>
);