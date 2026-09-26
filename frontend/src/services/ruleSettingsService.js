import { api } from "./api";

// Admin-tunable detection-rule thresholds (loitering seconds, fighting
// proximity/jitter, abandoned-object dwell time, person/vehicle count
// alerts) -- lives under /alerts/thresholds rather than /settings/... on
// the gateway because /api/v1/settings/* is already routed to
// camera-service's own (unrelated) display-only Setting store; /alerts/*
// already routes to event-alert-service, which is what actually owns
// these values.
export const ruleSettingsService = {
  getAll: async () => {
    const data = await api.get("/alerts/thresholds");
    return data.items;
  },
  update: (key, value) => api.put(`/alerts/thresholds/${key}`, { value }),
  reset: (key) => api.delete(`/alerts/thresholds/${key}`),
};
