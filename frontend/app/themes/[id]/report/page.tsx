"use client";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Printer, BookOpen, Rss, Zap, Target, FileText, GitBranch, ScrollText, TrendingUp, AlertTriangle, Settings2, X } from "lucide-react";
import {
  api,
  type Theme, type Signal, type Trend, type Driver,
  type ScenarioAxis, type Scenario, type ScenarioDraft,
  type SignalLinkOut, type PipelineStatus,
} from "@/lib/api";
import dynamic from "next/dynamic";

const SignalScatterChart = dynamic(
  () => import("@/components/charts/report-charts").then((m) => m.SignalScatterChart),
  { ssr: false }
);
const SteepDonutChart = dynamic(
  () => import("@/components/charts/report-charts").then((m) => m.SteepDonutChart),
  { ssr: false }
);
const TrendMomentumChart = dynamic(
  () => import("@/components/charts/report-charts").then((m) => m.TrendMomentumChart),
  { ssr: false }
);
const ScenarioQuadrantChart = dynamic(
  () => import("@/components/charts/report-charts").then((m) => m.ScenarioQuadrantChart),
  { ssr: false }
);

// ── Mapping simulation (mirrors scoring.py / suggest_scenario_mapping) ────
// Replicates the Python tokeniser so the browser can re-run the mapping live.

const SIM_STOPWORDS = new Set([
  "the","and","for","that","this","with","are","was","has","scenario",
  "not","but","from","they","have","will","its","been","can","new","more",
  "also","into","than","then","when","which","who","how","our","their",
]);
const SIM_NEGATION = new Set([
  "not","decline","fail","against","ban","block","oppose","stall","reject",
]);

function simTokenize(text: string): Set<string> {
  const tokens = text.toLowerCase().match(/[a-z]{3,}/g) ?? [];
  return new Set(tokens.filter((t) => !SIM_STOPWORDS.has(t)));
}

function simMapRel(
  signal: Signal,
  scenario: Scenario,
  threshold: number,
  steepBoost: number,
): "supports" | "weakens" | null {
  const sigText  = `${signal.title ?? ""} ${signal.summary ?? ""}`;
  const scText   = `${scenario.name ?? ""} ${scenario.narrative ?? ""} ${
    Array.isArray(scenario.assumptions) ? (scenario.assumptions as string[]).join(" ") : ""
  }`;
  if (!scText.trim()) return null;
  const st  = simTokenize(sigText);
  const sct = simTokenize(scText);
  if (!st.size || !sct.size) return null;
  const inter = new Set(Array.from(st).filter((t) => sct.has(t)));
  let overlap = inter.size / Math.min(st.size, sct.size);
  if (signal.steep_category && scText.toLowerCase().includes(signal.steep_category.toLowerCase())) {
    overlap += steepBoost;
  }
  const negAdj = Array.from(inter).some((t) => SIM_NEGATION.has(t)) ||
    Array.from(st).some((t) => SIM_NEGATION.has(t) && sct.has(t));
  if (overlap > threshold) return negAdj ? "weakens" : "supports";
  return null;
}

// ── Helpers ───────────────────────────────────────────────────────────────

const TYPE_COLOR: Record<string, string> = {
  trend:       "bg-blue-100 text-blue-800",
  weak_signal: "bg-amber-100 text-amber-800",
  wildcard:    "bg-red-100 text-red-800",
  driver:      "bg-purple-100 text-purple-800",
  indicator:   "bg-teal-100 text-teal-800",
};
const TYPE_LABEL: Record<string, string> = {
  trend: "Trend", weak_signal: "Weak Signal", wildcard: "Wildcard",
  driver: "Driver", indicator: "Indicator",
};
const STEEP_COLOR: Record<string, string> = {
  social: "bg-blue-50 text-blue-700",
  technological: "bg-purple-50 text-purple-700",
  economic: "bg-green-50 text-green-700",
  environmental: "bg-emerald-50 text-emerald-700",
  political: "bg-orange-50 text-orange-700",
};
const STEEP_LABEL: Record<string, string> = {
  social: "Social", technological: "Technological", economic: "Economic",
  environmental: "Environmental", political: "Political",
};
const HORIZON_LABEL: Record<string, string> = {
  H1: "Present (0–2 yrs)", H2: "Transition (2–7 yrs)", H3: "Future (7+ yrs)",
};
const MOMENTUM_LABEL: Record<string, string> = {
  increasing: "Gaining momentum", stable: "Holding steady", decreasing: "Losing momentum",
};
const CONFIDENCE_LABEL: Record<string, string> = {
  high: "High confidence", medium: "Medium confidence", low: "Low confidence",
};
const S_CURVE_LABEL: Record<string, string> = {
  emergence: "Emerging", early_growth: "Early growth", growth: "Growing",
  maturity: "Mature", decline: "Declining",
};

function pct(n: number) { return `${Math.round(n * 100)}%`; }

function groupBy<T>(arr: T[], key: (item: T) => string): Record<string, T[]> {
  return arr.reduce((acc, item) => {
    const k = key(item);
    (acc[k] = acc[k] ?? []).push(item);
    return acc;
  }, {} as Record<string, T[]>);
}

// ── Section wrapper ───────────────────────────────────────────────────────

