"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, GitBranch } from "lucide-react";
import { api, type TrendScenarioMatrix } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

const HORIZON_COLOR: Record<string, string> = {
  H1: "bg-blue-100 text-blue-700",
  H2: "bg-violet-100 text-violet-700",
  H3: "bg-orange-100 text-orange-700",
};

const CONFIDENCE_COLOR: Record<string, string> = {
  high: "text-green-600",
  medium: "text-yellow-600",
  low: "text-muted-foreground",
};

const MOMENTUM_SYMBOL: Record<string, string> = {
  increasing: "↑",
  stable: "→",
  decreasing: "↓",
};

function cellColor(overlap: number, supports: number, weakens: number, maxOverlap: number): string {
  if (overlap === 0 || maxOverlap === 0) return "bg-muted/30";
  const intensity = overlap / maxOverlap; // 0..1
  const net = supports - weakens;
  if (net < 0) {
    // Mostly weakens — red scale
    const alpha = Math.round(intensity * 100);
    return `bg-red-${alpha >= 80 ? 200 : alpha >= 50 ? 100 : 50} border border-red-200`;
  }
  // Mostly supports — green scale
  if (intensity >= 0.8) return "bg-green-300 border border-green-400";
  if (intensity >= 0.5) return "bg-green-200 border border-green-300";
  if (intensity >= 0.25) return "bg-green-100 border border-green-200";
  return "bg-green-50 border border-green-100";
}

