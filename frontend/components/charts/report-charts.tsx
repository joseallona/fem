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

interface ScenarioQuadrantProps {
  scenarios: Scenario[];
  drafts: ScenarioDraft[];
  axis1: ScenarioAxis | undefined;
  axis2: ScenarioAxis | undefined;
  supportValues?: Record<string, number>;
  totalMass?: number;
}

// Subtle quadrant tints: NW, NE, SW, SE
const Q_FILLS = ["#eff6ff", "#f0fdf4", "#fefce8", "#fdf4ff"];
const Q_BORDERS = ["#bfdbfe", "#bbf7d0", "#fde68a", "#e9d5ff"];

function wrapLabel(text: string, maxChars = 20): string[] {
  if (text.length <= maxChars) return [text];
  const words = text.split(" ");
  const lines: string[] = [];
  let line = "";
  for (const w of words) {
    const test = line ? `${line} ${w}` : w;
    if (test.length > maxChars && line) {
      lines.push(line);
      line = w;
      if (lines.length === 2) { line = line + "…"; break; }
    } else {
      line = test;
    }
  }
  if (line && lines.length < 3) lines.push(line);
  return lines.slice(0, 2);
}

function clip(text: string | undefined, max: number): string {
  if (!text) return "";
  return text.length > max ? text.slice(0, max - 1) + "…" : text;
}

// Extract a short 4-5 word concept from a long pole description
function shortConcept(text: string | undefined, maxWords = 5): string {
  if (!text) return "";
  const words = text.trim().split(/\s+/);
  if (words.length <= maxWords) return text;
  return words.slice(0, maxWords).join(" ") + "…";
}