function Section({ n, title, lead, children, action }: {
  n: number; title: string; lead: string; children: React.ReactNode; action?: React.ReactNode;
}) {
  return (
    <section className="mb-14 print:mb-10 print:break-inside-avoid">
      <div className="flex items-center gap-3 mb-2">
        <span className="text-3xl font-light text-muted-foreground/40 tabular-nums select-none leading-none">{String(n).padStart(2, "0")}</span>
        <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
        {action && <div className="ml-auto print:hidden">{action}</div>}
      </div>
      <p className="text-sm text-muted-foreground leading-relaxed mb-5 max-w-2xl italic">{lead}</p>
      {children}
    </section>
  );
}

// ── Mini bar ──────────────────────────────────────────────────────────────

function Bar({ value, color = "bg-primary", max = 1 }: { value: number; color?: string; max?: number }) {
  const w = Math.round((value / max) * 100);
  return (
    <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${w}%` }} />
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────

function fetchOrEmpty<T>(p: Promise<T[]>): Promise<{ data: T[]; error: string | null }> {
  return p
    .then((data) => ({ data, error: null }))
    .catch((e: unknown) => ({ data: [] as T[], error: e instanceof Error ? e.message : String(e) }));
}

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const [theme, setTheme] = useState<Theme | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [trends, setTrends] = useState<Trend[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [axes, setAxes] = useState<ScenarioAxis[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [drafts, setDrafts] = useState<ScenarioDraft[]>([]);
  const [signalLinks, setSignalLinks] = useState<Record<string, SignalLinkOut[]>>({});
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // ── Scenario mapping simulator state ────────────────────────────────────
  const [showSimPanel, setShowSimPanel] = useState(false);
  const [simThreshold, setSimThreshold]   = useState(0.08);
  const [simSteepBoost, setSimSteepBoost] = useState(0.08);
  const [simWindowDays, setSimWindowDays] = useState(30);

  useEffect(() => {
    async function load() {
      try {
        const [theme, signalsRes, trendsRes, driversRes, axesRes, scenariosRes, draftsRes, statusRes] =
          await Promise.all([
            api.themes.get(id),
            fetchOrEmpty(api.signals.list(id)),
            fetchOrEmpty(api.scenarioPipeline.trends(id)),
            fetchOrEmpty(api.scenarioPipeline.drivers(id)),
            fetchOrEmpty(api.scenarioPipeline.axes(id)),
            fetchOrEmpty(api.scenarios.list(id)),
            fetchOrEmpty(api.scenarioPipeline.drafts(id)),
            api.scenarioPipeline.status(id).catch((e: unknown) => {
              console.error("status fetch failed:", e);
              return null;
            }),
          ]);

        setTheme(theme);
        setSignals(signalsRes.data);
        setTrends(trendsRes.data);
        setDrivers(driversRes.data);
        setAxes(axesRes.data);
        setScenarios(scenariosRes.data);
        setDrafts(draftsRes.data);
        setStatus(statusRes);

        // Fetch signal links for each live scenario in parallel
        if (scenariosRes.data.length > 0) {
          const linksMap: Record<string, SignalLinkOut[]> = {};
          await Promise.all(
            scenariosRes.data.map(async (sc) => {
              try {
                linksMap[sc.id] = await api.scenarios.getSignals(sc.id);
              } catch {
                linksMap[sc.id] = [];
              }
            })
          );
          setSignalLinks(linksMap);
        }

        // Collect any section-level errors so they render inline
        const errs: Record<string, string> = {};
        if (signalsRes.error)   errs.signals   = signalsRes.error;
        if (trendsRes.error)    errs.trends     = trendsRes.error;
        if (driversRes.error)   errs.drivers    = driversRes.error;
        if (axesRes.error)      errs.axes       = axesRes.error;
        if (scenariosRes.error) errs.scenarios  = scenariosRes.error;
        if (Object.keys(errs).length) console.error("Report fetch errors:", errs);
        setErrors(errs);
      } catch (e) {
        console.error("Report top-level fetch error:", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  // Client-side mapping simulation — must be before early returns (Rules of Hooks)
  const simScores = useMemo(() => {
    if (!showSimPanel || scenarios.length === 0) return null;
    const cutoff = new Date(Date.now() - simWindowDays * 86_400_000);
    const result: Record<string, { support: number; contradiction: number; nSupporting: number; nWeakening: number; nUnmatched: number }> = {};
    for (const sc of scenarios) {
      let support = 0, contradiction = 0, nSupporting = 0, nWeakening = 0, nUnmatched = 0;
      for (const sig of signals) {
        if (new Date(sig.created_at) < cutoff) continue;
        const rel = simMapRel(sig, sc, simThreshold, simSteepBoost);
        const w = sig.importance_score * 0.5;
        if (rel === "supports")     { support += w;        nSupporting++; }
        else if (rel === "weakens") { contradiction += w;  nWeakening++;  }
        else                        { nUnmatched++; }
      }
      result[sc.id] = { support, contradiction, nSupporting, nWeakening, nUnmatched };
    }
    return result;
  }, [showSimPanel, scenarios, signals, simThreshold, simSteepBoost, simWindowDays]);

  if (loading) return <div className="p-8 text-muted-foreground text-sm">Loading report…</div>;
  if (!theme) return <div className="p-8 text-muted-foreground text-sm">Theme not found.</div>;

  // Fallback: approved (or any non-rejected) drafts shown when no live scenarios exist
  const visibleDrafts = scenarios.length === 0
    ? drafts.filter((d) => d.status !== "rejected")
    : [];

  // Relative evidence weight: each scenario's share of total support mass
  const totalSupportMass = scenarios.reduce((sum, sc) => sum + sc.support_score, 0) || 1;

  const simTotalMass = simScores
    ? Object.values(simScores).reduce((s, v) => s + v.support, 0) || 1
    : totalSupportMass;

  // Derived data
  const typeGroups = groupBy(signals, (s) => s.signal_type ?? "unknown");
  const steepGroups = groupBy(signals, (s) => s.steep_category ?? "unknown");
  const horizonGroups = groupBy(signals, (s) => s.horizon ?? "unknown");
  const topSignals = [...signals].sort((a, b) => b.importance_score - a.importance_score).slice(0, 5);
  const predetermined = drivers.filter((d) => d.is_predetermined);
  const uncertainties = drivers.filter((d) => !d.is_predetermined);
  const topDrivers = [...uncertainties].sort((a, b) => (b.impact_score * b.uncertainty_score) - (a.impact_score * a.uncertainty_score)).slice(0, 6);
  const axis1 = axes.find((a) => a.axis_number === 1);
  const axis2 = axes.find((a) => a.axis_number === 2);
  const stakeholders = Array.isArray(theme.stakeholders_json) ? (theme.stakeholders_json as string[]) : [];
  const generatedOn = new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });

  const navItems = [
    { label: "Dashboard",         href: `/themes/${id}`,                   icon: BookOpen },
    { label: "Sources",           href: `/themes/${id}/sources`,           icon: Rss },
    { label: "Signals",           href: `/themes/${id}/signals`,           icon: Zap },
    { label: "Scenarios",         href: `/themes/${id}/scenarios`,         icon: Target },
    { label: "Scenario Pipeline", href: `/themes/${id}/scenario-pipeline`, icon: GitBranch },
    { label: "Briefs",            href: `/themes/${id}/briefs`,            icon: FileText },
    { label: "Report",            href: `/themes/${id}/report`,            icon: ScrollText },
  ];

  return (
    <div className="max-w-4xl mx-auto px-8 pb-20">

      {/* Nav — hidden when printing */}
      <div className="print:hidden">
        <div className="mb-2 pt-8">
          <Link href="/themes" className="text-sm text-muted-foreground hover:underline">← Themes</Link>
        </div>
        <div className="flex gap-1 mb-10 border-b overflow-x-auto">
          {navItems.map(({ label, href, icon: Icon }) => (
            <Link key={href} href={href} className={`flex items-center gap-1.5 px-4 py-2 text-sm border-b-2 whitespace-nowrap transition-colors ${href === `/themes/${id}/report` ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground hover:border-primary"}`}>
              <Icon className="h-3.5 w-3.5" />{label}
            </Link>
          ))}
        </div>
      </div>

      {/* Report header */}
      <header className="mb-14 print:mb-10">
        <div className="flex items-start justify-between gap-4 mb-1">
          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-2">Strategic Foresight Report</p>
            <h1 className="text-4xl font-bold tracking-tight leading-tight">{theme.name}</h1>
          </div>
          <button
            onClick={() => window.print()}
            className="print:hidden flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground border rounded-md px-3 py-1.5 shrink-0"
          >
            <Printer className="h-4 w-4" /> Print / PDF
          </button>
        </div>
        {theme.focal_question && (
          <p className="text-lg text-muted-foreground mt-3 leading-relaxed max-w-2xl">{theme.focal_question}</p>
        )}
        <div className="flex flex-wrap gap-4 mt-5 text-xs text-muted-foreground">
          {theme.time_horizon && <span>Time horizon: <strong className="text-foreground">{theme.time_horizon}</strong></span>}
          <span>Generated: <strong className="text-foreground">{generatedOn}</strong></span>
          <span>Signals analysed: <strong className="text-foreground">{signals.length}</strong></span>
          {scenarios.length > 0 && <span>Scenarios: <strong className="text-foreground">{scenarios.length}</strong></span>}
          {scenarios.length === 0 && visibleDrafts.length > 0 && <span>Scenario drafts: <strong className="text-foreground">{visibleDrafts.length}</strong></span>}
        </div>
      </header>

      {/* ── 01  The Question ──────────────────────────────────────────── */}
      <Section n={1} title="The Question" lead="Every foresight exercise begins with a focal question — a specific, bounded inquiry that gives direction to the analysis and ensures that what we find is relevant to a real strategic decision.">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {theme.focal_question && (
            <div className="bg-primary/5 border border-primary/20 rounded-xl p-5">
              <p className="text-xs font-medium text-primary uppercase tracking-wider mb-2">Focal Question</p>
              <p className="text-base font-medium leading-snug">{theme.focal_question}</p>
            </div>
          )}
          {theme.scope_text && (
            <div className="bg-muted/50 rounded-xl p-5">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Scope</p>
              <p className="text-sm text-foreground leading-relaxed">{theme.scope_text}</p>
            </div>
          )}
          {theme.description && (
            <div className="md:col-span-2 bg-muted/30 rounded-xl p-5">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Context</p>
              <p className="text-sm leading-relaxed">{theme.description}</p>
            </div>
          )}
          {stakeholders.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Stakeholders</p>
              <div className="flex flex-wrap gap-1.5">
                {stakeholders.map((s, i) => (
                  <span key={i} className="text-xs bg-muted px-2 py-0.5 rounded-full">{String(s)}</span>
                ))}
              </div>
            </div>
          )}
          {theme.related_subjects_json?.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Related subjects</p>
              <div className="flex flex-wrap gap-1.5">
                {theme.related_subjects_json.map((s, i) => (
                  <span key={i} className="text-xs bg-muted px-2 py-0.5 rounded-full">{s}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </Section>

      {/* ── 02  Signals from the Field ───────────────────────────────── */}
      {signals.length > 0 && (
        <Section n={2} title="Signals from the Field" lead={`The system continuously scanned ${signals.length} signals — discrete pieces of evidence collected from open sources that indicate change is underway. Each signal was classified by type, STEEP domain, and time horizon to reveal the landscape of change.`}>
          {/* Type breakdown */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
            {Object.entries(typeGroups).sort((a, b) => b[1].length - a[1].length).map(([type, list]) => (
              <div key={type} className="flex items-center gap-3 bg-muted/40 rounded-lg p-3">
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${TYPE_COLOR[type] ?? "bg-muted text-muted-foreground"}`}>
                  {TYPE_LABEL[type] ?? type}
                </span>
                <span className="text-2xl font-bold ml-auto">{list.length}</span>
              </div>
            ))}
          </div>

          {/* STEEP donut */}
          <div className="mb-6">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">By domain (STEEP)</p>
            <SteepDonutChart signals={signals} />
          </div>

          {/* Horizon breakdown */}
          {Object.keys(horizonGroups).length > 1 && (
            <div className="mb-6">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">By time horizon</p>
              <div className="flex gap-4">
                {["H1", "H2", "H3"].filter((h) => horizonGroups[h]).map((h) => (
                  <div key={h} className="flex-1 text-center bg-muted/40 rounded-lg p-4">
                    <p className="text-2xl font-bold">{horizonGroups[h]?.length ?? 0}</p>
                    <p className="text-xs text-muted-foreground mt-1">{HORIZON_LABEL[h]}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Top signals */}
          <div className="mb-6">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">Highest-importance signals</p>
            <div className="space-y-3">
              {topSignals.map((s, i) => (
                <div key={s.id} className="flex gap-3">
                  <span className="text-muted-foreground/40 text-sm font-mono mt-0.5 w-4 shrink-0">{i + 1}</span>
                  <div className="flex-1 border-l pl-3">
                    <div className="flex items-start gap-2 flex-wrap">
                      <p className="text-sm font-medium flex-1">{s.title}</p>
                      {s.signal_type && (
                        <span className={`text-xs px-1.5 py-0.5 rounded-full shrink-0 ${TYPE_COLOR[s.signal_type] ?? "bg-muted"}`}>
                          {TYPE_LABEL[s.signal_type] ?? s.signal_type}
                        </span>
                      )}
                    </div>
                    {s.summary && <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{s.summary}</p>}
                    <div className="flex items-center gap-2 mt-1.5">
                      <Bar value={s.importance_score} color="bg-primary" />
                      <span className="text-xs text-muted-foreground font-mono w-8">{pct(s.importance_score)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Signal scatter: importance vs novelty */}
          <div className="mb-6">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">Importance vs. novelty</p>
            <SignalScatterChart signals={signals} />
          </div>
        </Section>
      )}

      {/* ── 03  Synthesized Trends ───────────────────────────────────── */}
      {trends.length > 0 && (
        <Section n={3} title="Synthesized Trends" lead="Signals do not speak alone. The system grouped signals that share vocabulary and timing into trends — coherent patterns of change that persist across multiple sources. Each trend represents a detectable trajectory shaping the future.">
          {/* Momentum chart — coloured bars diverging from 0; dot = S-curve stage */}
          <div className="mb-6">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">Momentum by trend</p>
            <TrendMomentumChart trends={trends} />
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
              {[
                ["#f59e0b", "Emergence"],
                ["#84cc16", "Early growth"],
                ["#22c55e", "Growth"],
                ["#3b82f6", "Maturity"],
                ["#94a3b8", "Decline"],
              ].map(([color, label]) => (
                <div key={label} className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ background: color }} />
                  <span className="text-xs text-muted-foreground">{label}</span>
                </div>
              ))}
              <span className="text-xs text-muted-foreground ml-auto">dot = S-curve stage</span>
            </div>
          </div>

          {/* Trend detail cards */}
          <div className="space-y-3">
            {trends.map((t) => (
              <div key={t.id} className="border rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <TrendingUp className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-semibold">{t.name}</p>
                      {t.horizon && <span className="text-xs bg-muted px-2 py-0.5 rounded">{t.horizon} · {HORIZON_LABEL[t.horizon]}</span>}
                      <span className="text-xs bg-muted px-2 py-0.5 rounded ml-auto">{S_CURVE_LABEL[t.s_curve_position] ?? t.s_curve_position}</span>
                    </div>
                    {t.description && <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{t.description}</p>}
                    <div className="flex items-center gap-2 flex-wrap mt-2">
                      {t.steep_domains.map((d) => (
                        <span key={d} className={`text-xs px-1.5 py-0.5 rounded ${STEEP_COLOR[d] ?? "bg-muted"}`}>{STEEP_LABEL[d] ?? d}</span>
                      ))}
                      <span className="ml-auto text-xs text-muted-foreground">{t.signal_count} signals</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* ── 04  Drivers of Change ────────────────────────────────────── */}
      {drivers.length > 0 && (
        <Section n={4} title="Drivers of Change" lead="Trends have causes. Drivers are the underlying forces — structural, economic, political, technological — that explain why trends exist. Foresight distinguishes between predetermined elements (which will shape the future regardless of what we do) and critical uncertainties (whose outcome is genuinely open).">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Predetermined */}
            {predetermined.length > 0 && (
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">Predetermined Forces</p>
                <p className="text-xs text-muted-foreground mb-3 italic">These forces will influence the future regardless of decisions made today.</p>
                <div className="space-y-2">
                  {predetermined.map((d) => (
                    <div key={d.id} className="flex items-start gap-2 bg-muted/40 rounded-lg p-3">
                      <div className="flex-1">
                        <p className="text-xs font-medium">{d.name}</p>
                        {d.description && <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{d.description}</p>}
                      </div>
                      <span className="text-xs font-mono bg-background border rounded px-1.5 py-0.5 shrink-0">Impact {d.impact_score.toFixed(1)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Critical uncertainties */}
            {topDrivers.length > 0 && (
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">Critical Uncertainties</p>
                <p className="text-xs text-muted-foreground mb-3 italic">High impact, high uncertainty — the forces whose outcome will most determine which future emerges.</p>
                <div className="space-y-2">
                  {topDrivers.map((d) => (
                    <div key={d.id} className="border rounded-lg p-3">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-xs font-medium">{d.name}</p>
                        {d.steep_domain && (
                          <span className={`text-xs px-1.5 py-0.5 rounded shrink-0 ${STEEP_COLOR[d.steep_domain] ?? "bg-muted"}`}>
                            {STEEP_LABEL[d.steep_domain] ?? d.steep_domain}
                          </span>
                        )}
                      </div>
                      {d.description && <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{d.description}</p>}
                      <div className="flex gap-4 mt-2">
                        <div className="flex items-center gap-1.5 flex-1">
                          <span className="text-xs text-muted-foreground w-12">Impact</span>
                          <Bar value={d.impact_score} max={10} color="bg-red-400" />
                          <span className="text-xs font-mono w-4">{d.impact_score.toFixed(0)}</span>
                        </div>
                        <div className="flex items-center gap-1.5 flex-1">
                          <span className="text-xs text-muted-foreground w-16">Uncertainty</span>
                          <Bar value={d.uncertainty_score} max={10} color="bg-purple-400" />
                          <span className="text-xs font-mono w-4">{d.uncertainty_score.toFixed(0)}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Section>
      )}

      {/* ── 05  The Uncertainty Map ──────────────────────────────────── */}
      {(axis1 || axis2) && (
        <Section n={5} title="The Uncertainty Map" lead="From all the drivers analysed, two were selected as the most consequential and most uncertain. These become the axes of a 2×2 scenario matrix — the backbone of the scenario analysis. Each axis defines a spectrum between two plausible poles.">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {[axis1, axis2].filter(Boolean).map((ax, i) => (
              <div key={ax!.id} className="border-2 border-primary/20 rounded-xl p-5">
                <p className="text-xs font-medium text-primary uppercase tracking-wider mb-2">Axis {i + 1}{ax!.driver_name ? ` — ${ax!.driver_name}` : ""}</p>
                <div className="flex items-stretch gap-3 mt-3">
                  <div className="flex-1 bg-muted/40 rounded-lg p-3 text-center">
                    <p className="text-xs text-muted-foreground mb-1">One extreme</p>
                    <p className="text-sm font-semibold">{ax!.pole_low ?? "—"}</p>
                  </div>
                  <div className="flex items-center text-muted-foreground/40 text-lg">↔</div>
                  <div className="flex-1 bg-muted/40 rounded-lg p-3 text-center">
                    <p className="text-xs text-muted-foreground mb-1">Other extreme</p>
                    <p className="text-sm font-semibold">{ax!.pole_high ?? "—"}</p>
                  </div>
                </div>
                {ax!.rationale && <p className="text-xs text-muted-foreground mt-3 italic leading-relaxed">{ax!.rationale}</p>}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* ── 06  Four Possible Futures ────────────────────────────────── */}
      {errors.scenarios && (
        <div className="mb-8 rounded-md border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          <strong>Could not load scenarios:</strong> {errors.scenarios}
        </div>
      )}
      {(scenarios.length > 0 || visibleDrafts.length > 0) && (
        <Section
          n={6}
          title="Four Possible Futures"
          lead="Each quadrant of the axis matrix produces a distinct, internally consistent world. These are not predictions — they are plausible future states that could emerge depending on how the critical uncertainties resolve. The goal is not to bet on one but to be prepared for all."
          action={
            <button
              onClick={() => setShowSimPanel((v) => !v)}
              className={`flex items-center gap-1.5 text-xs border rounded-md px-2.5 py-1.5 transition-colors ${showSimPanel ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground hover:text-foreground"}`}
              title="Tweak mapping parameters"
            >
              <Settings2 className="h-3.5 w-3.5" />
              Mapping settings
            </button>
          }
        >
          {/* ── Simulator panel ──────────────────────────────────────────── */}
          {showSimPanel && (
            <div className="mb-6 border rounded-xl bg-muted/30 p-5 space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold">Signal → Scenario Mapping Simulator</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Adjust parameters below to see how they change which signals get assigned to each scenario.
                    Changes are client-side only — they don't affect the database.
                  </p>
                </div>
                <button onClick={() => setShowSimPanel(false)} className="text-muted-foreground hover:text-foreground">
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Overlap threshold */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-medium">Overlap threshold</label>
                    <span className="text-xs font-mono bg-background border rounded px-1.5 py-0.5">{simThreshold.toFixed(2)}</span>
                  </div>
                  <input
                    type="range" min={0.01} max={0.40} step={0.01}
                    value={simThreshold}
                    onChange={(e) => setSimThreshold(parseFloat(e.target.value))}
                    className="w-full accent-primary"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Minimum token overlap for a signal to be assigned to a scenario.
                    Higher = stricter, fewer assignments.
                  </p>
                </div>

                {/* STEEP boost */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-medium">STEEP category boost</label>
                    <span className="text-xs font-mono bg-background border rounded px-1.5 py-0.5">{simSteepBoost.toFixed(2)}</span>
                  </div>
                  <input
                    type="range" min={0} max={0.30} step={0.01}
                    value={simSteepBoost}
                    onChange={(e) => setSimSteepBoost(parseFloat(e.target.value))}
                    className="w-full accent-primary"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Extra overlap added when the signal's STEEP category appears in the scenario text.
                    Set to 0 to disable domain boosting.
                  </p>
                </div>

                {/* Window days */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-medium">Look-back window</label>
                    <span className="text-xs font-mono bg-background border rounded px-1.5 py-0.5">{simWindowDays}d</span>
                  </div>
                  <input
                    type="range" min={7} max={180} step={1}
                    value={simWindowDays}
                    onChange={(e) => setSimWindowDays(parseInt(e.target.value))}
                    className="w-full accent-primary"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Only signals created within this many days are included in scoring.
                    Currently {signals.filter(s => new Date(s.created_at) >= new Date(Date.now() - simWindowDays * 86_400_000)).length} of {signals.length} signals qualify.
                  </p>
                </div>
              </div>

              {/* Per-scenario simulation breakdown */}
              {simScores && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Simulated assignment breakdown</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {scenarios.map((sc) => {
                      const s = simScores[sc.id];
                      const share = s.support / simTotalMass;
                      return (
                        <div key={sc.id} className="flex items-center gap-3 bg-background rounded-lg border px-3 py-2">
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium truncate">{sc.name}</p>
                            <div className="flex gap-3 mt-0.5 text-xs text-muted-foreground">
                              <span className="text-green-600">{s.nSupporting} supporting</span>
                              <span className="text-red-500">{s.nWeakening} weakening</span>
                              <span>{s.nUnmatched} unmatched</span>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                              <div className="h-full bg-primary rounded-full" style={{ width: `${Math.round(share * 100)}%` }} />
                            </div>
                            <span className="text-xs font-mono w-8 text-right">{Math.round(share * 100)}%</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Live scenarios ─────────────────────────────────────────── */}
          {scenarios.length > 0 && (
            <>
              <div className={`grid gap-5 ${scenarios.length === 4 ? "grid-cols-1 md:grid-cols-2" : "grid-cols-1"}`}>
                {scenarios.map((sc) => {
                  const links = signalLinks[sc.id] ?? [];
                  const confirmed = links.filter((l) => l.user_confirmed);
                  const supporting = confirmed.filter((l) => l.relationship_type === "supports");
                  const weakening = confirmed.filter((l) => l.relationship_type === "weakens");
                  const suggested = links.filter((l) => !l.user_confirmed);

                  return (
                    <div key={sc.id} className="border rounded-xl overflow-hidden">
                      {/* Scenario header */}
                      <div className="bg-muted/50 px-5 py-4 flex items-start justify-between gap-3">
                        <h3 className="text-base font-bold leading-tight">{sc.name}</h3>
                        <div className="flex flex-col items-end gap-1 shrink-0">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            sc.confidence_level === "high" ? "bg-green-100 text-green-700" :
                            sc.confidence_level === "medium" ? "bg-yellow-100 text-yellow-700" :
                            "bg-muted text-muted-foreground"
                          }`}>
                            {CONFIDENCE_LABEL[sc.confidence_level] ?? sc.confidence_level}
                          </span>
                          <span className={`text-xs ${
                            sc.momentum_state === "increasing" ? "text-green-600" :
                            sc.momentum_state === "decreasing" ? "text-red-500" :
                            "text-muted-foreground"
                          }`}>
                            {MOMENTUM_LABEL[sc.momentum_state] ?? sc.momentum_state}
                          </span>
                        </div>
                      </div>

                      {/* Scenario body */}
                      <div className="px-5 py-4 space-y-4">
                        {sc.narrative ? (
                          <p className="text-sm leading-relaxed text-foreground/80">{sc.narrative}</p>
                        ) : (
                          <p className="text-sm text-muted-foreground italic">No narrative yet.</p>
                        )}

                        {/* Signal evidence */}
                        {(supporting.length > 0 || weakening.length > 0) && (
                          <div className="space-y-3">
                            {supporting.length > 0 && (
                              <div>
                                <p className="text-xs font-medium text-green-700 mb-1.5">Supporting signals ({supporting.length})</p>
                                <ul className="space-y-1">
                                  {supporting.slice(0, 3).map((l) => (
                                    <li key={l.signal_id} className="text-xs text-foreground/80 pl-3 border-l-2 border-green-300 leading-relaxed">
                                      {l.signal_title}
                                    </li>
                                  ))}
                                  {supporting.length > 3 && (
                                    <li className="text-xs text-muted-foreground pl-3">+{supporting.length - 3} more</li>
                                  )}
                                </ul>
                              </div>
                            )}
                            {weakening.length > 0 && (
                              <div>
                                <p className="text-xs font-medium text-red-600 mb-1.5">Contradicting signals ({weakening.length})</p>
                                <ul className="space-y-1">
                                  {weakening.slice(0, 2).map((l) => (
                                    <li key={l.signal_id} className="text-xs text-foreground/80 pl-3 border-l-2 border-red-300 leading-relaxed">
                                      {l.signal_title}
                                    </li>
                                  ))}
                                  {weakening.length > 2 && (
                                    <li className="text-xs text-muted-foreground pl-3">+{weakening.length - 2} more</li>
                                  )}
                                </ul>
                              </div>
                            )}
                          </div>
                        )}

                        {/* No confirmed links but there are suggested ones */}
                        {confirmed.length === 0 && suggested.length > 0 && (
                          <p className="text-xs text-muted-foreground italic">
                            {suggested.length} signal{suggested.length !== 1 ? "s" : ""} suggested — not yet confirmed.
                          </p>
                        )}

                        {/* Evidence share — real or simulated */}
                        {(() => {
                          const simVal = simScores?.[sc.id];
                          const supportVal = simVal ? simVal.support : sc.support_score;
                          const mass       = simVal ? simTotalMass   : totalSupportMass;
                          const share      = supportVal / mass;
                          return (
                            <div className="flex items-center gap-3">
                              <span className="text-xs text-muted-foreground w-32 shrink-0">
                                Evidence share{simVal ? " (sim)" : ""}
                              </span>
                              <Bar value={supportVal} max={mass} color={simVal ? "bg-blue-500" : "bg-primary"} />
                              <span className="text-xs font-mono text-muted-foreground w-10 text-right">{pct(share)}</span>
                            </div>
                          );
                        })()}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Scenario quadrant matrix */}
              {scenarios.length > 0 && axis1 && axis2 && (
                <div className="mt-8">
                  <ScenarioQuadrantChart
                    scenarios={scenarios}
                    drafts={drafts}
                    axis1={axis1}
                    axis2={axis2}
                    supportValues={
                      simScores
                        ? Object.fromEntries(Object.entries(simScores).map(([id, v]) => [id, v.support]))
                        : undefined
                    }
                    totalMass={simScores ? simTotalMass : totalSupportMass}
                  />
                </div>
              )}
            </>
          )}

          {/* ── Draft fallback — shown when no live scenarios exist ──────── */}
          {scenarios.length === 0 && visibleDrafts.length > 0 && (
            <>
              <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-2.5 text-xs text-amber-800">
                Showing scenario drafts — approve them in the Scenario Pipeline to promote to live scenarios.
              </div>
              <div className={`grid gap-5 ${visibleDrafts.length === 4 ? "grid-cols-1 md:grid-cols-2" : "grid-cols-1"}`}>
                {visibleDrafts.map((d) => (
                  <div key={d.id} className="border border-dashed rounded-xl overflow-hidden">
                    <div className="bg-muted/30 px-5 py-4 flex items-start justify-between gap-3">
                      <h3 className="text-base font-bold leading-tight">{d.name}</h3>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${
                        d.status === "approved" ? "bg-green-100 text-green-700" :
                        "bg-amber-100 text-amber-700"
                      }`}>
                        {d.status === "approved" ? "Approved draft" : "Pending approval"}
                      </span>
                    </div>
                    <div className="px-5 py-4 space-y-3">
                      {d.narrative && <p className="text-sm leading-relaxed text-foreground/80">{d.narrative}</p>}
                      {d.key_characteristics.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground mb-1.5">Key characteristics</p>
                          <ul className="space-y-1">
                            {d.key_characteristics.slice(0, 4).map((c, i) => (
                              <li key={i} className="text-xs text-foreground/80 pl-3 border-l-2 border-primary/30 leading-relaxed">{c}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {(d.opportunities.length > 0 || d.threats.length > 0) && (
                        <div className="grid grid-cols-2 gap-3 pt-1">
                          {d.opportunities.length > 0 && (
                            <div>
                              <p className="text-xs font-medium text-green-700 mb-1">Opportunities</p>
                              <ul className="space-y-0.5">
                                {d.opportunities.slice(0, 2).map((o, i) => (
                                  <li key={i} className="text-xs text-muted-foreground leading-relaxed">{o}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {d.threats.length > 0 && (
                            <div>
                              <p className="text-xs font-medium text-red-600 mb-1">Threats</p>
                              <ul className="space-y-0.5">
                                {d.threats.slice(0, 2).map((t, i) => (
                                  <li key={i} className="text-xs text-muted-foreground leading-relaxed">{t}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}
                      {d.axis1_pole && d.axis2_pole && (
                        <p className="text-xs text-muted-foreground pt-1">
                          Quadrant: <strong className="text-foreground">{d.axis1_pole}</strong> × <strong className="text-foreground">{d.axis2_pole}</strong>
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </Section>
      )}

      {/* ── 07  What to Watch ────────────────────────────────────────── */}
      {(scenarios.length > 0 || visibleDrafts.length > 0) && (
        <Section n={7} title="What to Watch" lead="Scenarios are only useful if you can detect which one is emerging. Each scenario has a set of early indicators — specific signals whose appearance or absence would tell you which future is beginning to materialise.">
          {scenarios.length > 0 ? (
            <div className="space-y-3">
              {scenarios.map((sc) => {
                const links = signalLinks[sc.id] ?? [];
                const confirmed = links.filter((l) => l.user_confirmed);
                return (
                  <div key={sc.id} className="flex items-start gap-4 border rounded-lg p-4">
                    <AlertTriangle className={`h-4 w-4 shrink-0 mt-0.5 ${
                      sc.recent_delta > 0.05 ? "text-green-500" :
                      sc.recent_delta < -0.05 ? "text-red-400" : "text-muted-foreground"
                    }`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium">{sc.name}</p>
                      <p className="text-xs text-muted-foreground mb-2">
                        {sc.recent_delta > 0.05 ? "New signals are reinforcing this scenario" :
                         sc.recent_delta < -0.05 ? "Recent signals are weakening this scenario" :
                         "Signal flow is neutral — no strong movement yet"}
                      </p>
                      {confirmed.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {confirmed.slice(0, 4).map((l) => (
                            <span key={l.signal_id} className={`text-xs px-2 py-0.5 rounded-full border ${
                              l.relationship_type === "supports" ? "border-green-300 text-green-700 bg-green-50" :
                              l.relationship_type === "weakens" ? "border-red-300 text-red-700 bg-red-50" :
                              "border-muted text-muted-foreground"
                            }`}>
                              {(l.signal_title ?? "Signal").slice(0, 40)}{(l.signal_title ?? "").length > 40 ? "…" : ""}
                            </span>
                          ))}
                          {confirmed.length > 4 && (
                            <span className="text-xs text-muted-foreground px-1">+{confirmed.length - 4} more</span>
                          )}
                        </div>
                      )}
                    </div>
                    {(() => {
                      const simVal = simScores?.[sc.id];
                      const supportVal = simVal ? simVal.support : sc.support_score;
                      const mass       = simVal ? simTotalMass   : totalSupportMass;
                      return (
                        <div className="flex items-center gap-2 shrink-0">
                          <Bar value={supportVal} max={mass} color={simVal ? "bg-blue-500" : "bg-primary"} />
                          <span className="text-xs font-mono text-muted-foreground w-10">{pct(supportVal / mass)}</span>
                        </div>
                      );
                    })()}
                  </div>
                );
              })}
            </div>
          ) : (
            /* Draft-based early indicators */
            <div className="space-y-4">
              {visibleDrafts.filter((d) => d.early_indicators.length > 0).map((d) => (
                <div key={d.id} className="border rounded-lg p-4">
                  <p className="text-sm font-medium mb-2">{d.name}</p>
                  <ul className="space-y-1.5">
                    {d.early_indicators.map((ind, i) => (
                      <li key={i} className="flex items-start gap-2 text-xs text-foreground/80">
                        <span className="text-muted-foreground mt-0.5 shrink-0">→</span>
                        {ind}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              {visibleDrafts.every((d) => d.early_indicators.length === 0) && (
                <p className="text-sm text-muted-foreground italic">No early indicators defined in drafts.</p>
              )}
            </div>
          )}
        </Section>
      )}

      {/* ── Footer ────────────────────────────────────────────────────── */}
      <footer className="border-t pt-8 text-xs text-muted-foreground space-y-2">
        <p className="font-medium text-foreground">Methodology</p>
        <p className="leading-relaxed">
          This report was produced using a structured horizon-scanning and scenario-planning pipeline.
          Signals were automatically detected from open web sources, classified using the STEEP framework
          (Social, Technological, Economic, Environmental, Political), and scored for relevance,
          novelty, and impact. Signals were clustered into trends using semantic similarity and temporal
          co-occurrence. Drivers of change were extracted from trends and scored for impact and uncertainty.
          The two highest-scoring uncertain drivers were selected as scenario axes, and four internally
          consistent scenarios were generated and refined through a structured review process.
          Scenario momentum scores reflect the cumulative balance of incoming signals.
        </p>
        <p className="pt-2">
          Generated on {generatedOn} · Theme: {theme.name}
          {theme.time_horizon && ` · Horizon: ${theme.time_horizon}`}
        </p>
      </footer>
    </div>
  );
}
