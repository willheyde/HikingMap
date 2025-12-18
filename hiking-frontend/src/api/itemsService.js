import apiClient from "./client";

/**
 * ITEMS
 */

export const createItem = async (itemData) => {
  const res = await apiClient.post("/items/", itemData);
  return res.data;
};

export const getItemById = async (itemId) => {
  const res = await apiClient.get(`/items/${itemId}`);
  return res.data;
};

export const listItems = async () => {
  const res = await apiClient.get("/items/");
  return res.data;
};

export const deleteItem = async (itemId) => {
  await apiClient.delete(`/items/${itemId}`);
};
