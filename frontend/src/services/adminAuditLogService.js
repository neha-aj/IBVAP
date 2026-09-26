import { api } from "./api";

// Admin-only view of camera-service's hash-chained audit log (who
// created/updated/deleted a camera, and when) -- lives under
// /cameras/audit-log because camera-service owns the log, even though it
// tracks admin actions in general.
export const adminAuditLogService = {
  getPage: (page = 1, pageSize = 50) => api.get("/cameras/audit-log", { page, pageSize }),
  verifyChain: () => api.get("/cameras/audit-log/verify-chain"),
};
