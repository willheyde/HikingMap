import apiClient from "./client";

/**
 * HIKES
 */

export const listHikes = async () => {
  const res = await apiClient.get("/hikes/list");
  return res.data;
};

export const getHikeById = async (hikeId) => {
  const res = await apiClient.get(`/hikes/get/${hikeId}`);
  return res.data;
};

export const createHike = async (hikeData) => {
  const res = await apiClient.post("/hikes/create", hikeData);
  return res.data;
};

export const updateHike = async (hikeId, hikeData) => {
  const res = await apiClient.put(`/hikes/update/${hikeId}`, hikeData);
  return res.data;
};

export const deleteHike = async (hikeId) => {
  await apiClient.delete(`/hikes/delete/${hikeId}`);
};

export const searchHikes = async (filters = {}) => {
  const res = await apiClient.get("/hikes/search", {
    params: filters,
  });
  console.log(res.data);
  return res.data;
};
