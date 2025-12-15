import api from "./client";

export const getUserItems = (userId) =>
  api.get(`/users/${userId}/items`);

export const addUserItem = (userId, item) =>
  api.post(`/users/${userId}/items`, item);

export const removeUserItem = (userId, itemId) =>
  api.delete(`/users/${userId}/items/${itemId}`);
export const updateUserItem = (userId, itemId, itemData) =>
  api.put(`/users/${userId}/items/${itemId}`, itemData);
export const getAllItems = () =>
  api.get("/items");
export const getItemById = (itemId) =>
  api.get(`/items/${itemId}`);
