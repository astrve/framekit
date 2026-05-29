import type * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold tracking-[0.02em] transition-colors",
  {
    variants: {
      variant: {
        default: "border-primary/15 bg-primary/95 text-primary-foreground",
        secondary: "border-border/80 bg-secondary text-secondary-foreground",
        outline: "border-border bg-transparent text-foreground",
        success: "border-emerald-700/35 bg-emerald-200/80 text-emerald-950 dark:border-emerald-300/50 dark:bg-emerald-700/35 dark:text-emerald-50",
        warning: "border-amber-700/35 bg-amber-200/85 text-amber-950 dark:border-amber-300/50 dark:bg-amber-700/35 dark:text-amber-50",
        danger: "border-rose-700/35 bg-rose-200/85 text-rose-950 dark:border-rose-300/50 dark:bg-rose-700/35 dark:text-rose-50",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

function Badge({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof badgeVariants>): React.JSX.Element {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
