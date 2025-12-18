import { createContext, useContext, useState } from "react";
import * as tripService from "../api/tripService";

const TripContext = createContext(null);

export const useTrip = () => {
  return useContext(TripContext);
};

export const TripProvider = ({ children }) => {
  const [trip, setTrip] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // -------------------------
  // Trip actions
  // -------------------------

  const createTrip = async (tripData, userId) => {
    setLoading(true);
    try {
      const created = await tripService.createTrip(tripData, userId);
      setTrip(created);
      return created;
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const loadTrip = async (tripId) => {
    setLoading(true);
    try {
      const fetched = await tripService.getTripById(tripId);
      setTrip(fetched);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const deleteTrip = async (tripId) => {
    setLoading(true);
    try {
      await tripService.deleteTrip(tripId);
      setTrip(null);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // -------------------------
  // Context value
  // -------------------------

  const value = {
    trip,
    loading,
    error,
    createTrip,
    loadTrip,
    deleteTrip,
  };

  return (
    <TripContext.Provider value={value}>
      {children}
    </TripContext.Provider>
  );
};
