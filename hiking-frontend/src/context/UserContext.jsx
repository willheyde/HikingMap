import { createContext, useContext, useState } from "react";
import * as userService from "../api/userService";

const UserContext = createContext(null);

export const useUser = () => {
  return useContext(UserContext);
};

export const UserProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // -------------------------
  // User actions
  // -------------------------

  const createUser = async (userData) => {
    setLoading(true);
    try {
      const created = await userService.createUser(userData);
      setUser(created);
      setItems(created.items || []);
      return created;
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const loadUser = async (userId) => {
    setLoading(true);
    try {
      const fetched = await userService.getUserById(userId);
      setUser(fetched);
      setItems(fetched.items || []);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const updateUser = async (userId, updates) => {
    setLoading(true);
    try {
      const updated = await userService.updateUser(userId, updates);
      setUser(updated);
      setItems(updated.items || []);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const deleteUser = async (userId) => {
    setLoading(true);
    try {
      await userService.deleteUser(userId);
      setUser(null);
      setItems([]);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  // -------------------------
  // Item actions
  // -------------------------

  const loadItems = async (userId) => {
    setLoading(true);
    try {
      const fetchedItems = await userService.getUserItems(userId);
      setItems(fetchedItems);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const addItem = async (userId, item) => {
    try {
      const created = await userService.addUserItem(userId, item);
      setItems((prev) => [...prev, created]);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      throw err;
    }
  };

  const deleteItem = async (userId, itemIndex) => {
    try {
      await userService.deleteUserItem(userId, itemIndex);
      setItems((prev) => prev.filter((_, i) => i !== itemIndex));
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      throw err;
    }
  };

  // -------------------------
  // Context value
  // -------------------------

  const value = {
    user,
    items,
    loading,
    error,
    createUser,
    loadUser,
    updateUser,
    deleteUser,
    loadItems,
    addItem,
    deleteItem,
  };

  return (
    <UserContext.Provider value={value}>
      {children}
    </UserContext.Provider>
  );
};
