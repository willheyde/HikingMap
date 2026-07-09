import { createContext, useContext } from "react";

// Context object + hook, split out from the provider (TripContext.jsx) so the
// provider file exports only a component (react-refresh/only-export-components).
export const TripContext = createContext(null);

export const useTrip = () => useContext(TripContext);
