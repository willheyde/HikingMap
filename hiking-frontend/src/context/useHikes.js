import { createContext, useContext } from "react";

// Context object + hook, split out from the provider (HikeContext.jsx) so the
// provider file exports only a component (react-refresh/only-export-components).
export const HikeContext = createContext(null);

export const useHikes = () => useContext(HikeContext);
