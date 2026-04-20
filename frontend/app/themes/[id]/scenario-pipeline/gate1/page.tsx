"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { CheckCircle2, Edit2, Loader2, Lock, LockOpen, RefreshCw, X } from "lucide-react";
import { api, type ScenarioAxis, type Driver } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function Gate1Page() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [axes, setAxes] = useState<ScenarioAxis[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [editingAxis, setEditingAxis] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);
  const [rebuildMessage, setRebuildMessage] = useState<string | null>(null);

  async function load() {
    try {
      const [ax, dr] = await Promise.all([
        api.scenarioPipeline.axes(id),
        api.scenarioPipeline.drivers(id),
      ]);
      setAxes(ax);
      setDrivers(dr);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [id]);

  function startEdit(axis: ScenarioAxis) {
    setEditingAxis(axis.id);
    setEditDraft({
      driver_name: axis.driver_name || "",
      pole_low: axis.pole_low || "",
      pole_high: axis.pole_high || "",
      rationale: axis.rationale || "",
    });
  }

  async function saveEdit(axisId: string) {
    setSaving(true);
    try {
      const updated = await api.scenarioPipeline.updateAxis(axisId, editDraft);
      setAxes((prev) => prev.map((a) => (a.id === axisId ? updated : a)));
      setEditingAxis(null);
    } finally {
      setSaving(false);
    }
  }

  async function confirmAxes() {
    setConfirmError(null);
    setConfirming(true);
    try {
      await api.scenarioPipeline.confirmAxes(id);
      router.push(`/themes/${id}/scenario-pipeline`);
    } catch (e: unknown) {
      setConfirmError(e instanceof Error ? e.message : String(e));
    } finally {
      setConfirming(false);
    }
  }

  async function toggleLock(axis: ScenarioAxis) {
    const updated = await api.scenarioPipeline.updateAxis(axis.id, { axis_locked: !axis.axis_locked });
    setAxes((prev) => prev.map((a) => (a.id === axis.id ? updated : a)));
  }

  async function rebuildMatrix() {
    setRebuilding(true);
    setRebuildMessage(null);
    try {
      await api.scenarioPipeline.rebuildAxes(id);
      setRebuildMessage("Rebuild started — new axes will appear shortly.");
      setTimeout(() => load(), 4000);
    } catch (e: unknown) {
      setRebuildMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setRebuilding(false);
    }
  }

  if (loading) return <div className="p-8 text-muted-foreground">Loading…</div>;

  const allUnconfirmed = axes.every((a) => !a.user_confirmed);
  const driverMap = Object.fromEntries(drivers.map((d) => [d.id, d]));

  return (
    <div className="max-w-4xl mx-auto p-8">
      <div className="mb-2">
        <Link href={`/themes/${id}/scenario-pipeline`} className="text-sm text-muted-foreground hover:underline">
          ← Scenario Pipeline
        </Link>
      </div>

      <div className="mb-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">Gate 1 — Axis Review</h1>
              <Badge variant="secondary">Review Required</Badge>
            </div>
            <p className="text-sm text-muted-foreground mt-2 max-w-2xl">
              The pipeline has identified two critical uncertainties as scenario axes. Review the proposed
              poles for each axis, edit if needed, then confirm to generate the 4 scenario drafts.
            </p>
          </div>
          <div className="flex flex-col items-end gap-2 shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={rebuildMatrix}
              disabled={rebuilding}
              className="gap-2"
            >
              {rebuilding ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              Rebuild Matrix
            </Button>
            {rebuildMessage && (
              <p className="text-xs text-muted-foreground text-right max-w-48">{rebuildMessage}</p>
            )}
          </div>
        </div>
      </div>

      {axes.length === 0 && (
        <Card className="border-dashed">
          <CardContent className="pt-6 text-center text-muted-foreground text-sm">
            No axes proposed yet. Run the pipeline first to detect trends and drivers.
          </CardContent>
        </Card>
      )}

      {/* Quadrant preview */}
      {axes.length >= 2 && (
        <div className="mb-8">
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
            Quadrant Preview — 4 Scenarios
          </h2>
          <div className="border rounded-lg overflow-hidden">
            <div className="grid grid-cols-2">
              {[
                { q: "Q2", a1: axes[0].pole_low, a2: axes[1].pole_high },
                { q: "Q1", a1: axes[0].pole_high, a2: axes[1].pole_high },
                { q: "Q3", a1: axes[0].pole_low, a2: axes[1].pole_low },
                { q: "Q4", a1: axes[0].pole_high, a2: axes[1].pole_low },
              ].map(({ q, a1, a2 }) => (
                <div key={q} className="border p-4 bg-muted/30">
                  <p className="text-xs font-medium text-muted-foreground mb-1">{q}</p>
                  <p className="text-xs line-clamp-1">{a1}</p>
                  <p className="text-xs text-muted-foreground">+</p>
                  <p className="text-xs line-clamp-1">{a2}</p>
                </div>
              ))}
            </div>
            <div className="border-t px-4 py-2 bg-muted/10 flex items-center justify-between text-xs text-muted-foreground">
              <span>← {axes[0]?.pole_low} — {axes[0]?.driver_name} — {axes[0]?.pole_high} →</span>
              <span className="text-right">↑ {axes[1]?.pole_high}<br />↓ {axes[1]?.pole_low}</span>
            </div>
          </div>
        </div>
      )}

      {/* Axis cards */}
      <div className="space-y-6 mb-8">
        {axes.map((axis) => {
          const driver = axis.driver_id ? driverMap[axis.driver_id] : null;
          const isEditing = editingAxis === axis.id;

          return (
            <Card key={axis.id} className={axis.user_confirmed ? "border-green-300 bg-green-50" : axis.axis_locked ? "border-amber-300 bg-amber-50/40" : ""}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CardTitle className="text-base">
                      Axis {axis.axis_number}
                      {axis.user_confirmed && <CheckCircle2 className="inline h-4 w-4 text-green-600 ml-2" />}
                    </CardTitle>
                    {axis.axis_locked && (
                      <Badge variant="outline" className="text-amber-700 border-amber-400 text-xs gap-1">
                        <Lock className="h-3 w-3" /> Locked
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleLock(axis)}
                      title={axis.axis_locked ? "Unlock axis (will be replaced on next rebuild)" : "Lock axis (preserved on rebuild)"}
                      className={`gap-1.5 ${axis.axis_locked ? "text-amber-700 hover:text-amber-900" : "text-muted-foreground"}`}
                    >
                      {axis.axis_locked ? <Lock className="h-3.5 w-3.5" /> : <LockOpen className="h-3.5 w-3.5" />}
                    </Button>
                    {!axis.user_confirmed && !isEditing && (
                      <Button variant="ghost" size="sm" onClick={() => startEdit(axis)} className="gap-1.5">
                        <Edit2 className="h-3.5 w-3.5" /> Edit
                      </Button>
                    )}
                    {isEditing && (
                      <Button variant="ghost" size="sm" onClick={() => setEditingAxis(null)} className="gap-1">
                        <X className="h-3.5 w-3.5" /> Cancel
                      </Button>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {isEditing ? (
                  <div className="space-y-3">
                    <div>
                      <label className="text-xs font-medium text-muted-foreground">Driver / Uncertainty Name</label>
                      <input
                        className="mt-1 w-full rounded border px-3 py-1.5 text-sm bg-background"
                        value={editDraft.driver_name}
                        onChange={(e) => setEditDraft((d) => ({ ...d, driver_name: e.target.value }))}
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">Pole Low (pessimistic/slow end)</label>
                        <textarea
                          className="mt-1 w-full rounded border px-3 py-1.5 text-sm bg-background resize-none"
                          rows={2}
                          value={editDraft.pole_low}
                          onChange={(e) => setEditDraft((d) => ({ ...d, pole_low: e.target.value }))}
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">Pole High (optimistic/fast end)</label>
                        <textarea
                          className="mt-1 w-full rounded border px-3 py-1.5 text-sm bg-background resize-none"
                          rows={2}
                          value={editDraft.pole_high}
                          onChange={(e) => setEditDraft((d) => ({ ...d, pole_high: e.target.value }))}
                        />
                      </div>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-muted-foreground">Selection Rationale</label>
                      <textarea
                        className="mt-1 w-full rounded border px-3 py-1.5 text-sm bg-background resize-none"
                        rows={2}
                        value={editDraft.rationale}
                        onChange={(e) => setEditDraft((d) => ({ ...d, rationale: e.target.value }))}
                      />
                    </div>
                    <Button size="sm" onClick={() => saveEdit(axis.id)} disabled={saving}>
                      {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" /> : null}
                      Save Changes
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div>
                      <p className="text-xs text-muted-foreground font-medium mb-1">Critical Uncertainty</p>
                      <p className="font-medium">{axis.driver_name || "—"}</p>
                      {driver && (
                        <div className="flex gap-2 mt-1">
                          <span className="text-xs text-muted-foreground">Impact: <strong>{driver.impact_score.toFixed(1)}</strong></span>
                          <span className="text-xs text-muted-foreground">Uncertainty: <strong>{driver.uncertainty_score.toFixed(1)}</strong></span>
                        </div>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="rounded border p-3 bg-muted/30">
                        <p className="text-xs font-medium text-muted-foreground mb-1">Pole Low →</p>
                        <p className="text-sm">{axis.pole_low || "—"}</p>
                      </div>
                      <div className="rounded border p-3 bg-muted/30">
                        <p className="text-xs font-medium text-muted-foreground mb-1">← Pole High</p>
                        <p className="text-sm">{axis.pole_high || "—"}</p>
                      </div>
                    </div>
                    {axis.rationale && (
                      <div>
                        <p className="text-xs text-muted-foreground font-medium mb-1">Why this axis?</p>
                        <p className="text-sm text-muted-foreground">{axis.rationale}</p>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Confirm button */}
      {allUnconfirmed && axes.length >= 2 && (
        <div className="border rounded-lg p-6 bg-muted/20">
          <p className="text-sm font-medium mb-1">Ready to confirm?</p>
          <p className="text-sm text-muted-foreground mb-4">
            Confirming will lock these axes and immediately start generating the 4 scenario drafts.
            You can edit the drafts in Gate 2 before they go live.
          </p>
          {confirmError && (
            <p className="text-sm text-destructive mb-3">{confirmError}</p>
          )}
          <Button onClick={confirmAxes} disabled={confirming} className="gap-2">
            {confirming ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
            {confirming ? "Confirming…" : "Confirm Axes and Generate Scenarios"}
          </Button>
        </div>
      )}

      {!allUnconfirmed && (
        <div className="border border-green-300 rounded-lg p-4 bg-green-50 text-green-800 text-sm">
          <CheckCircle2 className="inline h-4 w-4 mr-2" />
          Axes confirmed. Scenario drafts are being generated.{" "}
          <Link href={`/themes/${id}/scenario-pipeline`} className="underline">
            Check pipeline status
          </Link>
        </div>
      )}
    </div>
  );
}
