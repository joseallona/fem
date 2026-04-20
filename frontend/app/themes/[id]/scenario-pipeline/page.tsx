"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowRight, BookOpen, CheckCircle2, Circle, Clock, FileText, GitBranch, Loader2, Rss, ScrollText, Target, TrendingUp, X, Zap } from "lucide-react";
import { api, type PipelineStatus, type Trend, type Driver } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";

type State = PipelineStatus["state"];

const STATE_STEPS: { state: State; label: string; description: string }[] = [
  { state: "no_data",         label: "Signal Synthesis",   description: "Run the pipeline to detect signals and cluster them into trends" },
  { state: "trends_ready",    label: "Driver Extraction",  description: "Trends are synthesized; drivers of change are being scored" },
  { state: "axes_pending",    label: "Axis Review",        description: "Two critical uncertainty axes proposed — review and confirm (Gate 1)" },
  { state: "axes_confirmed",  label: "Generating Scenarios", description: "Axes confirmed; 4 scenario drafts are being generated" },
  { state: "scenarios_pending", label: "Scenario Review",  description: "Review 4 scenario drafts and approve them (Gate 2)" },
  { state: "monitoring",      label: "Active Monitoring",  description: "Scenarios live — signals are continuously monitored against each scenario" },
];

const STATE_ORDER: State[] = [
  "no_data", "trends_ready", "axes_pending", "axes_confirmed", "scenarios_pending", "monitoring",
];

function stepStatus(step: State, current: State): "done" | "active" | "pending" {
  const stepIdx = STATE_ORDER.indexOf(step);
  const currIdx = STATE_ORDER.indexOf(current);
  if (stepIdx < currIdx) return "done";
  if (stepIdx === currIdx) return "active";
  return "pending";
}

// ── Autopilot ────────────────────────────────────────────────────────────────

type AutopilotPhase =
  | "idle" | "crawl" | "axes" | "confirm" | "generate" | "approve" | "done" | "error";

