import { createContext, useContext } from "react";

// The context object + its consumer hook live here, separate from the provider
// component (UserContext.jsx). Keeping non-component exports out of the provider
// file is what satisfies react-refresh/only-export-components (Fast Refresh).
export const UserContext = createContext(null);

export const useUser = () => useContext(UserContext);
