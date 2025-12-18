import apiClient from "./client";

/**
 * HIKES
 */

export const listHikes = async () => {
  const res = await apiClient.get("/hikes/");
  return res.data;
};

export const getHikeById = async (hikeId) => {
  const res = await apiClient.get(`/hikes/${hikeId}`);
  return res.data;
};

export const createHike = async (hikeData) => {
  const res = await apiClient.post("/hikes/", hikeData);
  return res.data;
};

export const updateHike = async (hikeId, hikeData) => {
  const res = await apiClient.put(`/hikes/${hikeId}`, hikeData);
  return res.data;
};

export const deleteHike = async (hikeId) => {
  await apiClient.delete(`/hikes/${hikeId}`);
};

export const searchHikes = async (filters = {}) => {
  const res = await apiClient.get("/hikes/search", {
    params: filters,
  });
  return res.data;
};
