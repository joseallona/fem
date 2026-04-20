"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { BookOpen, CheckCircle2, Circle, FileText, GitBranch, Loader2, Rss, ScrollText, Target, X, Zap } from "lucide-react";
import { api, type Theme, type Signal, type Scenario, type Run, type PipelineStatus } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// ── Autopilot helpers (shared with pipeline page) ─────────────────────────

type AutopilotPhase = "idle" | "crawl" | "axes" | "confirm" | "generate" | "approve" | "done" | "error";

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

// ── Page ────────────────────────────────────────────────────────────────────

export default function ThemeDashboard() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [theme, setTheme] = useState<Theme | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [activating, setActivating] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resettingScenarios, setResettingScenarios] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Autopilot
  const [autopilotOpen, setAutopilotOpen] = useState(false);
  const [autopilotPhase, setAutopilotPhase] = useState<AutopilotPhase>("idle");
  const [autopilotError, setAutopilotError] = useState<string | null>(null);
  const autopilotAbort = useRef(false);

  const activeRun = runs.find((r) => r.status === "running");

  function loadData() {
    setLoadError(false);
    Promise.all([
      api.themes.get(id),
      api.signals.list(id, { limit: "5" }),
      api.scenarios.list(id),
      api.runs.list(id),
      api.scenarioPipeline.status(id).catch(() => null),
    ]).then(([t, s, sc, r, ps]) => {
      setTheme(t); setSignals(s); setScenarios(sc); setRuns(r);
      setPipelineStatus(ps);
    }).catch(() => setLoadError(true));
  }

  useEffect(() => { loadData(); }, [id]);

  // Poll every 5s while a run is active
  useEffect(() => {
    if (activeRun) {
      pollRef.current = setInterval(async () => {
        try {
          const fresh = await api.runs.list(id);
          setRuns(fresh);
          if (!fresh.find((r) => r.status === "running")) {
            const [s, sc] = await Promise.all([
              api.signals.list(id, { limit: "5" }),
              api.scenarios.list(id),
            ]);
            setSignals(s);
            setScenarios(sc);
          }
        } catch {
          // Polling errors are silent — don't interrupt the user
        }
      }, 5000);
    } else {
      if (pollRef.current) clearInterval(pollRef.current);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [!!activeRun, id]);

  async function activate() {
    setActivating(true);
    try {
      const updated = await api.themes.activate(id);
      setTheme(updated);
    } finally {
      setActivating(false);
    }
  }

  function friendlyError(e: unknown): string {
    const msg = e instanceof Error ? e.message : String(e);
    if (msg.toLowerCase().includes("failed to fetch") || msg.toLowerCase().includes("networkerror")) {
      return "Request failed — this is usually a CORS issue or the backend is unreachable. Check the browser console for details.";
    }
    // Only map the trigger-specific conflict message, not every 409.
    if (msg.toLowerCase().includes("already active")) {
      return "A run is already in progress for this theme.";
    }
    // Extract the FastAPI detail string if present, otherwise show raw message.
    try {
      const parsed = JSON.parse(msg);
      if (parsed?.detail) return String(parsed.detail);
    } catch { /* not JSON */ }
    return msg;
  }

  async function cancelRun() {
    if (!activeRun) return;
    setCancelling(true);
    // Stop the poll immediately so a stale in-flight response can't restore
    // "running" status after we update local state.
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    try {
      await api.runs.cancel(activeRun.id);
      // Re-fetch from the server so local state reflects the real DB status.
      const fresh = await api.runs.list(id);
      setRuns(fresh);
    } catch (e: unknown) {
      setRunError(friendlyError(e));
    } finally {
      setCancelling(false);
    }
  }

  async function resetTheme() {
    if (!window.confirm("Reset this theme? All signals, trends, drivers, scenarios, and briefs will be permanently deleted. Sources will be kept.")) return;
    setResetting(true);
    setRunError(null);
    try {
      await api.themes.reset(id);
      loadData();
    } catch (e: unknown) {
      setRunError(friendlyError(e));
    } finally {
      setResetting(false);
    }
  }

  async function resetScenarios() {
    if (!window.confirm("Reset scenarios? Axes, scenario drafts, approved scenarios, and briefs will be deleted. Signals, trends, and drivers are kept. A new run will start automatically.")) return;
    setResettingScenarios(true);
    setRunError(null);
    try {
      await api.themes.resetScenarios(id);
      const run = await api.runs.trigger(id);
      setRuns((prev) => [run, ...prev]);
      loadData();
    } catch (e: unknown) {
      setRunError(friendlyError(e));
    } finally {
      setResettingScenarios(false);
    }
  }

  async function runAutopilot() {
    autopilotAbort.current = false;
    setAutopilotOpen(true);
    setAutopilotError(null);
    setAutopilotPhase("crawl");
    try {
      let s = await api.scenarioPipeline.status(id);
      if (s.state === "no_data") {
        try { await api.runs.trigger(id); } catch { /* already running is fine */ }
        while (!autopilotAbort.current && s.state === "no_data") {
          await sleep(5000);
          s = await api.scenarioPipeline.status(id);
        }
      }
      setAutopilotPhase("axes");
      while (!autopilotAbort.current && s.state === "trends_ready") {
        await sleep(4000);
        s = await api.scenarioPipeline.status(id);
      }
      if (s.state === "axes_pending") {
        setAutopilotPhase("confirm");
        await api.scenarioPipeline.confirmAxes(id);
        s = await api.scenarioPipeline.status(id);
      }
      if (s.state === "axes_confirmed") {
        setAutopilotPhase("generate");
        while (!autopilotAbort.current && s.state === "axes_confirmed") {
          await sleep(4000);
          s = await api.scenarioPipeline.status(id);
        }
      }
      if (s.state === "scenarios_pending") {
        setAutopilotPhase("approve");
        await api.scenarioPipeline.approveAll(id);
      }
      setAutopilotPhase("done");
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

  async function triggerRun() {
    setRunError(null);
    setTriggering(true);
    try {
      const run = await api.runs.trigger(id);
      setRuns((prev) => [run, ...prev]);
    } catch (e: unknown) {
      setRunError(friendlyError(e));
    } finally {
      setTriggering(false);
    }
  }

  if (loadError) return (
    <div className="p-8 flex flex-col gap-3 text-sm">
      <p className="text-destructive font-medium">Could not load dashboard — backend may still be starting up.</p>
      <button onClick={loadData} className="w-fit px-3 py-1.5 rounded border text-sm hover:bg-muted transition-colors">Retry</button>
    </div>
  );

  if (!theme) return <div className="p-8 text-muted-foreground">Loading...</div>;

  const lastRun = runs[0];
  const momentumIcon = { increasing: "↑", stable: "→", decreasing: "↓" } as Record<string, string>;

  function estimatedEnd(run: typeof activeRun): string | null {
    if (!run?.estimated_duration_seconds) return null;
    const started = new Date(run.started_at).getTime();
    const eta = new Date(started + run.estimated_duration_seconds * 1000);
    const now = Date.now();
    const secsLeft = Math.max(0, Math.round((eta.getTime() - now) / 1000));
    if (secsLeft === 0) return "any moment now";
    if (secsLeft < 60) return `~${secsLeft}s`;
    return `~${Math.ceil(secsLeft / 60)}m`;
  }

  return (
    <div className="max-w-5xl mx-auto p-8">
      <div className="mb-2">
        <Link href="/themes" className="text-sm text-muted-foreground hover:underline">← Themes</Link>
      </div>

      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{theme.name}</h1>
            <Badge variant={theme.status === "active" ? "default" : "secondary"}>{theme.status}</Badge>
          </div>
          {theme.focal_question && (
            <p className="text-muted-foreground text-sm mt-2 max-w-2xl">{theme.focal_question}</p>
          )}
          {theme.time_horizon && (
            <p className="text-xs text-muted-foreground mt-1">Time horizon: {theme.time_horizon}</p>
          )}
        </div>
        <div className="flex gap-2">
          {pipelineStatus?.state !== "monitoring" && !autopilotOpen && (
            <Button onClick={runAutopilot} className="gap-2">
              <Zap className="h-4 w-4" />
              Run Autopilot
            </Button>
          )}
          {pipelineStatus?.state === "monitoring" && (
            <Link href={`/themes/${id}/report`}>
              <Button variant="secondary" className="gap-2">
                <ScrollText className="h-4 w-4" />
                View Report
              </Button>
            </Link>
          )}
          <Button
            onClick={resetScenarios}
            disabled={resettingScenarios || !!activeRun}
            variant="outline"
            className="text-destructive border-destructive/40 hover:bg-destructive/5"
          >
            {resettingScenarios ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {resettingScenarios ? "Resetting..." : "Reset Scenarios"}
          </Button>
          <Button
            onClick={resetTheme}
            disabled={resetting || !!activeRun}
            variant="outline"
            className="text-destructive border-destructive/40 hover:bg-destructive/5"
          >
            {resetting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {resetting ? "Resetting..." : "Reset Theme"}
          </Button>
          {theme.status !== "active" && (
            <Button onClick={activate} disabled={activating} variant="secondary">
              {activating ? "Activating..." : "Activate Monitoring"}
            </Button>
          )}
          {activeRun ? (
            <Button onClick={cancelRun} disabled={cancelling} variant="outline" className="text-destructive border-destructive/40 hover:bg-destructive/5">
              {cancelling ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {cancelling ? "Stopping..." : "Stop Run"}
            </Button>
          ) : (
            <Button
              onClick={triggerRun}
              disabled={triggering || theme.status !== "active"}
              variant="outline"
            >
              {triggering ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rss className="h-4 w-4" />}
              {triggering ? "Triggering..." : "Run Now"}
            </Button>
          )}
        </div>
      </div>

      {/* Nav tabs */}
      <div className="flex gap-1 mb-8 border-b">
        {[
          { label: "Dashboard", href: `/themes/${id}`, icon: BookOpen },
          { label: "Sources", href: `/themes/${id}/sources`, icon: Rss },
          { label: "Signals", href: `/themes/${id}/signals`, icon: Zap },
          { label: "Scenarios", href: `/themes/${id}/scenarios`, icon: Target },
          { label: "Scenario Pipeline", href: `/themes/${id}/scenario-pipeline`, icon: GitBranch },
          { label: "Briefs", href: `/themes/${id}/briefs`, icon: FileText },
        ].map(({ label, href, icon: Icon }) => (
          <Link key={href} href={href} className="flex items-center gap-1.5 px-4 py-2 text-sm text-muted-foreground hover:text-foreground border-b-2 border-transparent hover:border-primary transition-colors">
            <Icon className="h-3.5 w-3.5" />{label}
          </Link>
        ))}
      </div>

      {activeRun && (
        <div className="flex items-center justify-between gap-4 mb-4 px-3 py-2 rounded-md bg-blue-50 border border-blue-200 text-blue-800 text-sm">
          <div className="flex items-center gap-2 min-w-0">
            <Loader2 className="h-4 w-4 animate-spin shrink-0" />
            <span className="min-w-0">
              {activeRun.current_stage
                ? <span className="font-medium">{activeRun.current_stage}</span>
                : <span>Pipeline run in progress — started {new Date(activeRun.started_at).toLocaleTimeString()}.</span>
              }
              {estimatedEnd(activeRun) && (
                <span className="ml-2 text-blue-600 opacity-75">ETA {estimatedEnd(activeRun)}</span>
              )}
            </span>
          </div>
          <button
            onClick={cancelRun}
            disabled={cancelling}
            className="shrink-0 flex items-center gap-1.5 px-2.5 py-1 rounded border border-blue-300 bg-white text-blue-700 hover:bg-blue-100 disabled:opacity-50 text-xs font-medium transition-colors"
          >
            {cancelling ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
            {cancelling ? "Stopping..." : "Stop Run"}
          </button>
        </div>
      )}
      {runError && (
        <div className="flex items-center justify-between mb-4 px-3 py-2 rounded-md bg-destructive/10 border border-destructive/30 text-destructive text-sm">
          <span>{runError}</span>
          <button onClick={() => setRunError(null)} className="ml-4 text-xs underline">Dismiss</button>
        </div>
      )}

      {autopilotOpen && (() => {
        const phaseIdx = AUTOPILOT_STEPS.findIndex((s) => s.id === autopilotPhase);
        return (
          <div className="mb-4 border rounded-lg bg-muted/20 p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                {autopilotPhase === "done" ? (
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                ) : autopilotPhase === "error" ? (
                  <X className="h-4 w-4 text-destructive" />
                ) : (
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                )}
                <span className="text-sm font-semibold">
                  {autopilotPhase === "done" ? "Pipeline complete — redirecting to report…" :
                   autopilotPhase === "error" ? "Autopilot stopped" :
                   "Autopilot running — gates approved automatically"}
                </span>
              </div>
              {autopilotPhase !== "done" && (
                <Button variant="ghost" size="sm" onClick={cancelAutopilot} className="gap-1 text-muted-foreground h-7 px-2">
                  <X className="h-3.5 w-3.5" /> Cancel
                </Button>
              )}
            </div>
            <div className="flex items-center gap-3">
              {AUTOPILOT_STEPS.map((step, i) => {
                const done = phaseIdx > i && autopilotPhase !== "error";
                const active = phaseIdx === i && autopilotPhase !== "error";
                return (
                  <div key={step.id} className="flex items-center gap-1.5 min-w-0">
                    <div className={`flex items-center justify-center w-5 h-5 rounded-full shrink-0 ${
                      done ? "bg-green-500 text-white" :
                      active ? "bg-primary text-primary-foreground" :
                      "bg-muted border text-muted-foreground"
                    }`}>
                      {done ? <CheckCircle2 className="h-3 w-3" /> :
                       active ? <Loader2 className="h-3 w-3 animate-spin" /> :
                       <Circle className="h-3 w-3" />}
                    </div>
                    <span className={`text-xs whitespace-nowrap ${active ? "font-medium" : "text-muted-foreground"}`}>
                      {step.label}
                    </span>
                    {i < AUTOPILOT_STEPS.length - 1 && (
                      <div className={`h-px w-4 shrink-0 ${done ? "bg-green-400" : "bg-muted-foreground/20"}`} />
                    )}
                  </div>
                );
              })}
            </div>
            {autopilotError && (
              <p className="mt-2 text-xs text-destructive">{autopilotError}</p>
            )}
          </div>
        );
      })()}

      {!autopilotOpen && pipelineStatus && (pipelineStatus.state === "axes_pending" || pipelineStatus.state === "scenarios_pending") && (
        <div className="mb-4 flex items-center gap-3 px-3 py-2.5 rounded-md bg-primary/5 border border-primary/30 text-sm">
          <GitBranch className="h-4 w-4 text-primary shrink-0" />
          <span className="text-primary font-medium">
            {pipelineStatus.state === "axes_pending" ? "Gate 1 ready — review proposed scenario axes" : "Gate 2 ready — review scenario drafts"}
          </span>
          <Link
            href={`/themes/${id}/scenario-pipeline${pipelineStatus.state === "axes_pending" ? "/gate1" : "/gate2"}`}
            className="ml-auto text-xs px-2.5 py-1 rounded border border-primary/40 text-primary hover:bg-primary/10 transition-colors"
          >
            Review →
          </Link>
        </div>
      )}

      <div className="grid grid-cols-3 gap-4 mb-8">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Signals</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-bold">{signals.length}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Scenarios</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-bold">{scenarios.length}</p></CardContent>
        </Card>
        <Card className={activeRun ? "border-blue-300" : ""}>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Last Run</CardTitle></CardHeader>
          <CardContent>
            <div className="flex items-center gap-1.5">
              {activeRun && <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-600" />}
              <p className={`text-sm font-medium ${
                activeRun ? "text-blue-700" :
                lastRun?.status === "cancelled" ? "text-orange-600" :
                lastRun?.status === "failed" ? "text-destructive" : ""
              }`}>
                {lastRun ? lastRun.status : "—"}
              </p>
            </div>
            {activeRun && estimatedEnd(activeRun) && (
              <p className="text-xs text-blue-600 mt-0.5">ETA {estimatedEnd(activeRun)}</p>
            )}
            {lastRun && <p className="text-xs text-muted-foreground">{new Date(lastRun.started_at).toLocaleDateString()}</p>}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div>
          <h2 className="text-sm font-semibold mb-3">Top Signals</h2>
          {signals.length === 0 ? (
            <p className="text-muted-foreground text-sm">No signals yet.</p>
          ) : (
            <div className="space-y-2">
              {signals.map((s) => (
                <Card key={s.id} className="p-3">
                  <div className="flex items-start justify-between gap-2">
                    {s.source_url ? (
                      <a href={s.source_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium line-clamp-2 hover:underline">{s.title}</a>
                    ) : (
                      <p className="text-sm font-medium line-clamp-2">{s.title}</p>
                    )}
                    {s.signal_type && <Badge variant="outline" className="text-xs shrink-0">{s.signal_type}</Badge>}
                  </div>
                  {s.steep_category && <p className="text-xs text-muted-foreground mt-1">{s.steep_category} · {s.horizon}</p>}
                </Card>
              ))}
            </div>
          )}
        </div>

        <div>
          <h2 className="text-sm font-semibold mb-3">Scenarios</h2>
          {scenarios.length === 0 ? (
            <p className="text-muted-foreground text-sm">No scenarios yet.</p>
          ) : (
            <div className="space-y-2">
              {scenarios.map((sc) => (
                <Card key={sc.id} className="p-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">{sc.name}</p>
                    <div className="flex gap-1.5">
                      <Badge variant="secondary" className="text-xs">{sc.confidence_level}</Badge>
                      <span className="text-sm" title={sc.momentum_state}>
                        {momentumIcon[sc.momentum_state] || "→"}
                      </span>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