const AUTOPILOT_STEPS: { id: AutopilotPhase; label: string }[] = [
  { id: "crawl",    label: "Collecting signals" },
  { id: "axes",     label: "Selecting scenario axes" },
  { id: "confirm",  label: "Confirming axes (Gate 1)" },
  { id: "generate", label: "Generating scenario drafts" },
  { id: "approve",  label: "Approving drafts (Gate 2)" },
  { id: "done",     label: "Report ready" },
];

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function ScenarioPipelinePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [trends, setTrends] = useState<Trend[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [loading, setLoading] = useState(true);

  // Autopilot state
  const [autopilotOpen, setAutopilotOpen] = useState(false);
  const [autopilotPhase, setAutopilotPhase] = useState<AutopilotPhase>("idle");
  const [autopilotError, setAutopilotError] = useState<string | null>(null);
  const autopilotAbort = useRef(false);

  async function load() {
    try {
      const [s, t, d] = await Promise.all([
        api.scenarioPipeline.status(id),
        api.scenarioPipeline.trends(id),
        api.scenarioPipeline.drivers(id),
      ]);
      setStatus(s);
      setTrends(t);
      setDrivers(d);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [id]);

  // Poll while generating (axes_confirmed state = background job running)
  useEffect(() => {
    if (status?.state !== "axes_confirmed") return;
    const interval = setInterval(async () => {
      const s = await api.scenarioPipeline.status(id);
      setStatus(s);
      if (s.state !== "axes_confirmed") clearInterval(interval);
    }, 4000);
    return () => clearInterval(interval);
  }, [status?.state, id]);

  async function runAutopilot() {
    autopilotAbort.current = false;
    setAutopilotOpen(true);
    setAutopilotError(null);
    setAutopilotPhase("crawl");

    try {
      let s = await api.scenarioPipeline.status(id);

      // Step 1 — trigger crawl if no data yet
      if (s.state === "no_data") {
        try { await api.runs.trigger(id); } catch { /* already running is fine */ }
        while (!autopilotAbort.current && s.state === "no_data") {
          await sleep(5000);
          s = await api.scenarioPipeline.status(id);
        }
      }

      // Step 2 — wait for axis proposal (trends_ready → axes_pending)
      setAutopilotPhase("axes");
      while (!autopilotAbort.current && s.state === "trends_ready") {
        await sleep(4000);
        s = await api.scenarioPipeline.status(id);
      }

      // Step 3 — auto-confirm axes (Gate 1)
      if (s.state === "axes_pending") {
        setAutopilotPhase("confirm");
        await api.scenarioPipeline.confirmAxes(id);
        s = await api.scenarioPipeline.status(id);
      }

      // Step 4 — wait for scenario generation
      if (s.state === "axes_confirmed") {
        setAutopilotPhase("generate");
        while (!autopilotAbort.current && s.state === "axes_confirmed") {
          await sleep(4000);
          s = await api.scenarioPipeline.status(id);
        }
      }

      // Step 5 — auto-approve all drafts (Gate 2)
      if (s.state === "scenarios_pending") {
        setAutopilotPhase("approve");
        await api.scenarioPipeline.approveAll(id);
      }

      // Done — navigate to report
      setAutopilotPhase("done");
      setStatus(await api.scenarioPipeline.status(id));
      await sleep(1200);
      router.push(`/themes/${id}/report`);
    } catch (e: unknown) {
      setAutopilotError(e instanceof Error ? e.message : String(e));
      setAutopilotPhase("error");
    }
  }

  function cancelAutopilot() {
    autopilotAbort.current = true;
    setAutopilotOpen(false);
    setAutopilotPhase("idle");
    setAutopilotError(null);
  }

  if (loading) return <div className="p-8 text-muted-foreground">Loading…</div>;
  if (!status) return <div className="p-8 text-muted-foreground">Could not load pipeline status.</div>;

  const autopilotPhaseIdx = AUTOPILOT_STEPS.findIndex((s) => s.id === autopilotPhase);

  return (
    <TooltipProvider>
    <div className="max-w-5xl mx-auto p-8">
      <div className="mb-2">
        <Link href="/themes" className="text-sm text-muted-foreground hover:underline">← Themes</Link>
      </div>

      <div className="flex gap-1 mb-8 border-b">
        {[
          { label: "Dashboard",         href: `/themes/${id}`,                    icon: BookOpen },
          { label: "Sources",           href: `/themes/${id}/sources`,            icon: Rss },
          { label: "Signals",           href: `/themes/${id}/signals`,            icon: Zap },
          { label: "Scenarios",         href: `/themes/${id}/scenarios`,          icon: Target },
          { label: "Scenario Pipeline", href: `/themes/${id}/scenario-pipeline`,  icon: GitBranch },
          { label: "Briefs",            href: `/themes/${id}/briefs`,             icon: FileText },
          { label: "Report",            href: `/themes/${id}/report`,             icon: ScrollText },
        ].map(({ label, href, icon: Icon }) => (
          <Link key={href} href={href} className={`flex items-center gap-1.5 px-4 py-2 text-sm border-b-2 transition-colors ${href === `/themes/${id}/scenario-pipeline` ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground hover:border-primary"}`}>
            <Icon className="h-3.5 w-3.5" />{label}
          </Link>
        ))}
      </div>

      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">Scenario Generation Pipeline</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Automates trend synthesis → driver extraction → axis selection → scenario generation → monitoring
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant={status.state === "monitoring" ? "default" : "secondary"} className="text-sm px-3 py-1">
            {status.state.replace(/_/g, " ")}
          </Badge>
          {status.state !== "monitoring" && !autopilotOpen && (
            <Button onClick={runAutopilot} className="gap-2">
              <Zap className="h-4 w-4" />
              Run Autopilot
            </Button>
          )}
          {status.state === "monitoring" && (
            <Link href={`/themes/${id}/report`}>
              <Button className="gap-2">
                <ScrollText className="h-4 w-4" />
                View Report
              </Button>
            </Link>
          )}
        </div>
      </div>

      {/* Autopilot panel */}
      {autopilotOpen && (
        <div className="mb-8 border rounded-lg bg-muted/20 p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              {autopilotPhase === "done" ? (
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              ) : autopilotPhase === "error" ? (
                <X className="h-5 w-5 text-destructive" />
              ) : (
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
              )}
              <span className="font-semibold text-sm">
                {autopilotPhase === "done" ? "Pipeline complete — redirecting to report…" :
                 autopilotPhase === "error" ? "Autopilot stopped" :
                 "Autopilot running — all gates will be approved automatically"}
              </span>
            </div>
            {autopilotPhase !== "done" && (
              <Button variant="ghost" size="sm" onClick={cancelAutopilot} className="gap-1 text-muted-foreground">
                <X className="h-3.5 w-3.5" /> Cancel
              </Button>
            )}
          </div>

          <div className="space-y-2">
            {AUTOPILOT_STEPS.map((step, i) => {
              const done = autopilotPhaseIdx > i && autopilotPhase !== "error";
              const active = autopilotPhaseIdx === i;
              return (
                <div key={step.id} className="flex items-center gap-3">
                  <div className={`flex items-center justify-center w-6 h-6 rounded-full shrink-0 ${
                    done ? "bg-green-500 text-white" :
                    active ? "bg-primary text-primary-foreground" :
                    "bg-muted border text-muted-foreground"
                  }`}>
                    {done ? <CheckCircle2 className="h-3.5 w-3.5" /> :
                     active && autopilotPhase !== "error" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> :
                     <Circle className="h-3.5 w-3.5" />}
                  </div>
                  <span className={`text-sm ${active ? "font-medium" : done ? "text-muted-foreground line-through" : "text-muted-foreground"}`}>
                    {step.label}
                  </span>
                </div>
              );
            })}
          </div>

          {autopilotError && (
            <p className="mt-4 text-sm text-destructive">{autopilotError}</p>
          )}
        </div>
      )}

      {/* Pipeline progress stepper */}
      <div className="mb-10">
        <div className="flex items-start gap-0">
          {STATE_STEPS.map((step, idx) => {
            const st = stepStatus(step.state, status.state);
            const isLast = idx === STATE_STEPS.length - 1;
            return (
              <div key={step.state} className="flex-1 flex items-start">
                <div className="flex flex-col items-center w-full">
                  <div className="flex items-center w-full">
                    <div className={`flex items-center justify-center w-8 h-8 rounded-full border-2 shrink-0 ${
                      st === "done" ? "bg-green-500 border-green-500 text-white" :
                      st === "active" ? "bg-primary border-primary text-primary-foreground" :
                      "bg-background border-muted-foreground/30 text-muted-foreground"
                    }`}>
                      {st === "done" ? <CheckCircle2 className="h-4 w-4" /> :
                       st === "active" && status.state === "axes_confirmed" ? <Loader2 className="h-4 w-4 animate-spin" /> :
                       <Circle className="h-4 w-4" />}
                    </div>
                    {!isLast && (
                      <div className={`h-0.5 flex-1 ${st === "done" ? "bg-green-400" : "bg-muted"}`} />
                    )}
                  </div>
                  <div className="mt-2 pr-2">
                    <p className={`text-xs font-medium ${st === "pending" ? "text-muted-foreground" : ""}`}>
                      {step.label}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Current state description + CTA */}
      {status.state === "no_data" && (
        <Card className="mb-8 border-dashed">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 mb-3">
              <Clock className="h-5 w-5 text-muted-foreground" />
              <p className="font-medium">Waiting for signal data</p>
            </div>
            <p className="text-sm text-muted-foreground mb-4">
              The scenario pipeline starts automatically after a pipeline run detects and clusters enough signals.
              Trigger a pipeline run from the Dashboard to get started.
            </p>
            <Link href={`/themes/${id}`}>
              <Button variant="outline" size="sm">Go to Dashboard</Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {status.state === "axes_pending" && (
        <Card className="mb-8 border-primary/40 bg-primary/5">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 mb-3">
              <GitBranch className="h-5 w-5 text-primary" />
              <p className="font-medium text-primary">Gate 1 Ready — Review Scenario Axes</p>
            </div>
            <p className="text-sm text-muted-foreground mb-4">
              Two critical uncertainty axes have been proposed based on the highest-scoring drivers.
              Review the axis poles, edit if needed, then confirm to trigger scenario generation.
            </p>
            <Link href={`/themes/${id}/scenario-pipeline/gate1`}>
              <Button size="sm" className="gap-2">
                Review Axes <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {status.state === "axes_confirmed" && (
        <Card className="mb-8 border-blue-300 bg-blue-50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 mb-3">
              <Loader2 className="h-5 w-5 text-blue-600 animate-spin" />
              <p className="font-medium text-blue-800">Generating 4 scenario drafts…</p>
            </div>
            <p className="text-sm text-blue-700">
              The LLM is generating scenario narratives for each quadrant of the axis matrix.
              This page will update automatically when drafts are ready.
            </p>
          </CardContent>
        </Card>
      )}

      {status.state === "scenarios_pending" && (
        <Card className="mb-8 border-primary/40 bg-primary/5">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 mb-3">
              <GitBranch className="h-5 w-5 text-primary" />
              <p className="font-medium text-primary">Gate 2 Ready — Review Scenario Drafts</p>
            </div>
            <p className="text-sm text-muted-foreground mb-4">
              {status.draft_count} scenario drafts are ready for review ({status.drafts_approved} already approved).
              Edit narratives, review early indicators, then approve each scenario to activate monitoring.
            </p>
            <Link href={`/themes/${id}/scenario-pipeline/gate2`}>
              <Button size="sm" className="gap-2">
                Review Scenarios <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {status.state === "monitoring" && (
        <Card className="mb-8 border-green-300 bg-green-50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 mb-3">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              <p className="font-medium text-green-800">Monitoring Active</p>
            </div>
            <p className="text-sm text-green-700 mb-4">
              {status.live_scenario_count} scenarios are live and being monitored.
              Each pipeline run updates the scenario probability scores based on new signals.
            </p>
            <div className="flex gap-2">
              <Link href={`/themes/${id}/scenarios`}>
                <Button variant="outline" size="sm">View Scenarios</Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {[
          { label: "Trends", value: status.trend_count, icon: TrendingUp },
          { label: "Drivers", value: status.driver_count, icon: Zap },
          { label: "Drafts", value: status.draft_count, icon: GitBranch },
          { label: "Live Scenarios", value: status.live_scenario_count, icon: CheckCircle2 },
        ].map(({ label, value, icon: Icon }) => (
          <Card key={label}>
            <CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground flex items-center gap-1.5"><Icon className="h-3.5 w-3.5" />{label}</CardTitle></CardHeader>
            <CardContent><p className="text-2xl font-bold">{value}</p></CardContent>
          </Card>
        ))}
      </div>

      {/* Trends list */}
      {trends.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-sm font-semibold">Synthesized Trends</h2>
            <Link href={`/themes/${id}/scenario-pipeline/matrix`} className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
              View trend × scenario matrix <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <p className="text-xs text-muted-foreground mb-3">
            Clusters of signals grouped by shared vocabulary and timing — the raw material for scenario axis selection.
          </p>
          <div className="space-y-3">
            {trends.map((t) => <TrendCard key={t.id} trend={t} />)}
          </div>
        </div>
      )}

      {/* Top drivers */}
      {drivers.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold mb-3">Drivers of Change</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-muted-foreground text-xs">
                  <th className="text-left pb-2 font-medium">Driver</th>
                  <th className="text-left pb-2 font-medium">Domain</th>
                  <th className="text-center pb-2 font-medium">Impact</th>
                  <th className="text-center pb-2 font-medium">Uncertainty</th>
                  <th className="text-center pb-2 font-medium">Type</th>
                </tr>
              </thead>
              <tbody>
                {drivers.map((d) => (
                  <tr key={d.id} className="border-b last:border-0">
                    <td className="py-2 pr-4">
                      <p className="font-medium">{d.name}</p>
                      {d.description && <p className="text-xs text-muted-foreground line-clamp-1">{d.description}</p>}
                    </td>
                    <td className="py-2 pr-4 text-xs text-muted-foreground">{d.steep_domain || "—"}</td>
                    <td className="py-2 text-center">
                      <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${d.impact_score >= 7 ? "bg-red-100 text-red-700" : d.impact_score >= 5 ? "bg-yellow-100 text-yellow-700" : "bg-muted text-muted-foreground"}`}>
                        {d.impact_score.toFixed(1)}
                      </span>
                    </td>
                    <td className="py-2 text-center">
                      <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${d.uncertainty_score >= 7 ? "bg-purple-100 text-purple-700" : d.uncertainty_score >= 5 ? "bg-blue-100 text-blue-700" : "bg-muted text-muted-foreground"}`}>
                        {d.uncertainty_score.toFixed(1)}
                      </span>
                    </td>
                    <td className="py-2 text-center">
                      <Badge variant={d.is_predetermined ? "secondary" : "outline"} className="text-xs">
                        {d.is_predetermined ? "predetermined" : "uncertainty"}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
    </TooltipProvider>
  );
}

// ── TrendCard ─────────────────────────────────────────────────────────────

const STEEP_STYLE: Record<string, string> = {
  social:         "bg-blue-50 text-blue-700 border border-blue-200",
  technological:  "bg-purple-50 text-purple-700 border border-purple-200",
  economic:       "bg-green-50 text-green-700 border border-green-200",
  environmental:  "bg-emerald-50 text-emerald-700 border border-emerald-200",
  political:      "bg-orange-50 text-orange-700 border border-orange-200",
};

const S_CURVE_STAGES = ["emergence", "early_growth", "growth", "maturity", "decline"] as const;
const S_CURVE_LABEL: Record<string, string> = {
  emergence:    "Emerging",
  early_growth: "Early Growth",
  growth:       "Growing",
  maturity:     "Mature",
  decline:      "Declining",
};
const S_CURVE_TIP: Record<string, string> = {
  emergence:    "Just appearing — very few signals, uncertain trajectory. Equivalent to a Horizon 3 seed.",
  early_growth: "Starting to gain traction. Signal count growing but not yet mainstream.",
  growth:       "Rapid acceleration — the trend is clearly real and spreading. Strongest H2 signal.",
  maturity:     "Dominant and widely understood. The H1 system — influential but may be near peak.",
  decline:      "Losing momentum. New trends are displacing it.",
};

function MomentumBar({ value }: { value: number }) {
  // value typically -1 to +1
  const clamped = Math.max(-1, Math.min(1, value));
  const pct = Math.abs(clamped) * 100;
  const label = clamped > 0.5 ? "strongly growing" : clamped > 0.15 ? "growing" : clamped < -0.5 ? "strongly declining" : clamped < -0.15 ? "declining" : "stable";
  const color = clamped > 0.15 ? "bg-green-500" : clamped < -0.15 ? "bg-red-400" : "bg-gray-400";
  const textColor = clamped > 0.15 ? "text-green-700" : clamped < -0.15 ? "text-red-600" : "text-muted-foreground";

  return (
    <Tooltip side="right" content={
      <div className="space-y-1">
        <p className="font-semibold">Momentum</p>
        <p className="text-muted-foreground">How fast signal volume supporting this trend is growing. Positive = accelerating, negative = fading.</p>
        <p>Value: <span className="font-mono">{value.toFixed(2)}</span> ({label})</p>
      </div>
    }>
      <div className="flex items-center gap-2 cursor-help">
        <span className="text-xs text-muted-foreground w-16 shrink-0">Momentum</span>
        <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
          <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%`, marginLeft: clamped < 0 ? `${100 - pct}%` : 0 }} />
        </div>
        <span className={`text-xs font-mono w-10 text-right ${textColor}`}>{clamped > 0 ? "+" : ""}{value.toFixed(2)}</span>
      </div>
    </Tooltip>
  );
}

function SCurveStrip({ position }: { position: string }) {
  const currentIdx = S_CURVE_STAGES.indexOf(position as typeof S_CURVE_STAGES[number]);
  return (
    <Tooltip content={
      <div className="space-y-1">
        <p className="font-semibold">S-Curve Position: {S_CURVE_LABEL[position] ?? position}</p>
        <p className="text-muted-foreground">{S_CURVE_TIP[position] ?? "Position in the innovation lifecycle."}</p>
        <p className="text-muted-foreground border-t pt-1 mt-1">S-curves model how trends grow slowly at first, then rapidly, then plateau or decline.</p>
      </div>
    }>
      <div className="flex items-center gap-0.5 cursor-help">
        {S_CURVE_STAGES.map((stage, i) => (
          <div
            key={stage}
            className={`h-2 rounded-sm transition-all ${
              i === currentIdx
                ? "w-5 bg-primary"
                : i < currentIdx
                ? "w-2 bg-primary/30"
                : "w-2 bg-muted"
            }`}
          />
        ))}
        <span className="ml-1.5 text-xs text-muted-foreground">{S_CURVE_LABEL[position] ?? position}</span>
      </div>
    </Tooltip>
  );
}

function AlignmentBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 70 ? "bg-green-500" : pct >= 40 ? "bg-yellow-400" : "bg-red-400";
  return (
    <Tooltip content={
      <div className="space-y-1">
        <p className="font-semibold">Ontology Alignment</p>
        <p className="text-muted-foreground">How well this trend aligns with the theme's focal question and key concepts. Higher = more relevant to your strategic question.</p>
        <p>Score: <span className="font-mono">{pct}%</span></p>
      </div>
    }>
      <div className="flex items-center gap-1.5 cursor-help">
        <span className="text-xs text-muted-foreground">Relevance</span>
        <div className="w-12 h-1.5 bg-muted rounded-full overflow-hidden">
          <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="text-xs font-mono text-muted-foreground">{pct}%</span>
      </div>
    </Tooltip>
  );
}

function HorizonBadge({ horizon }: { horizon?: string }) {
  if (!horizon) return null;
  const tip: Record<string, string> = {
    H1: "Present (0–2 yrs) — dominant, established systems. Observable now.",
    H2: "Transition (2–7 yrs) — emerging disruptions in the contested middle ground.",
    H3: "Future (7+ yrs) — seeds of future systems; marginal today, potentially dominant tomorrow.",
  };
  return (
    <Tooltip content={
      <div className="space-y-1">
        <p className="font-semibold">Three Horizons: {horizon}</p>
        <p className="text-muted-foreground">{tip[horizon] ?? horizon}</p>
      </div>
    }>
      <Badge variant="outline" className="text-xs cursor-help">{horizon}</Badge>
    </Tooltip>
  );
}

function TrendCard({ trend: t }: { trend: Trend }) {
  return (
    <Card className="p-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-start gap-2 min-w-0">
          <TrendingUp className="h-4 w-4 text-primary shrink-0 mt-0.5" />
          <p className="text-sm font-semibold leading-snug">{t.name}</p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <HorizonBadge horizon={t.horizon} />
        </div>
      </div>

      {/* Description — full, not clamped */}
      {t.description && (
        <p className="text-xs text-muted-foreground mb-3 leading-relaxed pl-6">{t.description}</p>
      )}

      {/* S-curve */}
      <div className="pl-6 mb-2">
        <SCurveStrip position={t.s_curve_position} />
      </div>

      {/* Momentum */}
      <div className="pl-6 mb-3">
        <MomentumBar value={t.momentum} />
      </div>

      {/* Footer row */}
      <div className="flex items-center gap-2 flex-wrap pl-6">
        {t.steep_domains.map((d) => (
          <span key={d} className={`text-xs px-1.5 py-0.5 rounded ${STEEP_STYLE[d] ?? "bg-muted text-muted-foreground"}`}>{d}</span>
        ))}
        <span className="ml-auto flex items-center gap-3">
          <AlignmentBar value={t.ontology_alignment} />
          <span className="text-xs text-muted-foreground">{t.signal_count} signals</span>
        </span>
      </div>
    </Card>
  );
}
