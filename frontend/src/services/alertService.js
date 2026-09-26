import { api } from "./api";

// Same bound as eventService's own export -- see that file's comment.
const EXPORT_PAGE_SIZE = 1000;
export const EXPORT_MAX_ROWS = 10000;

export const alertService = {
  getAll: async (params) => {
    const data = await api.get("/alerts", params);
    return data.items;
  },
  getById: (id) => api.get(`/alerts/${id}`),
  // Real backend status enum is active|reviewing|resolved (event-alert
  // Alert model) -- there is no "acknowledged" status server-side.
  updateStatus: (id, status) => api.patch(`/alerts/${id}/status`, { status }),
  // Every alert matching `params`, newest first, up to `max` rows -- for
  // export. Returns { items, total, truncated }.
  getAllMatching: async (params, { max = EXPORT_MAX_ROWS, onProgress } = {}) => {
    const items = [];
    let total = 0;
    for (let page = 1; items.length < max; page += 1) {
      const data = await api.get("/alerts", { ...params, page, pageSize: EXPORT_PAGE_SIZE });
      total = data.total;
      items.push(...data.items);
      if (onProgress) onProgress(Math.min(items.length, total), total);
      if (data.items.length < EXPORT_PAGE_SIZE || items.length >= total) break;
    }
    return { items: items.slice(0, max), total, truncated: total > max };
  },
};
