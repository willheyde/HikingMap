import apiClient from "./client";

/**
 * TRIPS
 */

export const createTrip = async (tripData, userId) => {
  const res = await apiClient.post("/trips/", null, {
    params: { user_id: userId },
    data: tripData,
  });
  return res.data;
};

export const getTripById = async (tripId) => {
  const res = await apiClient.get(`/trips/${tripId}`);
  return res.data;
};

export const deleteTrip = async (tripId) => {
  await apiClient.delete(`/trips/${tripId}`);
};