export default function TrendScenarioMatrixPage() {
  const { id: themeId } = useParams<{ id: string }>();
  const [matrix, setMatrix] = useState<TrendScenarioMatrix | null>(null);
  const [hoveredCell, setHoveredCell] = useState<{ trendId: string; scenarioId: string } | null>(null);

  useEffect(() => {
    api.scenarioPipeline.trendScenarioMatrix(themeId).then(setMatrix).catch(console.error);
  }, [themeId]);

  if (!matrix) {
    return (
      <div className="max-w-6xl mx-auto px-6 py-8">
        <p className="text-muted-foreground text-sm">Loading matrix…</p>
      </div>
    );
  }

  if (matrix.trends.length === 0 || matrix.scenarios.length === 0) {
    return (
      <div className="max-w-6xl mx-auto px-6 py-8">
        <BackLink themeId={themeId} />
        <p className="text-muted-foreground text-sm mt-6">
          No data yet — complete the scenario pipeline first.
        </p>
      </div>
    );
  }

  // Build lookup: trendId+scenarioId → cell
  const cellMap = new Map(
    matrix.cells.map((c) => [`${c.trend_id}:${c.scenario_id}`, c])
  );

  const maxOverlap = Math.max(...matrix.cells.map((c) => c.overlap), 1);

  const hoveredTrend = hoveredCell
    ? matrix.trends.find((t) => t.id === hoveredCell.trendId)
    : null;
  const hoveredScenario = hoveredCell
    ? matrix.scenarios.find((s) => s.id === hoveredCell.scenarioId)
    : null;
  const hoveredData = hoveredCell
    ? cellMap.get(`${hoveredCell.trendId}:${hoveredCell.scenarioId}`)
    : null;

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <BackLink themeId={themeId} />

      <div className="mt-6 mb-8">
        <h1 className="text-xl font-semibold">Trend × Scenario Matrix</h1>
        <p className="text-sm text-muted-foreground mt-1">
          How many signals from each trend are linked to each scenario. Darker green = stronger alignment.
        </p>
      </div>

      {/* Matrix */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              {/* top-left corner */}
              <th className="w-56 min-w-[14rem]" />
              {matrix.scenarios.map((s) => (
                <th
                  key={s.id}
                  className="pb-3 px-2 text-center align-bottom"
                  style={{ minWidth: "7rem" }}
                >
                  <div className="text-xs font-semibold leading-tight line-clamp-2">{s.name}</div>
                  <div className="flex items-center justify-center gap-1 mt-1">
                    <span className={`text-xs font-medium ${CONFIDENCE_COLOR[s.confidence_level] ?? "text-muted-foreground"}`}>
                      {s.confidence_level}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {MOMENTUM_SYMBOL[s.momentum_state] ?? ""}
                    </span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.trends.map((trend, ti) => (
              <tr key={trend.id} className={ti % 2 === 0 ? "bg-muted/20" : ""}>
                {/* Row header */}
                <td className="pr-4 py-2 align-middle">
                  <div className="text-xs font-medium leading-tight line-clamp-2">{trend.name}</div>
                  <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                    {trend.horizon && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${HORIZON_COLOR[trend.horizon] ?? "bg-muted text-muted-foreground"}`}>
                        {trend.horizon}
                      </span>
                    )}
                    <span className="text-[10px] text-muted-foreground">{trend.signal_count} signals</span>
                  </div>
                </td>

                {/* Cells */}
                {matrix.scenarios.map((scenario) => {
                  const cell = cellMap.get(`${trend.id}:${scenario.id}`) ?? {
                    trend_id: trend.id, scenario_id: scenario.id,
                    overlap: 0, supports: 0, weakens: 0,
                  };
                  const isHovered =
                    hoveredCell?.trendId === trend.id && hoveredCell?.scenarioId === scenario.id;

                  return (
                    <td
                      key={scenario.id}
                      className="px-2 py-1.5 text-center align-middle cursor-pointer transition-all"
                      onMouseEnter={() => setHoveredCell({ trendId: trend.id, scenarioId: scenario.id })}
                      onMouseLeave={() => setHoveredCell(null)}
                    >
                      <div
                        className={`rounded-md h-14 flex flex-col items-center justify-center gap-0.5 transition-transform ${
                          cellColor(cell.overlap, cell.supports, cell.weakens, maxOverlap)
                        } ${isHovered ? "scale-105 shadow-md" : ""}`}
                      >
                        <span className="text-base font-bold leading-none">
                          {cell.overlap > 0 ? cell.overlap : "–"}
                        </span>
                        {cell.overlap > 0 && (
                          <span className="text-[10px] text-muted-foreground leading-none">
                            {cell.supports > 0 && <span className="text-green-600">+{cell.supports}</span>}
                            {cell.supports > 0 && cell.weakens > 0 && " "}
                            {cell.weakens > 0 && <span className="text-red-500">−{cell.weakens}</span>}
                          </span>
                        )}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Hover detail card */}
      <div className="mt-6 min-h-[5rem]">
        {hoveredData && hoveredTrend && hoveredScenario && hoveredData.overlap > 0 ? (
          <Card className="border-dashed">
            <CardContent className="p-4 flex items-start gap-6">
              <div className="flex-1">
                <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Trend</p>
                <p className="text-sm font-medium">{hoveredTrend.name}</p>
                <div className="flex gap-1.5 mt-1 flex-wrap">
                  {hoveredTrend.steep_domains.map((d) => (
                    <Badge key={d} variant="secondary" className="text-xs">{d}</Badge>
                  ))}
                </div>
              </div>
              <div className="text-muted-foreground text-lg self-center">→</div>
              <div className="flex-1">
                <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Scenario</p>
                <p className="text-sm font-medium">{hoveredScenario.name}</p>
                <p className={`text-xs mt-1 ${CONFIDENCE_COLOR[hoveredScenario.confidence_level] ?? ""}`}>
                  {hoveredScenario.confidence_level} confidence · {hoveredScenario.momentum_state}
                </p>
              </div>
              <div className="text-center self-center px-4">
                <p className="text-2xl font-bold">{hoveredData.overlap}</p>
                <p className="text-xs text-muted-foreground">shared signals</p>
                <p className="text-xs mt-0.5">
                  <span className="text-green-600 font-medium">+{hoveredData.supports}</span>
                  {" / "}
                  <span className="text-red-500 font-medium">−{hoveredData.weakens}</span>
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <p className="text-xs text-muted-foreground">Hover over a cell to see details.</p>
        )}
      </div>

      {/* 2×2 Scenario Map */}
      {matrix.axes.length >= 2 && matrix.scenarios.some(s => s.axis1_pole) && (
        <ScenarioMap2x2 matrix={matrix} />
      )}

      {/* Legend */}
      <div className="mt-6 flex items-center gap-6">
        <p className="text-xs text-muted-foreground font-medium">Signal overlap:</p>
        <div className="flex items-center gap-1.5">
          <div className="w-6 h-6 rounded bg-muted/30" />
          <span className="text-xs text-muted-foreground">None</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-6 h-6 rounded bg-green-50 border border-green-100" />
          <span className="text-xs text-muted-foreground">Low</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-6 h-6 rounded bg-green-200 border border-green-300" />
          <span className="text-xs text-muted-foreground">Medium</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-6 h-6 rounded bg-green-300 border border-green-400" />
          <span className="text-xs text-muted-foreground">High</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-6 h-6 rounded bg-red-100 border border-red-200" />
          <span className="text-xs text-muted-foreground">Mostly weakens</span>
        </div>
      </div>
    </div>
  );
}

function BackLink({ themeId }: { themeId: string }) {
  return (
    <Link
      href={`/themes/${themeId}/scenario-pipeline`}
      className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="h-3.5 w-3.5" />
      Scenario Pipeline
    </Link>
  );
}

// ─── 2×2 Scenario Map ────────────────────────────────────────────────────────

const CONFIDENCE_DOT: Record<string, string> = {
  high: "bg-green-500",
  medium: "bg-yellow-400",
  low: "bg-muted-foreground",
};

function ScenarioMap2x2({ matrix }: { matrix: TrendScenarioMatrix }) {
  const axis1 = matrix.axes.find(a => a.axis_number === 1);
  const axis2 = matrix.axes.find(a => a.axis_number === 2);
  if (!axis1 || !axis2) return null;

  // Build per-scenario top trends (sorted by overlap desc)
  const topTrends = (scenarioId: string, n = 3) => {
    return matrix.cells
      .filter(c => c.scenario_id === scenarioId && c.overlap > 0)
      .sort((a, b) => b.overlap - a.overlap)
      .slice(0, n)
      .map(c => matrix.trends.find(t => t.id === c.trend_id))
      .filter(Boolean);
  };

  // Quadrant layout: [axis1_pole, axis2_pole] → grid position
  // axis1 = X (low left, high right), axis2 = Y (low bottom, high top)
  const quadrants: Array<{ a1: string; a2: string; col: number; row: number }> = [
    { a1: "low",  a2: "high", col: 1, row: 1 },
    { a1: "high", a2: "high", col: 2, row: 1 },
    { a1: "low",  a2: "low",  col: 1, row: 2 },
    { a1: "high", a2: "low",  col: 2, row: 2 },
  ];

  return (
    <div className="mt-12 mb-2">
      <h2 className="text-base font-semibold mb-1">2×2 Scenario Space</h2>
      <p className="text-sm text-muted-foreground mb-6">
        Each scenario positioned by its assumed axis poles. Top aligned trends listed per quadrant.
      </p>

      {/* Outer layout: Y-axis label + grid */}
      <div className="flex items-stretch gap-3">

        {/* Y-axis label */}
        <div className="flex flex-col items-center justify-center w-6 shrink-0">
          <span className="text-[10px] text-muted-foreground font-medium">{axis2.pole_high.split(" ").slice(0,3).join(" ")}…</span>
          <div className="flex-1 flex items-center justify-center my-2">
            <span
              className="text-[10px] font-semibold text-muted-foreground tracking-widest"
              style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
            >
              {axis2.driver_name}
            </span>
          </div>
          <span className="text-[10px] text-muted-foreground font-medium">{axis2.pole_low.split(" ").slice(0,3).join(" ")}…</span>
        </div>

        {/* Grid */}
        <div className="flex-1">
          <div
            className="grid gap-2"
            style={{ gridTemplateColumns: "1fr 1fr", gridTemplateRows: "1fr 1fr" }}
          >
            {quadrants.map(({ a1, a2, col, row }) => {
              const scenario = matrix.scenarios.find(
                s => s.axis1_pole === a1 && s.axis2_pole === a2
              );
              const trends = scenario ? topTrends(scenario.id) : [];
              const bgClass =
                a1 === "high" && a2 === "high" ? "bg-blue-50 border-blue-200" :
                a1 === "high" && a2 === "low"  ? "bg-amber-50 border-amber-200" :
                a1 === "low"  && a2 === "high" ? "bg-violet-50 border-violet-200" :
                "bg-rose-50 border-rose-200";

              return (
                <div
                  key={`${a1}-${a2}`}
                  className={`relative border rounded-lg p-4 min-h-[160px] flex flex-col gap-2 ${bgClass}`}
                  style={{ gridColumn: col, gridRow: row }}
                >
                  {/* Pole badge */}
                  <div className="flex gap-1.5 flex-wrap mb-1">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/70 border text-muted-foreground font-mono">
                      {axis1.driver_name?.split(" ")[0]} {a1}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/70 border text-muted-foreground font-mono">
                      {axis2.driver_name?.split(" ")[0]} {a2}
                    </span>
                  </div>

                  {scenario ? (
                    <>
                      <div className="flex items-start gap-2">
                        <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${CONFIDENCE_DOT[scenario.confidence_level] ?? "bg-muted"}`} />
                        <p className="text-sm font-semibold leading-snug">{scenario.name}</p>
                      </div>
                      <p className="text-[11px] text-muted-foreground">
                        {scenario.confidence_level} confidence · {MOMENTUM_SYMBOL[scenario.momentum_state] ?? "→"} {scenario.momentum_state}
                      </p>
                      {trends.length > 0 && (
                        <div className="mt-auto pt-2 border-t border-black/10">
                          <p className="text-[10px] text-muted-foreground mb-1.5 font-medium uppercase tracking-wide">Top aligned trends</p>
                          <div className="flex flex-col gap-1">
                            {trends.map(t => t && (
                              <div key={t.id} className="flex items-start gap-1.5">
                                <span className="text-[10px] text-muted-foreground shrink-0 mt-0.5">·</span>
                                <span className="text-xs leading-tight">{t.name}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="text-xs text-muted-foreground italic mt-auto">No scenario assigned to this quadrant</p>
                  )}
                </div>
              );
            })}
          </div>

          {/* X-axis label */}
          <div className="flex items-center justify-between mt-2 px-1">
            <span className="text-[10px] text-muted-foreground">{axis1.pole_low.split(" ").slice(0,4).join(" ")}…</span>
            <span className="text-[10px] font-semibold text-muted-foreground">{axis1.driver_name}</span>
            <span className="text-[10px] text-muted-foreground">{axis1.pole_high.split(" ").slice(0,4).join(" ")}…</span>
          </div>
        </div>
      </div>
    </div>
  );
}
