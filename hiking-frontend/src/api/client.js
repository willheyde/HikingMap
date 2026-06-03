// client.js
import axios from "axios";

const apiClient = axios.create({
  baseURL: "http://localhost:8000",
});

// Attach token to every request automatically
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("hike_token"); // or wherever you store it
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default apiClient;