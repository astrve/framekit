export function RunTimeline(props: {
  items: Array<{ label: string; active: boolean; done: boolean; failed: boolean }>;
}) {
  const { items } = props;
  return (
    <div className="grid gap-2 md:grid-cols-3">
      {items.map((item) => (
        <div
          key={item.label}
          className={`rounded-md border p-3 text-sm ${
            item.failed
              ? "border-rose-300 bg-rose-50 text-rose-800"
              : item.done
                ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                : item.active
                  ? "border-blue-300 bg-blue-50 text-blue-800"
                  : "border-border bg-background"
          }`}
        >
          {item.label}
        </div>
      ))}
    </div>
  );
}
