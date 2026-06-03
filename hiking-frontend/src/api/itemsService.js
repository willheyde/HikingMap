import apiClient from "./client";

// ─── Read ──────────────────────────────────────────────────────────────────────

export const getItemById = async (itemId) => {
  const res = await apiClient.get(`/items/${itemId}`);
  return res.data;
};

export const getItemByName = async (name) => {
  const res = await apiClient.get(`/items/by-name/${encodeURIComponent(name)}`);
  return res.data;
};

/**
 * List items, optionally filtered by type.
 * @param {string|null} itemType  e.g. "backpack" | "footwear" | "shelter" …
 */
export const listItems = async (itemType = null) => {
  const params = itemType ? { item_type: itemType } : {};
  const res = await apiClient.get("/items/", { params });
  return res.data;
};

// ─── Create (one per item type) ────────────────────────────────────────────────

export const createBackpack      = (data) => apiClient.post("/items/backpacks",       data).then((r) => r.data);
export const createFootwear      = (data) => apiClient.post("/items/footwear",        data).then((r) => r.data);
export const createShelter       = (data) => apiClient.post("/items/shelters",        data).then((r) => r.data);
export const createSleepingBag   = (data) => apiClient.post("/items/sleeping-bags",   data).then((r) => r.data);
export const createSleepingPad   = (data) => apiClient.post("/items/sleeping-pads",   data).then((r) => r.data);
export const createClothing      = (data) => apiClient.post("/items/clothing",        data).then((r) => r.data);
export const createWaterSystem   = (data) => apiClient.post("/items/water",           data).then((r) => r.data);
export const createKitchen       = (data) => apiClient.post("/items/kitchen",         data).then((r) => r.data);
export const createNavigation    = (data) => apiClient.post("/items/navigation",      data).then((r) => r.data);
export const createLighting      = (data) => apiClient.post("/items/lighting",        data).then((r) => r.data);
export const createSafety        = (data) => apiClient.post("/items/safety",          data).then((r) => r.data);
export const createTechnical     = (data) => apiClient.post("/items/technical",       data).then((r) => r.data);
export const createTrekkingPoles = (data) => apiClient.post("/items/trekking-poles",  data).then((r) => r.data);

/**
 * Generic helper — routes to the correct endpoint based on item_type string.
 * Useful when a component already knows the type and just passes data through.
 */
const TYPE_ROUTE_MAP = {
  backpack:       createBackpack,
  footwear:       createFootwear,
  shelter:        createShelter,
  sleeping_bag:   createSleepingBag,
  sleeping_pad:   createSleepingPad,
  clothing:       createClothing,
  water:          createWaterSystem,
  kitchen:        createKitchen,
  navigation:     createNavigation,
  lighting:       createLighting,
  safety:         createSafety,
  technical:      createTechnical,
  trekking_poles: createTrekkingPoles,
};

export const createItem = (itemType, data) => {
  const fn = TYPE_ROUTE_MAP[itemType];
  if (!fn) throw new Error(`Unknown item type: "${itemType}"`);
  return fn(data);
};

// ─── Update ────────────────────────────────────────────────────────────────────

export const updateItemImage = async (itemId, imageUrl) => {
  const res = await apiClient.patch(`/items/${itemId}/image`, { image_url: imageUrl });
  return res.data;
};

// ─── Delete ────────────────────────────────────────────────────────────────────

export const deleteItem = async (itemId) => {
  await apiClient.delete(`/items/${itemId}`);
};