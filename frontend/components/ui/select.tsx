"use client";
import * as React from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

// ── Child-tree scraper ────────────────────────────────────────────────────
// Walk the React element tree to collect SelectItem values and SelectTrigger
// className without needing portals, context, or effects.

const _TRIGGER = Symbol("SelectTrigger");
const _ITEM    = Symbol("SelectItem");

interface ScrapedData {
  triggerClass: string;
  placeholder: string;
  items: { value: string; label: string }[];
}

function scrape(children: React.ReactNode): ScrapedData {
  const out: ScrapedData = { triggerClass: "", placeholder: "", items: [] };

  function walk(nodes: React.ReactNode) {
    React.Children.forEach(nodes, node => {
      if (!React.isValidElement(node)) return;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const sel = (node.type as any)._sel as symbol | undefined;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const p = node.props as any;
      if (sel === _TRIGGER) {
        out.triggerClass = p.className ?? "";
        walk(p.children); // recurse into SelectValue for placeholder
      } else if (sel === _ITEM) {
        const label = typeof p.children === "string" ? p.children : String(p.value);
        out.items.push({ value: p.value, label });
      } else {
        if (p?.children) walk(p.children);
      }
    });
  }

  walk(children);
  return out;
}

// ── Select (root) ─────────────────────────────────────────────────────────

export function Select({
  value,
  defaultValue,
  onValueChange,
  children,
}: {
  value?: string;
  defaultValue?: string;
  onValueChange?: (v: string) => void;
  children?: React.ReactNode;
}) {
  const { triggerClass, placeholder, items } = scrape(children);
  const current = value ?? defaultValue ?? "";

  return (
    <div className="relative w-full">
      <select
        value={current}
        onChange={e => onValueChange?.(e.target.value)}
        className={cn(
          "flex h-9 w-full appearance-none rounded-md border border-input bg-transparent px-3 py-2 pr-8 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
          triggerClass
        )}
      >
        {placeholder && !current && (
          <option value="" disabled>{placeholder}</option>
        )}
        {items.map(item => (
          <option key={item.value} value={item.value}>{item.label}</option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 opacity-50" />
    </div>
  );
}

// ── Structural components (scraped by Select, render nothing themselves) ──

export const SelectGroup = ({ children }: { children?: React.ReactNode }) => <>{children}</>;

// SelectValue: its placeholder prop is read by scrape(); nothing rendered.
export const SelectValue = Object.assign(
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  function SelectValue({ placeholder }: { placeholder?: string }) { return null; },
  { _sel: Symbol("SelectValue") }
);

// SelectTrigger: its className is read by scrape(); nothing rendered.
export const SelectTrigger = Object.assign(
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  function SelectTrigger({ className, children }: { className?: string; children?: React.ReactNode }) { return null; },
  { _sel: _TRIGGER }
);

// SelectContent: wrapper for SelectItems; nothing rendered.
export const SelectContent = Object.assign(
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  function SelectContent({ children, className, position }: { children?: React.ReactNode; className?: string; position?: string }) { return null; },
  { _sel: Symbol("SelectContent") }
);

// SelectItem: carries value + label; nothing rendered directly.
export const SelectItem = Object.assign(
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  function SelectItem({ value, children, className, disabled }: { value: string; children?: React.ReactNode; className?: string; disabled?: boolean }) { return null; },
  { _sel: _ITEM }
);
