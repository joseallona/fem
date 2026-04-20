"use client";
import * as React from "react";
import { cn } from "@/lib/utils";

// TooltipProvider is a no-op kept for API compatibility.
export function TooltipProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

// TooltipContent kept for low-level usage compatibility.
export function TooltipContent({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "max-w-xs rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

// ── Main Tooltip ──────────────────────────────────────────────────────────
// Pure CSS hover via Tailwind `group` / `group-hover` — no JavaScript state,
// no portals, no z-index stacking context issues.

const SIDE_CLASSES: Record<string, string> = {
  top:    "bottom-full left-1/2 -translate-x-1/2 mb-2",
  bottom: "top-full  left-1/2 -translate-x-1/2 mt-2",
  right:  "left-full  top-1/2 -translate-y-1/2 ml-2",
  left:   "right-full top-1/2 -translate-y-1/2 mr-2",
};

export function Tooltip({
  content,
  children,
  side = "top",
}: {
  content: React.ReactNode;
  children: React.ReactNode;
  side?: "top" | "bottom" | "left" | "right";
}) {
  return (
    <span className="group relative inline-flex items-center">
      {children}
      <div
        className={cn(
          // Always in the DOM but invisible; becomes visible on group hover.
          "pointer-events-none invisible absolute z-[99999] w-max max-w-xs",
          "rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md",
          "whitespace-normal group-hover:visible",
          SIDE_CLASSES[side]
        )}
      >
        {content}
      </div>
    </span>
  );
}
