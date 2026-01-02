import { createContext, useContext, useState } from "react";
import * as itemService from "../api/itemService";

const ItemContext = createContext(null);

export const useItems = () => {
  return useContext(ItemContext);
};

export const ItemProvider = ({ children }) => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // -------------------------
  // Item actions
  // -------------------------

  const loadItems = async () => {
    setLoading(true);
    try {
      const fetched = await itemService.listItems();
      setItems(fetched);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const getItem = async (itemId) => {
    setLoading(true);
    try {
      return await itemService.getItemById(itemId);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const createItem = async (itemData) => {
    setLoading(true);
    try {
      const created = await itemService.createItem(itemData);
      setItems((prev) => [...prev, created]);
      return created;
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const deleteItem = async (itemId) => {
    setLoading(true);
    try {
      await itemService.deleteItem(itemId);
      setItems((prev) => prev.filter((i) => i.id !== itemId));
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // -------------------------
  // Context value
  // -------------------------

  const value = {
    items,
    loading,
    error,
    loadItems,
    getItem,
    createItem,
    deleteItem,
  };

  return (
    <ItemContext.Provider value={value}>
      {children}
    </ItemContext.Provider>
  );
};
