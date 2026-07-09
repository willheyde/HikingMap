import { createContext, useContext } from "react";

// Context object + hook, split out from the provider (ItemContext.jsx) so the
// provider file exports only a component (react-refresh/only-export-components).
export const ItemContext = createContext(null);

export const useItems = () => useContext(ItemContext);
