import { cn } from "@/lib/utils";

interface ToggleProps {
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
  label?: string;
  tooltip?: React.ReactNode;
  className?: string;
}

export function Toggle({ checked, onChange, disabled, label, tooltip, className }: ToggleProps) {
  return (
    <label className={cn("inline-flex cursor-pointer items-center gap-3 text-sm select-none", disabled && "cursor-not-allowed opacity-50", className)}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        className={cn(
          "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          checked
            ? "border-primary bg-primary"
            : "border-border bg-muted",
          disabled && "cursor-not-allowed",
        )}
      >
        <span
          className={cn(
            "inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform duration-200 dark:bg-slate-100",
            checked ? "translate-x-[18px]" : "translate-x-[2px]",
          )}
        />
      </button>
      {label ? <span className="font-medium">{label}</span> : null}
      {tooltip ?? null}
    </label>
  );
}
