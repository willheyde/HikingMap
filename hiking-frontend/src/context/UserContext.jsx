import { createContext, useContext, useState, useEffect } from "react";
import * as userService from "../api/usersService";

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

  // Check for existing session on mount
  useEffect(() => {
    const storedUser = localStorage.getItem("hike_user");
    if (storedUser) {
      try {
        const parsed = JSON.parse(storedUser);
        setUser(parsed);
        setItems(parsed.items || []);
      } catch (err) {
        console.error("Failed to parse stored user:", err);
        localStorage.removeItem("hike_user");
        setAuthModalOpen(true);
      }
    } else {
      setAuthModalOpen(true);
    }
  }, []);

  // --- NEW: Auto-fetch location if null ---
  useEffect(() => {
    // Only run if user is logged in, not loading, and location is strictly null/undefined
    if (user && !loadingLocation && !user.home_location) {
      console.log("Home location missing, attempting auto-update...");
      updateLocation();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]); // We intentionally depend on user to check the home_location property

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

  const login = async (email, password) => {
    setLoading(true);
    setError(null);
    try {
      const loggedInUser = await userService.loginUser({ email, password });
      setUser(loggedInUser);
      setItems(loggedInUser.items || []);
      localStorage.setItem("hike_user", JSON.stringify(loggedInUser));
      setAuthModalOpen(false);
      return loggedInUser;
    } catch (err) {
      const errorMsg = err.response?.data?.detail || "Invalid email or password";
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
    setAuthModalOpen(true);
  };

  const createUser = async (userData) => {
    setLoading(true);
    setError(null);
    try {
      const created = await userService.createUser(userData);
      setUser(created);
      setItems(created.items || []);
      localStorage.setItem("hike_user", JSON.stringify(created));
      setAuthModalOpen(false);
      return created;
    } catch (err) {
      let errorMsg = "Failed to create user";
      if (err.response?.status === 422) {
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
    } finally {
      setLoading(false);
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
    loadingLocation, // Exported so Profile can use it
    updateLocation,  // Exported so Profile can call it manually
    login,
    logout,
    createUser,
    addItem,
    deleteItem,
    addItemsBatch,
  };

  return (
    <UserContext.Provider value={value}>
      {children}
    </UserContext.Provider>
  );
};