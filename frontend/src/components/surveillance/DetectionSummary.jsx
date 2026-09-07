export default function DetectionSummary({ camera, detections }) {
  const average = detections.length
    ? Math.round(
        (detections.reduce(
          (sum, detection) => sum + detection.confidence,
          0
        ) /
          detections.length) *
          100
      )
    : 0;

  const stats = [
    [camera.detections.persons, "Persons"],
    [camera.detections.vehicles, "Vehicles"],
    [0, "Unknown"],
    [`${average}%`, "Avg confidence"],
  ];

  return (
    <section className="panel p-4">
      <p className="eyebrow">Current Detections</p>

      <div className="mt-3 grid grid-cols-4 divide-x">
        {stats.map(([value, label]) => (
          <div className="px-2 first:pl-0" key={label}>
            <p className="text-lg font-semibold text-primary">
              {value}
            </p>

            <p className="mt-1 text-[9px] uppercase tracking-wide text-muted">
              {label}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}