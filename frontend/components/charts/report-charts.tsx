"use client";
import { useRef, useEffect, useState } from "react";
import * as d3 from "d3";
import type { Signal, Trend, Scenario, ScenarioDraft, ScenarioAxis } from "@/lib/api";

// ── Shared colour maps ─────────────────────────────────────────────────────

const TYPE_FILL: Record<string, string> = {
  trend:       "#3b82f6",
  weak_signal: "#f59e0b",
  wildcard:    "#ef4444",
  driver:      "#a855f7",
  indicator:   "#14b8a6",
};

const STEEP_FILL: Record<string, string> = {
  social:         "#3b82f6",
  technological:  "#a855f7",
  economic:       "#22c55e",
  environmental:  "#10b981",
  political:      "#f97316",
};

const MOMENTUM_FILL: Record<string, string> = {
  increasing: "#22c55e",
  stable:     "#94a3b8",
  decreasing: "#ef4444",
};

// ── 1. Signal Scatter ──────────────────────────────────────────────────────
// X = importance_score, Y = novelty_score, colour = signal_type

interface SignalScatterProps {
  signals: Signal[];
  width?: number;
  height?: number;
}

export function SignalScatterChart({ signals, width = 720, height = 340 }: SignalScatterProps) {
  const margin = { top: 20, right: 20, bottom: 44, left: 50 };
  const iw = width - margin.left - margin.right;
  const ih = height - margin.top - margin.bottom;

  const x = d3.scaleLinear([0, 1], [0, iw]);
  const y = d3.scaleLinear([0, 1], [ih, 0]);

  const gxRef = useRef<SVGGElement>(null);
  const gyRef = useRef<SVGGElement>(null);

  const [tooltip, setTooltip] = useState<{ signal: Signal; px: number; py: number } | null>(null);

  useEffect(() => {
    if (gxRef.current) {
      d3.select(gxRef.current)
        .call(d3.axisBottom(x).ticks(5).tickSize(-ih).tickFormat(d3.format(".1f")))
        .call(g => g.select(".domain").remove())
        .call(g => g.selectAll(".tick line").attr("stroke", "#e2e8f0"))
        .call(g => g.selectAll(".tick text").attr("font-size", "12"));
    }
    if (gyRef.current) {
      d3.select(gyRef.current)
        .call(d3.axisLeft(y).ticks(4).tickSize(-iw).tickFormat(d3.format(".1f")))
        .call(g => g.select(".domain").remove())
        .call(g => g.selectAll(".tick line").attr("stroke", "#e2e8f0"))
        .call(g => g.selectAll(".tick text").attr("font-size", "12"));
    }
  });

  const types = Array.from(new Set(signals.map(s => s.signal_type ?? "unknown")));

  return (
    <div>
      <div className="relative">
        <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="overflow-visible">
          <g transform={`translate(${margin.left},${margin.top})`}>
            <g ref={gxRef} transform={`translate(0,${ih})`} className="text-muted-foreground" />
            <g ref={gyRef} className="text-muted-foreground" />

            {/* axis labels */}
            <text x={iw / 2} y={ih + 40} textAnchor="middle" fontSize={13} fill="#94a3b8">Importance</text>
            <text transform={`translate(-38,${ih / 2}) rotate(-90)`} textAnchor="middle" fontSize={13} fill="#94a3b8">Novelty</text>

            {/* data points */}
            {signals.map(s => (
              <circle
                key={s.id}
                cx={x(s.importance_score ?? 0)}
                cy={y(s.novelty_score ?? 0.5)}
                r={5}
                fill={TYPE_FILL[s.signal_type ?? ""] ?? "#94a3b8"}
                opacity={0.65}
                className="cursor-pointer hover:opacity-100"
                onMouseEnter={() => setTooltip({
                  signal: s,
                  px: (x(s.importance_score ?? 0) + margin.left) / width,
                  py: (y(s.novelty_score ?? 0.5) + margin.top) / height,
                })}
                onMouseLeave={() => setTooltip(null)}
              />
            ))}
          </g>
        </svg>

        {tooltip && (
          <div
            className="pointer-events-none absolute z-10 max-w-xs rounded-md border bg-popover px-3 py-2 shadow-md text-sm"
            style={{
              left: `calc(${tooltip.px * 100}% + 8px)`,
              top: `calc(${tooltip.py * 100}% - 8px)`,
              transform: tooltip.px > 0.7 ? "translateX(-100%)" : undefined,
            }}
          >
            <p className="font-medium leading-snug mb-1">{tooltip.signal.title}</p>
            <div className="text-xs text-muted-foreground space-y-0.5">
              <p>Type: <span className="capitalize">{(tooltip.signal.signal_type ?? "unknown").replace("_", " ")}</span></p>
              {tooltip.signal.steep_category && (
                <p>STEEP: <span className="capitalize">{tooltip.signal.steep_category}</span></p>
              )}
              <p>Importance: {(tooltip.signal.importance_score ?? 0).toFixed(2)}</p>
              <p>Novelty: {(tooltip.signal.novelty_score ?? 0).toFixed(2)}</p>
            </div>
          </div>
        )}
      </div>

      {/* legend */}
      <div className="flex flex-wrap gap-x-5 gap-y-1.5 mt-2">
        {types.map(t => (
          <div key={t} className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full shrink-0" style={{ background: TYPE_FILL[t] ?? "#94a3b8" }} />
            <span className="text-sm text-muted-foreground capitalize">{t.replace("_", " ")}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── 2. STEEP Donut ─────────────────────────────────────────────────────────

interface SteepDonutProps {
  signals: Signal[];
  size?: number;
}

export function SteepDonutChart({ signals, size = 240 }: SteepDonutProps) {
  const r = size / 2;
  const counts = d3.rollup(signals, v => v.length, d => d.steep_category ?? "unknown");
  const data = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);

  const pie = d3.pie<[string, number]>().value(d => d[1]).sort(null);
  const arc = d3.arc<d3.PieArcDatum<[string, number]>>()
    .innerRadius(r * 0.52)
    .outerRadius(r * 0.88);

  const slices = pie(data);

  return (
    <div className="flex items-center gap-6">
      <svg width={size} height={size}>
        <g transform={`translate(${r},${r})`}>
          {slices.map((slice, i) => (
            <path
              key={i}
              d={arc(slice) ?? ""}
              fill={STEEP_FILL[slice.data[0]] ?? "#94a3b8"}
              stroke="white"
              strokeWidth={2}
            />
          ))}
          <text textAnchor="middle" dy="0.35em" fontSize={16} fill="#64748b">
            {signals.length}
          </text>
          <text textAnchor="middle" dy="1.6em" fontSize={12} fill="#94a3b8">
            signals
          </text>
        </g>
      </svg>
      <div className="space-y-2">
        {data.map(([domain, count]) => (
          <div key={domain} className="flex items-center gap-2.5">
            <span className="h-3 w-3 rounded-sm shrink-0" style={{ background: STEEP_FILL[domain] ?? "#94a3b8" }} />
            <span className="text-sm text-muted-foreground capitalize w-32">{domain}</span>
            <span className="text-sm font-mono">{count}</span>
            <span className="text-sm text-muted-foreground">({Math.round(count / signals.length * 100)}%)</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── 3. Trend Momentum Bars ─────────────────────────────────────────────────
// Diverging horizontal bars centred at 0. Green = gaining, red = declining.

interface TrendMomentumProps {
  trends: Trend[];
  width?: number;
}

export function TrendMomentumChart({ trends, width = 720 }: TrendMomentumProps) {
  const sorted = [...trends].sort((a, b) => b.momentum - a.momentum);
  const rowH = 32;
  const margin = { top: 10, right: 56, bottom: 28, left: 210 };
  const height = sorted.length * rowH + margin.top + margin.bottom;
  const iw = width - margin.left - margin.right;
  const ih = height - margin.top - margin.bottom;

  const absMax = Math.max(...sorted.map(t => Math.abs(t.momentum)), 0.01);
  const x = d3.scaleLinear([-absMax, absMax], [0, iw]);

  const gxRef = useRef<SVGGElement>(null);
  const centerRef = useRef<SVGLineElement>(null);

  useEffect(() => {
    if (gxRef.current) {
      d3.select(gxRef.current)
        .call(d3.axisBottom(x).ticks(5).tickFormat(d3.format("+.2f")).tickSize(-ih))
        .call(g => g.select(".domain").remove())
        .call(g => g.selectAll(".tick line").attr("stroke", "#e2e8f0"))
        .call(g => g.selectAll(".tick text").attr("font-size", "12"));
    }
  });

  const zero = x(0);

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`}>
      <g transform={`translate(${margin.left},${margin.top})`}>
        {/* grid + axis */}
        <g ref={gxRef} transform={`translate(0,${ih})`} />

        {/* centre line */}
        <line x1={zero} y1={0} x2={zero} y2={ih} stroke="#cbd5e1" strokeDasharray="3 2" />

        {sorted.map((t, i) => {
          const y = i * rowH + rowH / 2;
          const barW = Math.abs(x(t.momentum) - zero);
          const barX = t.momentum >= 0 ? zero : zero - barW;
          const fill = t.momentum > 0.05 ? "#22c55e" : t.momentum < -0.05 ? "#ef4444" : "#94a3b8";

          return (
            <g key={t.id}>
              {/* bar */}
              <rect x={barX} y={y - 9} width={Math.max(barW, 2)} height={18} fill={fill} opacity={0.8} rx={2} />
              {/* label */}
              <text x={-8} y={y} textAnchor="end" dominantBaseline="middle" fontSize={12} fill="#64748b">
                {t.name.length > 28 ? t.name.slice(0, 27) + "…" : t.name}
              </text>
              {/* value */}
              <text
                x={t.momentum >= 0 ? zero + barW + 5 : zero - barW - 5}
                y={y}
                textAnchor={t.momentum >= 0 ? "start" : "end"}
                dominantBaseline="middle"
                fontSize={11}
                fill={fill}
                fontFamily="monospace"
              >
                {t.momentum >= 0 ? "+" : ""}{t.momentum.toFixed(2)}
              </text>
              {/* S-curve dot */}
              <circle
                cx={iw + 20}
                cy={y}
                r={5}
                fill={({
                  emergence: "#f59e0b",
                  early_growth: "#84cc16",
                  growth: "#22c55e",
                  maturity: "#3b82f6",
                  decline: "#94a3b8",
                } as Record<string, string>)[t.s_curve_position] ?? "#94a3b8"}
              >
                <title>{t.s_curve_position}</title>
              </circle>
            </g>
          );
        })}

        {/* S-curve legend label */}
        <text x={iw + 20} y={ih + 20} textAnchor="middle" fontSize={11} fill="#94a3b8">stage</text>
      </g>
    </svg>
  );
}

// ── 4. Scenario Quadrant ───────────────────────────────────────────────────
// 2×2 matrix with scenarios positioned by their axis poles.
// Circle size = relative evidence share. Colour = momentum state.

interface ScenarioQuadrantProps {
  scenarios: Scenario[];
  drafts: ScenarioDraft[];
  axis1: ScenarioAxis | undefined;
  axis2: ScenarioAxis | undefined;
  /** support score per scenario id → use simulated when panel open */
  supportValues?: Record<string, number>;
  totalMass?: number;
  size?: number;
}

export function ScenarioQuadrantChart({
  scenarios,
  drafts,
  axis1,
  axis2,
  supportValues,
  totalMass,
  size = 480,
}: ScenarioQuadrantProps) {
  // Map each live scenario to its draft to get quadrant pole info
  const draftByScenarioId = new Map(
    drafts
      .filter(d => d.approved_scenario_id)
      .map(d => [d.approved_scenario_id!, d])
  );

  const mass = totalMass ?? (scenarios.reduce((s, sc) => s + (supportValues?.[sc.id] ?? sc.support_score), 0) || 1);

  const margin = { top: 36, right: 36, bottom: 36, left: 36 };
  const iw = size - margin.left - margin.right;
  const ih = size - margin.top - margin.bottom;

  // Pole positions: low → 0.25, high → 0.75 (centre of each quadrant half)
  function poleToFrac(pole: string | undefined): number {
    return pole === "high" ? 0.75 : 0.25;
  }

  // Fallback positions for when draft info is missing: spread by index
  const FALLBACK: [number, number][] = [[0.25, 0.75], [0.75, 0.75], [0.25, 0.25], [0.75, 0.25]];

  const xScale = d3.scaleLinear([0, 1], [0, iw]);
  const yScale = d3.scaleLinear([0, 1], [ih, 0]); // y=1 at top

  // Max circle radius so bubbles fit in a quadrant
  const maxR = Math.min(iw, ih) * 0.18;
  const minR = 12;

  const shares = scenarios.map(sc => (supportValues?.[sc.id] ?? sc.support_score) / mass);
  const maxShare = Math.max(...shares, 0.01);
  const rScale = d3.scaleSqrt([0, maxShare], [minR, maxR]);

  return (
    <svg width="100%" viewBox={`0 0 ${size} ${size}`} className="overflow-visible">
      <g transform={`translate(${margin.left},${margin.top})`}>
        {/* quadrant lines */}
        <line x1={iw / 2} y1={0} x2={iw / 2} y2={ih} stroke="#e2e8f0" strokeWidth={1} />
        <line x1={0} y1={ih / 2} x2={iw} y2={ih / 2} stroke="#e2e8f0" strokeWidth={1} />

        {/* outer border */}
        <rect x={0} y={0} width={iw} height={ih} fill="none" stroke="#e2e8f0" strokeWidth={1} rx={4} />

        {/* axis pole labels */}
        {axis1 && (
          <>
            <text x={8} y={ih + 22} fontSize={9} fill="#94a3b8">{axis1.pole_low}</text>
            <text x={iw - 8} y={ih + 22} fontSize={9} fill="#94a3b8" textAnchor="end">{axis1.pole_high}</text>
            <text x={iw / 2} y={ih + 34} fontSize={9} fill="#cbd5e1" textAnchor="middle">{axis1.driver_name}</text>
          </>
        )}
        {axis2 && (
          <>
            <text x={-12} y={ih - 4} fontSize={9} fill="#94a3b8" textAnchor="end">{axis2.pole_low}</text>
            <text x={-12} y={14} fontSize={9} fill="#94a3b8" textAnchor="end">{axis2.pole_high}</text>
            <text
              transform={`translate(-30,${ih / 2}) rotate(-90)`}
              fontSize={9}
              fill="#cbd5e1"
              textAnchor="middle"
            >
              {axis2.driver_name}
            </text>
          </>
        )}

        {/* scenario bubbles */}
        {scenarios.map((sc, i) => {
          const draft = draftByScenarioId.get(sc.id);
          let fx: number, fy: number;
          if (draft) {
            fx = xScale(poleToFrac(draft.axis1_pole));
            fy = yScale(poleToFrac(draft.axis2_pole));
          } else {
            [fx, fy] = [xScale(FALLBACK[i % 4][0]), yScale(FALLBACK[i % 4][1])];
          }

          const share = shares[i];
          const r = rScale(share);
          const fill = MOMENTUM_FILL[sc.momentum_state] ?? "#94a3b8";

          return (
            <g key={sc.id}>
              {/* bubble */}
              <circle cx={fx} cy={fy} r={r} fill={fill} opacity={0.18} />
              <circle cx={fx} cy={fy} r={r} fill="none" stroke={fill} strokeWidth={1.5} />

              {/* scenario name — split at first space to fit two lines */}
              <text x={fx} y={fy - 6} textAnchor="middle" dominantBaseline="middle" fontSize={9} fill="#334155" fontWeight={600}>
                {sc.name.length > 22 ? sc.name.slice(0, 21) + "…" : sc.name}
              </text>

              {/* share % */}
              <text x={fx} y={fy + 10} textAnchor="middle" dominantBaseline="middle" fontSize={9} fill={fill} fontFamily="monospace">
                {Math.round(share * 100)}%
              </text>
            </g>
          );
        })}
      </g>
    </svg>
  );
}

