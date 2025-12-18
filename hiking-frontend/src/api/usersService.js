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

/**
 * USER ITEMS
 */

export const getUserItems = async (userId) => {
  const res = await apiClient.get(`/users/${userId}/items`);
  return res.data;
};

export const addUserItem = async (userId, item) => {
  const res = await apiClient.post(`/users/${userId}/items`, item);
  return res.data;
};

export const deleteUserItem = async (userId, itemIndex) => {
  await apiClient.delete(`/users/${userId}/items/${itemIndex}`);
};
