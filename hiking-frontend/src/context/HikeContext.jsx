import { createContext, useContext, useState } from "react";
import {
  getHikes,
  getHikeById,
  getUserHikes,
  createHike,
  updateHike,
  deleteHike
} from "../api/hikesService";

const HikeContext = createContext();

export const HikeProvider = ({ children }) => {
  const [hikes, setHikes] = useState([]);
  const [selectedHike, setSelectedHike] = useState(null);
  const [userHikes, setUserHikes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // 🔹 Fetch filtered hikes (map view)
  const fetchHikes = async (filters = {}) => {
    setLoading(true);
    try {
      const res = await getHikes(filters);
      setHikes(res.data);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  // 🔹 Fetch all hikes (admin / debug)
  const fetchAllHikes = async () => {
    setLoading(true);
    try {
      const res = await getHikes();
      setHikes(res.data);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  // 🔹 Fetch single hike
  const fetchHikeById = async (id) => {
    setLoading(true);
    try {
      const res = await getHikeById(id);
      setSelectedHike(res.data);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  // 🔹 Fetch user-specific hikes
  const fetchUserHikes = async (userId) => {
    setLoading(true);
    try {
      const res = await getUserHikes(userId);
      setUserHikes(res.data);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  // 🔹 Admin / ingestion
  const addHike = async (hikeData) => {
    const res = await createHike(hikeData);
    setHikes((prev) => [...prev, res.data]);
    return res.data;
  };

  const editHike = async (id, hikeData) => {
    const res = await updateHike(id, hikeData);
    setHikes((prev) =>
      prev.map((h) => (h.id === id ? res.data : h))
    );
    return res.data;
  };

  const removeHike = async (id) => {
    await deleteHike(id);
    setHikes((prev) => prev.filter((h) => h.id !== id));
  };

  return (
    <HikeContext.Provider
      value={{
        hikes,
        selectedHike,
        userHikes,
        loading,
        error,
        fetchHikes,
        fetchAllHikes,
        fetchHikeById,
        fetchUserHikes,
        addHike,
        editHike,
        removeHike,
        setSelectedHike,
      }}
    >
      {children}
    </HikeContext.Provider>
  );
};

export const useHikes = () => useContext(HikeContext);
