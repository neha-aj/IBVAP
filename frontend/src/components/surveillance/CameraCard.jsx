import { useEffect, useState } from 'react';
import { Expand, UserRound, CarFront, TriangleAlert } from 'lucide-react';
import VideoPlaceholder from './VideoPlaceholder';
import Badge from '../common/Badge';
import StatusDot from '../common/StatusDot';
import { cameraService } from '../../services/cameraService';
import { GATEWAY_ORIGIN } from '../../services/api';

export default function CameraCard({ camera, detections = [], dailyCounts, selected, onSelect }) {
  const isOffline = camera.status === 'offline';
  const [streamUrl, setStreamUrl] = useState(null);

  // camera.detections.{persons,vehicles} is always {0,0} by backend design
  // (API Spec §2 -- the frontend derives it from live detections instead),
  // so count from the real per-camera detections this tile was handed.
  const personCount = detections.filter((d) => d.type === 'person').length;
  const vehicleCount = detections.filter((d) => d.type === 'vehicle').length;

  useEffect(() => {
    let cancelled = false;
    if (isOffline) return;
    cameraService.getStream(camera.id).then((info) => {
      if (!cancelled) setStreamUrl(`${GATEWAY_ORIGIN}${info.mjpegUrl}`);
    }).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [camera.id, isOffline]);

  return (
    <article
      onClick={() => onSelect(camera)}
      className={`panel cursor-pointer overflow-hidden transition-colors hover:border-secondary ${selected ? 'ring-1 ring-info border-info' : ''}`}
    >
      <VideoPlaceholder cameraName={camera.id} detections={detections} streamUrl={streamUrl} />
      <div className="p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <StatusDot status={camera.status} />
              <p className="truncate text-[13px] font-semibold text-primary">{camera.name}</p>
            </div>
            <p className="mt-1 truncate text-[11px] text-secondary">{camera.location}</p>
          </div>
          <button aria-label={`Expand ${camera.name}`} className="text-muted hover:text-primary">
            <Expand size={15} />
          </button>
        </div>
        <div className="mt-3 flex items-center gap-3 border-t pt-3 text-[11px] text-secondary">
          <span className="flex items-center gap-1" title="Currently in frame">
            <UserRound size={13} /> {personCount}
            {dailyCounts && <span className="text-muted">/{dailyCounts.personCount} today</span>}
          </span>
          <span className="flex items-center gap-1" title="Currently in frame">
            <CarFront size={13} /> {vehicleCount}
            {dailyCounts && <span className="text-muted">/{dailyCounts.vehicleCount} today</span>}
          </span>
          {camera.alert ? (
            <Badge tone={isOffline ? 'offline' : 'high'}><TriangleAlert size={11} className="mr-1" />{camera.alert}</Badge>
          ) : (
            <span className="ml-auto text-muted">{camera.fps} FPS</span>
          )}
        </div>
      </div>
    </article>
  );
}
