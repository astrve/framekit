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
              ? "border-destructive/40 bg-destructive/10 text-destructive"
              : item.done
                ? "border-success/40 bg-success/10 text-success"
                : item.active
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border bg-card text-muted-foreground"
          }`}
        >
          {item.label}
        </div>
      ))}
    </div>
  );
}
