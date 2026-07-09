import { useState, useCallback } from "react";
import * as itemService from "../api/itemService";
import { ItemContext } from "./useItems";

export const ItemProvider = ({ children }) => {
  const [items, setItems]   = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState(null);

  // ─── Helpers ────────────────────────────────────────────────────────────────

  const withLoading = useCallback(async (fn) => {
    setLoading(true);
    setError(null);
    try {
      return await fn();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      setError(msg);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // ─── Read ────────────────────────────────────────────────────────────────────

  /**
   * Load all items into state, optionally filtered by type.
   * e.g. loadItems("backpack") populates state with only backpacks.
   * Call with no argument to load everything.
   */
  const loadItems = useCallback((itemType = null) =>
    withLoading(async () => {
      const fetched = await itemService.listItems(itemType);
      setItems(fetched);
      return fetched;
    }), [withLoading]);

  const getItem = useCallback((itemId) =>
    withLoading(() => itemService.getItemById(itemId)), [withLoading]);

  const getItemByName = useCallback((name) =>
    withLoading(() => itemService.getItemByName(name)), [withLoading]);

  // ─── Create ──────────────────────────────────────────────────────────────────

  /**
   * Create an item of any type.
   * @param {string} itemType  e.g. "backpack", "footwear", "shelter" …
   * @param {object} data      Fields for that type
   */
  const createItem = useCallback((itemType, data) =>
    withLoading(async () => {
      const created = await itemService.createItem(itemType, data);
      setItems((prev) => [...prev, created]);
      return created;
    }), [withLoading]);

  // ─── Update ──────────────────────────────────────────────────────────────────

  const updateItemImage = useCallback((itemId, imageUrl) =>
    withLoading(async () => {
      const updated = await itemService.updateItemImage(itemId, imageUrl);
      setItems((prev) => prev.map((i) => (i.id === itemId ? updated : i)));
      return updated;
    }), [withLoading]);

  // ─── Delete ──────────────────────────────────────────────────────────────────

  const deleteItem = useCallback((itemId) =>
    withLoading(async () => {
      await itemService.deleteItem(itemId);
      setItems((prev) => prev.filter((i) => i.id !== itemId));
    }), [withLoading]);

  // ─── Context value ───────────────────────────────────────────────────────────

  return (
    <ItemContext.Provider value={{
      items,
      loading,
      error,
      loadItems,
      getItem,
      getItemByName,
      createItem,
      updateItemImage,
      deleteItem,
    }}>
      {children}
    </ItemContext.Provider>
  );
};