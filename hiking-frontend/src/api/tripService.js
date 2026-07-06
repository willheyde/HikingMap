import apiClient from "./client";

// ─── TRIPS CRUD ──────────────────────────────────────────────────────────────
// These hit your standard REST trips API (/trips/)

export const createTrip = async (tripData, userId) => {
  const res = await apiClient.post("/trips/", tripData, {
    params: { user_id: userId },
  });
  return res.data;
};

export const getTripById = async (tripId) => {
  const res = await apiClient.get(`/trips/${tripId}`);
  return res.data;
};

export const getUserTrips = async (userId) => {
  const res = await apiClient.get("/trips/", { params: { user_id: userId } });
  return res.data;
};

export const deleteTrip = async (tripId) => {
  await apiClient.delete(`/trips/${tripId}`);
};

// ─── AI CHAT ─────────────────────────────────────────────────────────────────
// These hit the AI pipeline (/api/trip/). The session_id is managed by the
// backend — null on the first message, echo it back on every subsequent one.

/**
 * Send a chat message and get back the full AI response + state.
 *
 * @param {string}      message     - User's typed text
 * @param {string|null} sessionId   - null on first message; use value from prev response after
 * @param {number|null} userLat     - Device latitude; safe to pass on every turn
 * @param {number|null} userLng     - Device longitude; safe to pass on every turn
 * @returns {Promise<ChatResponse>}
 */
export const sendChatMessage = async (message, sessionId, userLat = null, userLng = null) => {
  const res = await apiClient.post("/api/trip/chat", {
    message,
    session_id: sessionId,
    user_lat: userLat,
    user_lng: userLng,
  });
  return res.data;
};

/**
 * Persist the trip after the AI returns save_confirmed === true.
 * The session_id goes as a query param; no request body needed.
 *
 * @param {string} sessionId
 * @returns {Promise<SaveResponse>}  { trip_id, title, stops, gear }
 */
export const confirmSaveTrip = async (sessionId) => {
  const res = await apiClient.post("/api/trip/save", null, {
    params: { session_id: sessionId },
  });
  return res.data;
};

/**
 * Liveness check — call on app load before letting the user start typing.
 * @returns {Promise<{ redis: boolean, status: string }>}
 */
export const checkHealth = async () => {
  const res = await apiClient.get("/api/trip/health");
  return res.data;
};

// ─── Chat history ────────────────────────────────────────────────────────────
// Spans two stores server-side (Redis for active, Postgres `trips` for
// saved/completed/reviewed) but presents as one list here.

/**
 * @param {string[]|null} statuses - subset of active|saved|completed|reviewed;
 *   omit for all four.
 * @returns {Promise<Array<{id, status, title, created_at, updated_at, phase}>>}
 */
export const getChats = async (statuses = null) => {
  const params = statuses?.length ? { status: statuses.join(",") } : {};
  const res = await apiClient.get("/api/trip/chats", { params });
  return res.data;
};

/**
 * Fetches one chat. Shape differs by status: active includes phase/plan/
 * messages (live session); saved/completed/reviewed return the trip shape
 * (title/status/stops/gear/timestamps) — no raw message transcript, since
 * that's never persisted past the Redis session.
 */
export const getChat = async (chatId) => {
  const res = await apiClient.get(`/api/trip/chats/${chatId}`);
  return res.data;
};

// ─── Completion + review (Phase 2) ───────────────────────────────────────────

/** "Mark as done" — saved -> completed. */
export const completeChat = async (chatId) => {
  const res = await apiClient.post(`/api/trip/chats/${chatId}/complete`);
  return res.data;
};

/**
 * Questionnaire submission — completed -> reviewed.
 * @param {{went: boolean, difficulty_felt?: string, elevation_felt?: string, rating?: number, notes?: string}} payload
 */
export const submitReview = async (chatId, payload) => {
  const res = await apiClient.post(`/api/trip/chats/${chatId}/review`, payload);
  return res.data;
};

/** Aggregate header for the Past Hikes page: hike_count, total_miles, favorite_region. */
export const getPastHikesStats = async () => {
  const res = await apiClient.get("/api/trip/past-hikes/stats");
  return res.data;
};

/**
 * "Go Again" — clones a saved/completed/reviewed trip's criteria into a
 * fresh active session and re-runs the search against current trail data
 * (not a replay of the original results).
 * @returns {Promise<{session_id, response, phase, plan, hike_options}>}
 */
export const duplicateChat = async (chatId) => {
  const res = await apiClient.post(`/api/trip/chats/${chatId}/duplicate`);
  return res.data;
};