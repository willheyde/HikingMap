import apiClient from "./client";

/**
 * USERS
 */
export const createUser = async (userData) => {
  const res = await apiClient.post("/users/", userData);
  return res.data;
};

export const getUserById = async (userId) => {
  const res = await apiClient.get(`/users/${userId}`);
  return res.data;
};

export const listUsers = async () => {
  const res = await apiClient.get("/users/");
  return res.data;
};

export const updateUser = async (userId, userData) => {
  const res = await apiClient.put(`/users/${userId}`, userData);
  return res.data;
};

export const deleteUser = async (userId) => {
  await apiClient.delete(`/users/${userId}`);
};

export const loginUser = async (credentials) => {
  const res = await apiClient.post("/users/login", credentials);
  return res.data;
};

/**
 * USER ITEMS (Updated for ID-based logic)
 */

export const getUserItems = async (userId) => {
  const res = await apiClient.get(`/users/${userId}/items`);
  return res.data;
};

// 1. Add Single Item by ID
// Backend expects: { "item_id": "uuid..." }
export const addUserItem = async (userId, itemId) => {
  const payload = { item_id: itemId };
  const res = await apiClient.post(`/users/${userId}/items`, payload);
  // Backend now returns the FULL updated list of items
  return res.data;
};

// 2. Add Batch Items by IDs
// Backend expects: ["uuid1", "uuid2"]
export const addUserItemsBatch = async (userId, itemIds) => {
  const res = await apiClient.post(`/users/${userId}/items/batch`, itemIds);
  // Backend now returns the FULL updated list of items
  return res.data;
};

// 3. Delete Item by ID (not index)
export const deleteUserItem = async (userId, itemId) => {
  await apiClient.delete(`/users/${userId}/items/${itemId}`);
};