import { useEffect, useRef, useState } from "react";
import { cameraService } from "../services/cameraService";
import { socket } from "../services/socket";

// Detections are inherently per-camera (API Spec §2/§8) -- there is no
// "all detections across every camera" endpoint or topic. `cameraIds` is
// the set of cameras currently rendered (the surveillance grid); this hook
// fetches each one's current detections once, then keeps them live via
// each camera's own `camera:{id}` `detection.new` topic, and flattens the
// result into one array so existing per-camera filtering (`CameraGrid`,
// `DetectionSummary`) keeps working unchanged.
export function useDetections(cameraIds = []) {
  const [byCamera, setByCamera] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const subscribedIds = useRef(new Set());
  const idsKey = cameraIds.join(",");

  useEffect(() => {
    if (cameraIds.length === 0) {
      setIsLoading(false);
      return;
    }
    let cancelled = false;

    async function load() {
      setIsLoading(true);
      const results = await Promise.all(
        cameraIds.map(async (id) => {
          try {
            return [id, await cameraService.getCurrentDetections(id)];
          } catch {
            return [id, []];
          }
        })
      );
      if (!cancelled) {
        setByCamera(Object.fromEntries(results));
        setIsLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idsKey]);

  useEffect(() => {
    const currentIds = new Set(cameraIds);
    const toSubscribe = [...currentIds].filter((id) => !subscribedIds.current.has(id));
    const toUnsubscribe = [...subscribedIds.current].filter((id) => !currentIds.has(id));

    if (toSubscribe.length > 0) socket.subscribe(toSubscribe.map((id) => `camera:${id}`));
    if (toUnsubscribe.length > 0) socket.unsubscribe(toUnsubscribe.map((id) => `camera:${id}`));

    subscribedIds.current = currentIds;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idsKey]);

  useEffect(() => {
    return socket.on("detection.new", ({ cameraId, detections }) => {
      setByCamera((current) => ({ ...current, [cameraId]: detections }));
    });
  }, []);

  const detections = Object.values(byCamera).flat();
  return { detections, isLoading };
}