export function ScenarioQuadrantChart({
  scenarios,
  drafts,
  axis1,
  axis2,
  supportValues,
  totalMass,
}: ScenarioQuadrantProps) {
  const draftByScenarioId = new Map(
    drafts.filter(d => d.approved_scenario_id).map(d => [d.approved_scenario_id!, d])
  );

  const rawMass = totalMass ?? (scenarios.reduce((s, sc) => s + (supportValues?.[sc.id] ?? sc.support_score), 0));
  const mass = rawMass || 1;
  const shares = scenarios.map(sc => (supportValues?.[sc.id] ?? sc.support_score) / mass);
  const allZero = shares.every(s => s === 0);

  // Layout — generous margins so axis labels sit cleanly outside the chart
  const W = 560, H = 560;
  const margin = { top: 48, right: 32, bottom: 80, left: 32 };
  const iw = W - margin.left - margin.right;
  const ih = H - margin.top - margin.bottom;
  const qw = iw / 2, qh = ih / 2;

  function poleToFrac(pole: string | undefined): number {
    return pole === "high" ? 0.75 : 0.25;
  }
  const FALLBACK: [number, number][] = [[0.25, 0.75], [0.75, 0.75], [0.25, 0.25], [0.75, 0.25]];

  const xScale = d3.scaleLinear([0, 1], [0, iw]);
  const yScale = d3.scaleLinear([0, 1], [ih, 0]);

  const BUBBLE_R = 38;
  const maxShare = Math.max(...shares, 0.01);
  const rScale = d3.scaleSqrt([0, maxShare], [BUBBLE_R * 0.6, BUBBLE_R * 1.3]);

  // Quadrant fills — ordered NW, NE, SW, SE
  const quadrants = [
    { x: 0,   y: 0,   fill: Q_FILLS[0], border: Q_BORDERS[0] },
    { x: qw,  y: 0,   fill: Q_FILLS[1], border: Q_BORDERS[1] },
    { x: 0,   y: qh,  fill: Q_FILLS[2], border: Q_BORDERS[2] },
    { x: qw,  y: qh,  fill: Q_FILLS[3], border: Q_BORDERS[3] },
  ];

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`}>
      <g transform={`translate(${margin.left},${margin.top})`}>

        {/* Quadrant background fills */}
        {quadrants.map((q, i) => (
          <rect key={i} x={q.x} y={q.y} width={qw} height={qh} fill={q.fill} />
        ))}

        {/* Quadrant dividers */}
        <line x1={iw / 2} y1={0} x2={iw / 2} y2={ih} stroke="#cbd5e1" strokeWidth={1.5} />
        <line x1={0} y1={ih / 2} x2={iw} y2={ih / 2} stroke="#cbd5e1" strokeWidth={1.5} />

        {/* Outer border */}
        <rect x={0} y={0} width={iw} height={ih} fill="none" stroke="#cbd5e1" strokeWidth={1.5} rx={6} />

        {/* ── X-axis labels (axis1) — inside chart edges, bottom ── */}
        {axis1 && (
          <>
            {/* pole_low: inside chart, bottom-left corner */}
            <g style={{ cursor: "default" }}>
              <title>{axis1.pole_low}</title>
              <text x={8} y={ih - 10} fontSize={10} fontWeight={500} fill="#475569" textAnchor="start">
                ← {shortConcept(axis1.pole_low)}
              </text>
            </g>
            {/* pole_high: inside chart, bottom-right corner */}
            <g style={{ cursor: "default" }}>
              <title>{axis1.pole_high}</title>
              <text x={iw - 8} y={ih - 10} fontSize={10} fontWeight={500} fill="#475569" textAnchor="end">
                {shortConcept(axis1.pole_high)} →
              </text>
            </g>
            {/* driver name: below chart */}
            <text x={iw / 2} y={ih + 28} fontSize={11} fill="#94a3b8" textAnchor="middle" fontStyle="italic">
              {clip(axis1.driver_name, 60)}
            </text>
          </>
        )}

        {/* ── Y-axis labels (axis2) — inside chart edges, left column ── */}
        {axis2 && (
          <>
            {/* pole_high: inside chart, top-left corner */}
            <g style={{ cursor: "default" }}>
              <title>{axis2.pole_high}</title>
              <text x={8} y={18} fontSize={10} fontWeight={500} fill="#475569" textAnchor="start">
                ↑ {shortConcept(axis2.pole_high)}
              </text>
            </g>
            {/* pole_low: inside chart, bottom-left corner — sits above x-axis label */}
            <g style={{ cursor: "default" }}>
              <title>{axis2.pole_low}</title>
              <text x={8} y={ih - 26} fontSize={10} fontWeight={500} fill="#475569" textAnchor="start">
                ↓ {shortConcept(axis2.pole_low)}
              </text>
            </g>
            {/* driver name: left of chart, rotated — position at absolute x≈14 */}
            <text
              transform={`translate(-20,${ih / 2}) rotate(-90)`}
              fontSize={11} fill="#94a3b8" textAnchor="middle" fontStyle="italic"
            >
              {clip(axis2.driver_name, 60)}
            </text>
          </>
        )}

        {/* ── Scenario bubbles ── */}
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
          const r = allZero ? BUBBLE_R : rScale(share);
          const fill = MOMENTUM_FILL[sc.momentum_state] ?? "#64748b";
          const nameLines = wrapLabel(sc.name, 20);
          const lineH = 14;
          // Name block sits above the bubble
          const nameBlockH = nameLines.length * lineH;
          const nameY = fy - r - 8 - nameBlockH;

          return (
            <g key={sc.id}>
              {/* Bubble fill */}
              <circle cx={fx} cy={fy} r={r} fill={fill} opacity={0.15} />
              {/* Bubble stroke */}
              <circle cx={fx} cy={fy} r={r} fill="none" stroke={fill} strokeWidth={2} />

              {/* Evidence % inside bubble — only if meaningful */}
              {!allZero && (
                <text
                  x={fx} y={fy}
                  textAnchor="middle" dominantBaseline="middle"
                  fontSize={11} fill={fill} fontWeight={700} fontFamily="monospace"
                >
                  {Math.round(share * 100)}%
                </text>
              )}

              {/* Scenario name above bubble, word-wrapped */}
              {nameLines.map((line, li) => (
                <text
                  key={li}
                  x={fx}
                  y={nameY + li * lineH}
                  textAnchor="middle"
                  dominantBaseline="hanging"
                  fontSize={12}
                  fontWeight={600}
                  fill="#1e293b"
                >
                  {line}
                </text>
              ))}

              {/* Momentum dot below bubble */}
              <circle cx={fx} cy={fy + r + 7} r={4} fill={fill} opacity={0.7} />
            </g>
          );
        })}

        {/* No evidence note */}
        {allZero && scenarios.length > 0 && (
          <text
            x={iw / 2} y={ih + 62}
            textAnchor="middle"
            fontSize={10}
            fill="#94a3b8"
            fontStyle="italic"
          >
            No evidence assigned yet — bubbles are equal size
          </text>
        )}
      </g>
    </svg>
  );
}

