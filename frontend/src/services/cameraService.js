import { api } from "./api";

export const cameraService = {
  // API Spec §2: response is an envelope {items,total,page,pageSize} --
  // callers of getAll only ever need the array itself.
  getAll: async (params) => {
    const data = await api.get("/cameras", params);
    return data.items;
  },
  getById: (id) => api.get(`/cameras/${id}`),
  update: (id, payload) => api.put(`/cameras/${id}`, payload),
  getStatusSummary: () => api.get("/cameras/status/summary"),
  getStream: (id) => api.get(`/cameras/${id}/stream`),
  getCurrentDetections: (id) => api.get(`/cameras/${id}/detections/current`),
  getHealth: (id) => api.get(`/cameras/${id}/health`),
  create: (payload) => api.post("/cameras", payload),
  uploadVideo: (id, file) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.postForm(`/cameras/${id}/upload`, formData);
  },
};
