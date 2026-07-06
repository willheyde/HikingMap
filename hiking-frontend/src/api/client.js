// client.js
import axios from "axios";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
});

// Attach token to every request automatically
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("hike_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Sign the user out if their token is expired/invalid on any protected route
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const isAuthEndpoint = error.config?.url?.includes("/users/login");

    if (error.response?.status === 401 && !isAuthEndpoint) {
      localStorage.removeItem("hike_token");
      delete apiClient.defaults.headers.common["Authorization"];
      // Hard redirect resets all React state cleanly
      window.location.href = "/";
    }

    return Promise.reject(error);
  }
);

export default apiClient;