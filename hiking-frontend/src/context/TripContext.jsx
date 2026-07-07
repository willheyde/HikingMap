import { createContext, useContext, useState, useCallback } from "react";
import * as tripService from "../api/tripService";

const TripContext = createContext(null);

export const useTrip = () => useContext(TripContext);

// Attaches the current hike option set to the last assistant message so the
// cards render anchored in place on resume/duplicate (the per-message shape
// sendMessage uses). The backend only returns the *current* option set, so on
// rehydration we can only anchor it to the most recent assistant turn — good
// enough, since that's the only turn whose options are still actionable.
const anchorOptionsToLastAssistant = (messages, hikeOptions) => {
  if (!hikeOptions?.length) return messages;
  let lastAssistant = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "assistant") { lastAssistant = i; break; }
  }
  if (lastAssistant === -1) return messages;
  return messages.map((m, i) =>
    i === lastAssistant ? { ...m, hikeOptions } : m
  );
};

// ─── Initial state shapes ────────────────────────────────────────────────────

const INITIAL_CHAT_STATE = {
  sessionId: null,
  messages: [],      // [{ role: "user" | "assistant", content: string }]
  phase: "destination",
  plan: null,
  serviceReady: null, // null = unchecked, true/false after health check
  hikeOptions: [],    // structured hike cards for the current turn (destination phase only)
};

// ─── Provider ────────────────────────────────────────────────────────────────

