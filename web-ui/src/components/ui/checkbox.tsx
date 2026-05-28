import { Check } from "lucide-react";
import type React from "react";

import { cn } from "@/lib/utils";

interface CheckboxProps {
  checked: boolean;
  onCheckedChange?: ((checked: boolean) => void) | undefined;
  id?: string | undefined;
  disabled?: boolean | undefined;
  className?: string | undefined;
}

export function Checkbox({ checked, onCheckedChange, id, disabled, className }: CheckboxProps) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      id={id}
      disabled={disabled}
      onClick={() => onCheckedChange?.(!checked)}
      className={cn(
        "inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
        checked
          ? "border-primary bg-primary text-primary-foreground"
          : "border-input bg-background hover:border-primary/60",
        disabled && "cursor-not-allowed opacity-50",
        className,
      )}
    >
      {checked ? <Check className="h-3 w-3" strokeWidth={3} /> : null}
    </button>
  );
}

interface CheckboxFieldProps {
  checked: boolean;
  onCheckedChange?: (checked: boolean) => void;
  id?: string;
  disabled?: boolean;
  children: React.ReactNode;
  className?: string;
}

export function CheckboxField({ checked, onCheckedChange, id, disabled, children, className }: CheckboxFieldProps) {
  return (
    <label
      className={cn(
        "inline-flex cursor-pointer items-center gap-2 text-sm",
        disabled && "cursor-not-allowed opacity-50",
        className,
      )}
    >
      <Checkbox checked={checked} onCheckedChange={onCheckedChange} id={id} disabled={disabled} />
      <span>{children}</span>
    </label>
  );
}
