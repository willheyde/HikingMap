import { createContext, useContext, useState } from "react";
import * as hikeService from "../api/hikesService";

const HikeContext = createContext(null);

export const useHikes = () => {
  return useContext(HikeContext);
};

export const HikeProvider = ({ children }) => {
  const [hikes, setHikes] = useState([]);
  const [selectedHike, setSelectedHike] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // -------------------------
  // Hike actions
  // -------------------------

  const loadHikes = async () => {
    setLoading(true);
    try {
      const data = await hikeService.listHikes();
      setHikes(data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadHikeById = async (hikeId) => {
    setLoading(true);
    try {
      const hike = await hikeService.getHikeById(hikeId);
      setSelectedHike(hike);
      return hike;
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const searchHikes = async (filters) => {
    setLoading(true);
    try {
      const results = await hikeService.searchHikes(filters);
      setHikes(results);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const selectHike = (hike) => {
    setSelectedHike(hike);
  };

  const clearSelectedHike = () => {
    setSelectedHike(null);
  };

  // -------------------------
  // Context value
  // -------------------------

  const value = {
    hikes,
    selectedHike,
    loading,
    error,
    loadHikes,
    loadHikeById,
    searchHikes,
    selectHike,
    clearSelectedHike,
  };

  return (
    <HikeContext.Provider value={value}>
      {children}
    </HikeContext.Provider>
  );
};
