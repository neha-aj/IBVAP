import { useCallback, useEffect, useState } from "react";
import { ShieldCheck, ShieldAlert } from "lucide-react";
import PageHeader from "../components/layout/PageHeader";
import Badge from "../components/common/Badge";
import EmptyState from "../components/common/EmptyState";
import { adminAuditLogService } from "../services/adminAuditLogService";

const PAGE_SIZE = 50;

// action strings look like "camera.created" / "camera.updated" / "camera.deleted"
// (see camera-service's admin_audit_log_service.py) -- split for a badge tone.
function actionTone(action) {
  if (action.endsWith(".deleted")) return "offline";
  if (action.endsWith(".created")) return "online";
  return "active";
}

export default function AdminAuditLog() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [chain, setChain] = useState(null); // null | { checking } | ChainIntegrity
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async (p) => {
    setIsLoading(true);
    try {
      const result = await adminAuditLogService.getPage(p, PAGE_SIZE);
      setData(result);
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load(page);
  }, [load, page]);

  async function handleVerifyChain() {
    setChain({ checking: true });
    try {
      const result = await adminAuditLogService.verifyChain();
      setChain(result);
    } catch (err) {
      setChain({ intact: false, error: err.detail || err.message || "Verification failed." });
    }
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <>
      <PageHeader
        title="Admin Audit Log"
        subtitle="Hash-chained record of every admin camera action -- who did what, and when"
        action={
          <button
            type="button"
            onClick={handleVerifyChain}
            disabled={chain?.checking}
            className="flex items-center gap-2 border border-line bg-panelSecondary px-3 py-2 text-xs font-semibold text-secondary hover:bg-slate-800/40 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ShieldCheck size={14} />
            {chain?.checking ? "Verifying..." : "Verify chain integrity"}
          </button>
        }
      />

      {chain && !chain.checking && (
        <div
          role="status"
          className={`mb-3 flex items-center gap-2 border px-3 py-2 text-xs ${
            chain.intact
              ? "border-success/40 bg-success/10 text-success"
              : "border-danger/40 bg-danger/10 text-danger"
          }`}
        >
          {chain.intact ? <ShieldCheck size={14} /> : <ShieldAlert size={14} />}
          {chain.intact
            ? `Chain intact -- ${chain.entriesChecked.toLocaleString()} entries verified from genesis.`
            : chain.error || `Chain broken at entry ${chain.firstBrokenEntryId} -- an entry may have been tampered with.`}
        </div>
      )}

      {isLoading ? (
        <div className="panel p-10 text-center text-xs text-muted">Loading audit log...</div>
      ) : error ? (
        <div className="panel p-10 text-center text-xs text-danger">Failed to load the audit log.</div>
      ) : data.items.length === 0 ? (
        <EmptyState title="No admin actions recorded yet" />
      ) : (
        <>
          <p className="mb-2 text-[11px] text-muted">
            Showing {data.items.length.toLocaleString()} of {data.total.toLocaleString()} entries
          </p>
          <div className="panel overflow-x-auto">
            <table className="w-full min-w-[760px] text-left">
              <thead className="bg-slate-900/40 text-[10px] uppercase tracking-wider text-muted">
                <tr>
                  {["Time", "Actor", "Action", "Target", "Details"].map((h) => (
                    <th className="px-4 py-3 font-medium" key={h}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.items.map((entry) => (
                  <tr key={entry.id} className="hover:bg-slate-800/30">
                    <td className="px-4 py-3 text-muted">
                      {new Date(entry.createdAt).toLocaleString([], {
                        day: "2-digit",
                        month: "short",
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })}
                    </td>
                    <td className="px-4 py-3 font-medium">{entry.actor || "unknown"}</td>
                    <td className="px-4 py-3">
                      <Badge tone={actionTone(entry.action)}>{entry.action}</Badge>
                    </td>
                    <td className="px-4 py-3 text-muted">
                      {entry.targetType} <span className="text-[10px]">{entry.targetId}</span>
                    </td>
                    <td className="px-4 py-3 text-[11px] text-muted">{entry.details || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <div className="mt-3 flex items-center justify-center gap-3">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="border border-line bg-panelSecondary px-4 py-2 text-xs font-semibold text-secondary hover:text-primary disabled:opacity-50"
              >
                Previous
              </button>
              <span className="text-[11px] text-muted">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="border border-line bg-panelSecondary px-4 py-2 text-xs font-semibold text-secondary hover:text-primary disabled:opacity-50"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </>
  );
}
