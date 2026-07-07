import { createContext, useContext, useState, useEffect, useRef } from "react";
import * as userService from "../api/usersService";

import axios from "axios";

const UserContext = createContext(null);

export const useUser = () => {
  return useContext(UserContext);
};

export const UserProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // New state for location handling
  const [loadingLocation, setLoadingLocation] = useState(false);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const locationAttemptedRef = useRef(false);

  useEffect(() => {
    if (user && !locationAttemptedRef.current && !user.home_location) {
      locationAttemptedRef.current = true; // mark attempted regardless of outcome
      updateLocation();
    }
  }, [user]);
  // Check for existing session on mount
  useEffect(() => {
    const storedUser = localStorage.getItem("hike_user");
    const storedToken = localStorage.getItem("hike_token");  // add this

    if (storedUser && storedToken) {
      try {
        userService.setAuthHeader(storedToken);             // add this
        const parsed = JSON.parse(storedUser);
        setUser(parsed);
        setItems(parsed.items || []);
      } catch (err) {
        localStorage.removeItem("hike_user");
        localStorage.removeItem("hike_token");             // add this
        setAuthModalOpen(true);
      }
    } else {
      setAuthModalOpen(true);
    }
  }, []);

  // Helper to sync state changes to LocalStorage
  const updateLocalUser = (updatedUser) => {
    setUser(updatedUser);
    localStorage.setItem("hike_user", JSON.stringify(updatedUser));
  };

  // --- NEW: Location Update Logic ---
  const updateLocation = () => {
    if (!navigator.geolocation) {
      setError("Geolocation is not supported by your browser.");
      return;
    }

    setLoadingLocation(true);

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const { latitude, longitude } = position.coords;

          // 1. Reverse Geocode (Get City Name)
          // Using OpenStreetMap Nominatim API (Free, requires User-Agent)
          let locationName = `${latitude.toFixed(2)}, ${longitude.toFixed(2)}`;
          try {
            const geoRes = await fetch(
              `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&zoom=10`,
              { headers: { "User-Agent": "HikePlannerApp/1.0" } }
            );
            const geoData = await geoRes.json();
            // Try to construct a readable name: "Raleigh, North Carolina"
            if (geoData.address) {
              const city = geoData.address.city || geoData.address.town || geoData.address.village;
              const state = geoData.address.state;
              if (city && state) locationName = `${city}, ${state}`;
              else if (state) locationName = state;
            }
          } catch (geoErr) {
            console.warn("Reverse geocoding failed, using coords", geoErr);
          }

          // 2. Prepare Data
          const locationData = {
            name: locationName,
            lat: latitude,
            lon: longitude,
          };

          // 3. Update User in Backend
          // We assume updateUser accepts partial updates
          const updatedUser = await userService.updateUser(user.id, {
            home_location: locationData,
          });

          // 4. Update Context & LocalStorage
          updateLocalUser(updatedUser);
          
        } catch (err) {
          console.error("Failed to update location:", err);
          setError("Failed to save location data.");
        } finally {
          setLoadingLocation(false);
        }
      },
      (geoError) => {
        console.error("Geolocation permission denied or failed:", geoError);
        setLoadingLocation(false);
        // We don't set a global error here to avoid annoying the user if they simply denied permission
      }
    );
  };

  // UserContext.jsx - update your login function

  const login = async (email, password) => {
  setLoading(true);
  setError(null);
  try {
    const tokenResponse = await userService.loginUser({ email, password });
    localStorage.setItem("hike_token", tokenResponse.access_token);
    localStorage.setItem("hike_user_id", tokenResponse.user_id);
    userService.setAuthHeader(tokenResponse.access_token);
    const fullUser = await userService.getUserById(tokenResponse.user_id);
    setUser(fullUser);
    setItems(fullUser.items || []);
    localStorage.setItem("hike_user", JSON.stringify(fullUser));
    setAuthModalOpen(false);
    return fullUser;
  } catch (err) {
    const errorMsg = err.response?.status === 401
      ? "Incorrect email or password, please try again."
      : "Something went wrong. Please try again.";
    setError(errorMsg);
    throw new Error(errorMsg);
  } finally {
    setLoading(false);
  }
};

  const logout = () => {
    setUser(null);
    setItems([]);
    localStorage.removeItem("hike_user");
    localStorage.removeItem("hike_token");
    localStorage.removeItem("hike_user_id");
    userService.clearAuthHeader(); 
    setAuthModalOpen(true);
  };

  const createUser = async (userData) => {
    setLoading(true);
    setError(null);
    try {
      await userService.createUser(userData);
      await login(userData.email, userData.password);
      setAuthModalOpen(false);
      } catch (err) {
          let errorMsg = "Failed to create user";
          if (err.response?.status === 409) {
            errorMsg = "An account with that email already exists.";
          } else if (err.response?.status === 422) {
            const detail = err.response.data.detail;
            errorMsg = Array.isArray(detail)
              ? detail.map(e => `${e.loc[1]}: ${e.msg}`).join(" | ")
              : String(detail);
          } else if (err.response?.data?.detail) {
            errorMsg = err.response.data.detail;
          } else if (err.message) {
            errorMsg = err.message;
          }
          setError(errorMsg);
          throw err; // ← this is what was missing
      } finally {
        setLoading(false);
        }
  };
    const setGlobalUserLocation = async (locationData) => {
      if (!user) return;

      try {
        // Update backend
        const updatedUser = await userService.updateUser(user.id, {
          home_location: locationData,
        });

        // Sync context + localStorage
        updateLocalUser(updatedUser);
      } catch (err) {
        console.error("Failed to set global user location:", err);
        setError("Failed to update user location.");
      }
    };
    const addItem = async (userId, itemId) => {
      setLoading(true);
      try {
        const updatedItemsList = await userService.addUserItem(userId, itemId);
        setItems(updatedItemsList);
        if (user) {
          updateLocalUser({ ...user, items: updatedItemsList });
        }
        return updatedItemsList;
      } catch (err) {
        setError(err.response?.data?.detail || err.message);
        throw err;
      } finally {
        setLoading(false);
      }
    };

  const addItemsBatch = async (userId, itemIds) => {
    setLoading(true);
    try {
      const updatedItemsList = await userService.addUserItemsBatch(userId, itemIds);
      setItems(updatedItemsList);
      if (user) {
        updateLocalUser({ ...user, items: updatedItemsList });
      }
      return updatedItemsList;
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // Pull the authoritative item list from the server and sync it into context +
  // localStorage. Used after gear is added outside the batch/catalog flow (the
  // onboarding wizard and the gear manager both create gear via POST /gear) and
  // on Profile mount, so newly-added generalized gear shows without a re-login.
  const refreshItems = async (userId) => {
    const id = userId || user?.id;
    if (!id) return [];
    try {
      const fresh = await userService.getUserItems(id);
      setItems(fresh);
      if (user) updateLocalUser({ ...user, items: fresh });
      return fresh;
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      return [];
    }
  };

  // Free-text "I have this" gear (functional category + optional level), created
  // via POST /users/:id/gear. Appends the created item to context so the profile
  // and manager update immediately.
  const createGear = async (userId, gear) => {
    setLoading(true);
    try {
      const created = await userService.createUserGear(userId, gear);
      setItems(prev => {
        const next = [...prev, created];
        if (user) updateLocalUser({ ...user, items: next });
        return next;
      });
      return created;
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const deleteItem = async (userId, itemId) => {
    setLoading(true);
    try {
      await userService.deleteUserItem(userId, itemId);
      const updatedItems = items.filter((item) => item.id !== itemId);
      setItems(updatedItems);
      if (user) {
        updateLocalUser({ ...user, items: updatedItems });
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const value = {
    user,
    items,
    loading,
    error,
    authModalOpen,
    setAuthModalOpen,
    setGlobalUserLocation,
    loadingLocation, // Exported so Profile can use it
    updateLocation,  // Exported so Profile can call it manually
    login,
    logout,
    createUser,
    addItem,
    deleteItem,
    addItemsBatch,
    refreshItems,
    createGear,
  };

  return (
    <UserContext.Provider value={value}>
      {children}
    </UserContext.Provider>
  );
};