export const TripProvider = ({ children }) => {

  // Saved trips (from REST API)
  const [savedTrips, setSavedTrips] = useState([]);
  const [activeTrip, setActiveTrip] = useState(null);

  // AI chat session
  const [chat, setChat] = useState(INITIAL_CHAT_STATE);

  // Chat history (sidebar list) + the read-only view for a saved/completed/
  // reviewed chat. Kept separate from `chat` (the live conversation) rather
  // than overloading chat.messages with synthesized content — a saved trip
  // never had a stored transcript to begin with (see getChat's docstring).
  const [chatList, setChatList] = useState([]);
  const [readOnlyChat, setReadOnlyChat] = useState(null);

  // Shared async state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // ─── Helpers ───────────────────────────────────────────────────────────────

  const withLoading = async (fn) => {
    setLoading(true);
    setError(null);
    try {
      return await fn();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      setError(msg);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // ─── Chat actions ──────────────────────────────────────────────────────────

  /**
   * Send a message through the AI pipeline.
   * Appends both the user turn and the assistant reply to `messages`.
   * Automatically calls confirmSaveTrip when the backend signals save_confirmed.
   */
  const sendMessage = useCallback(
    async (text, userLat = null, userLng = null) => {
      return withLoading(async () => {
        // Optimistically append the user's message so the UI is snappy
        setChat((prev) => ({
          ...prev,
          messages: [...prev.messages, { role: "user", content: text }],
        }));

        const data = await tripService.sendChatMessage(
          text,
          chat.sessionId,
          userLat,
          userLng
        );

        // If the AI just confirmed a save, persist the trip immediately

        // Anchor the hike option cards to the assistant message that produced
        // them, rather than a single chat-level field re-rendered at the
        // bottom every turn. This keeps each option set in place in the
        // transcript: a later refinement's fresh 5 attach to their own message
        // and become the new set, while the old cards stay put above them
        // instead of following the conversation and crowding later phases.
        setChat((prev) => ({
          ...prev,
          sessionId: data.session_id,
          phase: data.phase,
          plan: data.plan,
          hikeOptions: data.hike_options || [],
          messages: [
            ...prev.messages,
            {
              role: "assistant",
              content: data.response,
              hikeOptions: data.hike_options || [],
            },
          ],
        }));
        if (data.save_confirmed) {
          try {
            const saved = await tripService.confirmSaveTrip(data.session_id);
            setActiveTrip(saved);
            setSavedTrips((prev) => [saved, ...prev]);
            // The session that was "active" a moment ago is now gone from
            // Redis and replaced by a "saved" trip row — refresh the
            // sidebar list so it reflects that instead of showing a stale
            // active entry until the user manually reloads.
            tripService.getChats().then(setChatList).catch(() => {});
          } catch (err) {
            const msg = err.response?.data?.detail || err.message;
            setError(`Trip save failed: ${msg}`);
          }
        }
        // Return the raw response so components can inspect advanced / save_confirmed
        return data;
      });
    },
    [chat.sessionId]
  );

  /** Reset the chat to start a brand-new planning session. */
  const resetChat = useCallback(() => {
    setChat(INITIAL_CHAT_STATE);
    setReadOnlyChat(null);
    setError(null);
  }, []);

  /** Load the history sidebar list. statuses omitted = all four states. */
  const loadChatList = useCallback(async (statuses = null) => {
    return withLoading(async () => {
      const list = await tripService.getChats(statuses);
      setChatList(list);
    });
  }, []);

  /**
   * Opens a chat by id, regardless of which store it lives in.
   * active     -> rehydrates the live conversation into `chat` so the user
   *               can keep talking to the AI right where they left off.
   * saved/completed/reviewed -> nothing left to converse with (planning is
   *               done); sets `readOnlyChat` so the UI can render a summary
   *               instead. See Step 0 discussion: there's no stored message
   *               transcript for a saved trip, only the structured plan.
   */
  const openChat = useCallback(async (chatId) => {
    return withLoading(async () => {
      const data = await tripService.getChat(chatId);
      if (data.status === "active") {
        setReadOnlyChat(null);
        setChat({
          sessionId: data.id,
          phase: data.phase,
          plan: data.plan,
          messages: anchorOptionsToLastAssistant(
            data.messages || [],
            data.hike_options || []
          ),
          serviceReady: true,
          hikeOptions: data.hike_options || [],
        });
      } else {
        setReadOnlyChat(data);
      }
      return data;
    });
  }, []);

  /** "Mark as done" — saved -> completed. */
  const markChatCompleted = useCallback(async (chatId) => {
    return withLoading(async () => {
      const updated = await tripService.completeChat(chatId);
      setChatList((prev) => prev.map((c) => (c.id === chatId ? { ...c, status: updated.status } : c)));
      setReadOnlyChat((prev) => (prev?.id === chatId ? { ...prev, ...updated } : prev));
      return updated;
    });
  }, []);

  /**
   * Questionnaire submission — completed -> reviewed. Re-fetches the list
   * and the open chat afterward rather than hand-patching local state —
   * the trip's status/needs_review both change server-side and this is a
   * rare action, not worth two parallel sources of truth for.
   */
  const submitChatReview = useCallback(async (chatId, payload) => {
    return withLoading(async () => {
      const completion = await tripService.submitReview(chatId, payload);
      const [list, updatedChat] = await Promise.all([
        tripService.getChats(),
        tripService.getChat(chatId),
      ]);
      setChatList(list);
      setReadOnlyChat((prev) => (prev?.id === chatId ? updatedChat : prev));
      return completion;
    });
  }, []);

  /**
   * "Go Again" — clones a past/upcoming trip's criteria into a fresh active
   * session (search re-run against current trail data, not a replay) and
   * switches the live chat over to it, same as if the user had just started
   * this conversation from scratch.
   */
  const duplicateChat = useCallback(async (chatId) => {
    return withLoading(async () => {
      const data = await tripService.duplicateChat(chatId);
      setReadOnlyChat(null);
      setChat({
        sessionId: data.session_id,
        phase: data.phase,
        plan: data.plan,
        messages: [
          {
            role: "assistant",
            content: data.response,
            hikeOptions: data.hike_options || [],
          },
        ],
        serviceReady: true,
        hikeOptions: data.hike_options || [],
      });
      // The clone is a brand-new active session — reflect that in the sidebar.
      tripService.getChats().then(setChatList).catch(() => {});
      return data;
    });
  }, []);

  /**
   * "Not going" — the user has decided to skip an upcoming (saved) trip.
   * Deletes the trip and drops it from the sidebar / clears the open view.
   * Deliberately a hard delete: there is no "cancelled" lifecycle state, and
   * an abandoned upcoming trip is noise in the Past Hikes review flow.
   */
  const cancelChat = useCallback(async (chatId) => {
    return withLoading(async () => {
      await tripService.deleteTrip(chatId);
      setChatList((prev) => prev.filter((c) => c.id !== chatId));
      setReadOnlyChat((prev) => (prev?.id === chatId ? null : prev));
    });
  }, []);

  /** Call once on mount to verify the AI service is reachable. */
  const checkServiceHealth = useCallback(async () => {
    try {
      const { status } = await tripService.checkHealth();
      setChat((prev) => ({ ...prev, serviceReady: status === "ok" }));
    } catch {
      setChat((prev) => ({ ...prev, serviceReady: false }));
    }
  }, []);

  // ─── Saved-trip CRUD actions ───────────────────────────────────────────────

  const loadUserTrips = useCallback(async (userId) => {
    return withLoading(async () => {
      const trips = await tripService.getUserTrips(userId);
      setSavedTrips(trips);
    });
  }, []);

  const loadTrip = useCallback(async (tripId) => {
    return withLoading(async () => {
      const fetched = await tripService.getTripById(tripId);
      setActiveTrip(fetched);
    });
  }, []);

  const removeTrip = useCallback(async (tripId) => {
    return withLoading(async () => {
      await tripService.deleteTrip(tripId);
      setActiveTrip((prev) => (prev?.trip_id === tripId ? null : prev));
      setSavedTrips((prev) => prev.filter((t) => t.trip_id !== tripId));
    });
  }, []);

  // ─── Context value ─────────────────────────────────────────────────────────

  return (
    <TripContext.Provider
      value={{
        // Chat state
        chat,               // { sessionId, messages, phase, plan, serviceReady }
        sendMessage,
        resetChat,
        checkServiceHealth,

        // Chat history (Planning / Upcoming / Past hikes)
        chatList,           // [{ id, status, title, created_at, updated_at, phase, needs_review }]
        readOnlyChat,       // trip-shaped dict when viewing a saved/completed/reviewed chat, else null
        loadChatList,
        openChat,
        markChatCompleted,
        submitChatReview,
        duplicateChat,
        cancelChat,

        // Saved-trip state
        savedTrips,
        activeTrip,
        loadUserTrips,
        loadTrip,
        removeTrip,

        // Async state
        loading,
        error,
      }}
    >
      {children}
    </TripContext.Provider>
  );
};