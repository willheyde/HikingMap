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

// Reverted: backend uses a custom LoginRequest Pydantic model (email + password as JSON),
// NOT FastAPI's OAuth2PasswordRequestForm, so plain JSON is correct here.
export const loginUser = async (credentials) => {
  const res = await apiClient.post("/users/login", credentials);
  return res.data;
};

/**
 * AUTH HEADER HELPERS
 */
export const setAuthHeader = (token) => {
  apiClient.defaults.headers.common["Authorization"] = `Bearer ${token}`;
};

export const clearAuthHeader = () => {
  delete apiClient.defaults.headers.common["Authorization"];
};

/**
 * USER ITEMS
 */
export const getUserItems = async (userId) => {
  const res = await apiClient.get(`/users/${userId}/items`);
  return res.data;
};

// Sends { item_id } to match the new ItemAdd schema on the backend.
export const addUserItem = async (userId, itemId) => {
  const res = await apiClient.post(`/users/${userId}/items`, { item_id: itemId });
  return res.data; // returns full updated list
};

// Sends { item_ids: [...] } to match the new ItemsBatchAdd schema.
export const addUserItemsBatch = async (userId, itemIds) => {
  const res = await apiClient.post(`/users/${userId}/items/batch`, { item_ids: itemIds });
  return res.data; // returns full updated list
};

// Path now uses item UUID, matching /{user_id}/items/{item_id} on the backend.
export const deleteUserItem = async (userId, itemId) => {
  await apiClient.delete(`/users/${userId}/items/${itemId}`);
};

// Free-text "I have this" gear: a functional category (+ optional level), not a
// catalog item_id. Matches the GearAdd schema on POST /users/:id/gear.
// gear = { name, gear_category, level?, weight?, cost?, temp_rating_f? }
export const createUserGear = async (userId, gear) => {
  const res = await apiClient.post(`/users/${userId}/gear`, gear);
  return res.data; // the created item dict (includes id)
};