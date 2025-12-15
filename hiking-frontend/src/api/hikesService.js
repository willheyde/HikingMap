import api from "./client";

export const getHikes = (filters) =>
  api.get("/hikes", { params: filters });

export const getHikeById = (id) =>
  api.get(`/hikes/${id}`);
export const createHike = (hikeData) =>
  api.post("/hikes", hikeData);
export const updateHike = (id, hikeData) =>
  api.put(`/hikes/${id}`, hikeData);
export const deleteHike = (id) =>
  api.delete(`/hikes/${id}`);
export const getUserHikes = (userId) =>
  api.get(`/hikes/user/${userId}`);
export const saveHikeForUser = (userId, hikeId) =>
  api.post(`/users/${userId}/hikes/${hikeId}`);

export const removeUserHike = (userId, hikeId) =>
  api.delete(`/users/${userId}/hikes/${hikeId}`);
