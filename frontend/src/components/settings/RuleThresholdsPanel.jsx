import { useCallback, useEffect, useState } from "react";
import { RotateCcw, SlidersHorizontal } from "lucide-react";
import { ruleSettingsService } from "../../services/ruleSettingsService";
import { useAuth } from "../../hooks/useAuth";

// Human-readable label/description for each key the backend exposes
// (app/services/rule_settings_service.py's TUNABLE_KEYS) -- if the backend
// ever adds a new tunable key, it still renders (falls back to the raw
// key as its own label) rather than silently disappearing.
const LABELS = {
  loitering_seconds_threshold: { label: "Loitering duration", hint: "How long a person must stay in one spot before Loitering Detected fires.", unit: "seconds" },
  person_count_threshold: { label: "Person count alert", hint: "Number of people in frame at once before a count alert fires.", unit: "people" },
  vehicle_count_threshold: { label: "Vehicle count alert", hint: "Number of vehicles in frame at once before a count alert fires.", unit: "vehicles" },
  fighting_proximity_threshold: { label: "Fighting: proximity", hint: "How close two people must be (as % of frame) to be a candidate fighting pair.", unit: "% of frame" },
  fighting_jitter_threshold: { label: "Fighting: motion jitter", hint: "How erratic a person's movement must be to count as part of a fight.", unit: "ratio" },
  fighting_min_mean_displacement: { label: "Fighting: minimum movement", hint: "Ignores near-stationary tracker jitter below this movement floor.", unit: "ratio" },
  abandoned_object_seconds_threshold: { label: "Abandoned object duration", hint: "How long a bag must sit still, with nobody nearby, before it's flagged.", unit: "seconds" },
  abandoned_object_proximity_threshold: { label: "Abandoned object: nearby-person distance", hint: "How close a person must be (as % of frame) to count as \"with\" the bag.", unit: "% of frame" },
};

export default function RuleThresholdsPanel() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [items, setItems] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [loadError, setLoadError] = useState(null);
  const [savingKey, setSavingKey] = useState(null);
  const [note, setNote] = useState(null);

  const load = useCallback(async () => {
    try {
      const data = await ruleSettingsService.getAll();
      setItems(data);
      setDrafts(Object.fromEntries(data.map((item) => [item.key, String(item.value)])));
      setLoadError(null);
    } catch (err) {
      setLoadError(err);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSave(key) {
    const value = Number(drafts[key]);
    if (Number.isNaN(value)) {
      setNote({ tone: "danger", text: "Enter a valid number." });
      return;
    }
    setSavingKey(key);
    setNote(null);
    try {
      await ruleSettingsService.update(key, value);
      await load();
      setNote({ tone: "success", text: `Saved -- takes effect within a few seconds.` });
    } catch (err) {
      setNote({ tone: "danger", text: err.detail || err.message || "Save failed." });
    } finally {
      setSavingKey(null);
    }
  }

  async function handleReset(key) {
    setSavingKey(key);
    setNote(null);
    try {
      await ruleSettingsService.reset(key);
      await load();
      setNote({ tone: "success", text: "Reverted to the default value." });
    } catch (err) {
      setNote({ tone: "danger", text: err.detail || err.message || "Reset failed." });
    } finally {
      setSavingKey(null);
    }
  }

  return (
    <section className="panel mb-5">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <SlidersHorizontal size={15} className="text-info" />
          <h2 className="font-semibold">Detection Thresholds</h2>
        </div>
      </div>

      <div className="p-4">
        <p className="text-xs leading-5 text-secondary">
          Tune the rule engine's numeric thresholds live, without redeploying. A changed value is picked up by the
          running system within a few seconds -- it doesn't require a restart.
        </p>

        {!isAdmin && <p className="mt-3 text-[11px] text-muted">Only administrators can change these.</p>}

        {note && (
          <div
            role="status"
            className={`mt-3 border px-3 py-2 text-xs ${
              note.tone === "danger" ? "border-danger/40 bg-danger/10 text-danger" : "border-success/40 bg-success/10 text-success"
            }`}
          >
            {note.text}
          </div>
        )}

        {loadError ? (
          <p className="mt-4 text-xs text-danger">Couldn't load the current thresholds.</p>
        ) : !items ? (
          <p className="mt-4 text-xs text-muted">Loading...</p>
        ) : (
          <div className="mt-4 divide-y divide-line border-t border-line">
            {items.map((item) => {
              const meta = LABELS[item.key] || { label: item.key, hint: "", unit: "" };
              const dirty = drafts[item.key] !== String(item.value);
              return (
                <div key={item.key} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-primary">
                      {meta.label}
                      {item.isOverridden && (
                        <span className="ml-2 border border-info/40 bg-info/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-info">
                          Overridden
                        </span>
                      )}
                    </p>
                    <p className="mt-0.5 text-[11px] text-muted">{meta.hint}</p>
                    {item.isOverridden && (
                      <p className="mt-0.5 text-[10px] text-muted">
                        Default: {item.default}{meta.unit ? ` ${meta.unit}` : ""}
                        {item.updatedBy ? ` -- last changed by ${item.updatedBy}` : ""}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      value={drafts[item.key] ?? ""}
                      onChange={(e) => setDrafts((d) => ({ ...d, [item.key]: e.target.value }))}
                      disabled={!isAdmin || savingKey === item.key}
                      className="w-24 border border-line bg-panelSecondary px-2 py-1.5 text-right text-xs text-primary outline-none focus:border-info disabled:opacity-50"
                    />
                    <span className="w-16 text-[10px] text-muted">{meta.unit}</span>
                    <button
                      type="button"
                      onClick={() => handleSave(item.key)}
                      disabled={!isAdmin || !dirty || savingKey === item.key}
                      className="border border-line bg-panelSecondary px-2.5 py-1.5 text-[11px] font-semibold text-secondary hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {savingKey === item.key ? "..." : "Save"}
                    </button>
                    {item.isOverridden && (
                      <button
                        type="button"
                        onClick={() => handleReset(item.key)}
                        disabled={!isAdmin || savingKey === item.key}
                        aria-label={`Reset ${meta.label} to default`}
                        title="Reset to default"
                        className="p-1.5 text-muted hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        <RotateCcw size={13} />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
