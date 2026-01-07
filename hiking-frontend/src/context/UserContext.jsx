import { createContext, useContext, useState, useEffect } from "react";
import * as userService from "../api/usersService";

const UserContext = createContext(null);

export const useUser = () => {
  return useContext(UserContext);
};

export const UserProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [globalUserLocation, setGlobalUserLocation] = useState(null);
  const [authModalOpen, setAuthModalOpen] = useState(false);

  // Check for existing session on mount
  useEffect(() => {
    const storedUser = localStorage.getItem("hike_user");
    if (storedUser) {
      try {
        const parsed = JSON.parse(storedUser);
        setUser(parsed);
        setItems(parsed.items || []);
      } catch (err) {
        console.error("Failed to parse stored user:", err);
        localStorage.removeItem("hike_user");
        setAuthModalOpen(true);
      }
    } else {
      setAuthModalOpen(true);
    }
  }, []);

  // Helper to sync state changes to LocalStorage
  const updateLocalUser = (updatedUser) => {
    setUser(updatedUser);
    localStorage.setItem("hike_user", JSON.stringify(updatedUser));
  };

  const login = async (email, password) => {
    setLoading(true);
    setError(null);
    try {
      const loggedInUser = await userService.loginUser({ email, password });
      setUser(loggedInUser);
      setItems(loggedInUser.items || []);
      localStorage.setItem("hike_user", JSON.stringify(loggedInUser));
      setAuthModalOpen(false);
      return loggedInUser;
    } catch (err) {
      const errorMsg = err.response?.data?.detail || "Invalid email or password";
      setError(errorMsg);
      throw new Error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    setUser(null);
    setItems([]);
    localStorage.removeItem("hike_user");
    setAuthModalOpen(true);
  };

  const createUser = async (userData) => {
    setLoading(true);
    setError(null);
    try {
      const created = await userService.createUser(userData);
      setUser(created);
      setItems(created.items || []);
      localStorage.setItem("hike_user", JSON.stringify(created));
      setAuthModalOpen(false);
      return created;
    } catch (err) {
      // (Your existing robust error handling logic here...)
      let errorMsg = "Failed to create user";
      if (err.response?.status === 422) {
         const detail = err.response.data.detail;
         errorMsg = Array.isArray(detail) 
            ? detail.map(e => `${e.loc[1]}: ${e.msg}`).join(" | ") 
            : String(detail);
      } else if (err.response?.data?.detail) {
         errorMsg = err.response.data.detail;
      } else if (err.message) {
         errorMsg = err.message;
      }
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  // --- UPDATED ITEM METHODS ---

  // Adds a single item by ID
  const addItem = async (userId, itemId) => {
    setLoading(true);
    try {
      // API now returns the FULL LIST of items
      const updatedItemsList = await userService.addUserItem(userId, itemId);
      
      // 1. Update Items State directly
      setItems(updatedItemsList);
      
      // 2. Sync User object + LocalStorage
      if (user) {
        updateLocalUser({ ...user, items: updatedItemsList });
      }
      
      return updatedItemsList;
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // Adds multiple items by IDs
  const addItemsBatch = async (userId, itemIds) => {
    setLoading(true);
    try {
      // API now returns the FULL LIST of items
      const updatedItemsList = await userService.addUserItemsBatch(userId, itemIds);
      
      // 1. Update Items State directly
      setItems(updatedItemsList);
      
      // 2. Sync User object + LocalStorage
      if (user) {
        updateLocalUser({ ...user, items: updatedItemsList });
      }
      
      return updatedItemsList;
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // Deletes item by ID (changed from Index)
  const deleteItem = async (userId, itemId) => {
    setLoading(true);
    try {
      await userService.deleteUserItem(userId, itemId);
      
      // 1. Filter out the deleted item from current state
      const updatedItems = items.filter((item) => item.id !== itemId);
      setItems(updatedItems);
      
      // 2. Sync User object + LocalStorage
      if (user) {
        updateLocalUser({ ...user, items: updatedItems });
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const value = {
    user,
    items,
    loading,
    error,
    authModalOpen,
    setAuthModalOpen,
    login,
    logout,
    createUser,
    addItem,        // Now takes (userId, itemId)
    deleteItem,     // Now takes (userId, itemId)
    addItemsBatch,  // Now takes (userId, [itemId, itemId])
    globalUserLocation, 
    setGlobalUserLocation
  };

  return (
    <UserContext.Provider value={value}>
      {children}
    </UserContext.Provider>
  );
};