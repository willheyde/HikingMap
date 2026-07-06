import { createContext, useContext, useState, useRef, useCallback } from "react";
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

  const searchAbortRef = useRef(null);

  const searchHikes = useCallback(async (filters) => {
    if (searchAbortRef.current) searchAbortRef.current.abort();
    const controller = new AbortController();
    searchAbortRef.current = controller;

    setLoading(true);
    try {
      const results = await hikeService.searchHikes(filters, controller.signal);
      setHikes(results);
    } catch (err) {
      if (axios.isCancel(err) || err.code === "ERR_CANCELED" || err.name === "CanceledError") return;
      setError(err.response?.data?.detail || err.message);
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);

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
