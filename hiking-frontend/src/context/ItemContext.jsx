import { createContext, useContext, useState } from "react";
import {
  getUserItems,
  addUserItem,
  removeUserItem,
  updateUserItem,
  getAllItems,
  getItemById
} from "../api/itemsService";

const InventoryContext = createContext();

export const InventoryProvider = ({ children }) => {
  const [items, setItems] = useState([]);        // user's items
  const [allItems, setAllItems] = useState([]);  // master catalog
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // 🔹 Fetch user's inventory
  const fetchUserItems = async (userId) => {
    setLoading(true);
    try {
      const res = await getUserItems(userId);
      setItems(res.data);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  // 🔹 Fetch master item list
  const fetchAllItems = async () => {
    setLoading(true);
    try {
      const res = await getAllItems();
      setAllItems(res.data);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  // 🔹 Fetch single item (rarely needed, but useful)
  const fetchItemById = async (itemId) => {
    setLoading(true);
    try {
      const res = await getItemById(itemId);
      return res.data;
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  // 🔹 Add item to user
  const addItem = async (userId, item) => {
    const res = await addUserItem(userId, item);
    setItems((prev) => [...prev, res.data]);
    return res.data;
  };

  // 🔹 Update user item
  const updateItem = async (userId, itemId, itemData) => {
    const res = await updateUserItem(userId, itemId, itemData);
    setItems((prev) =>
      prev.map((i) => (i.id === itemId ? res.data : i))
    );
    return res.data;
  };

  // 🔹 Remove item from user
  const removeItem = async (userId, itemId) => {
    await removeUserItem(userId, itemId);
    setItems((prev) => prev.filter((i) => i.id !== itemId));
  };

  return (
    <InventoryContext.Provider
      value={{
        items,
        allItems,
        loading,
        error,
        fetchUserItems,
        fetchAllItems,
        fetchItemById,
        addItem,
        updateItem,
        removeItem,
      }}
    >
      {children}
    </InventoryContext.Provider>
  );
};

export const useInventory = () => useContext(InventoryContext);
