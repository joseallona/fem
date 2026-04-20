"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { CheckCircle2, ChevronDown, ChevronUp, Loader2, X } from "lucide-react";
import { api, type ScenarioDraft, type ScenarioAxis } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const QUADRANT_LABELS: Record<string, string> = {
  Q1: "Axis 1 High + Axis 2 High",
  Q2: "Axis 1 Low + Axis 2 High",
  Q3: "Axis 1 Low + Axis 2 Low",
  Q4: "Axis 1 High + Axis 2 Low",
};

function StatusBadge({ status }: { status: string }) {
  if (status === "approved") return <Badge className="bg-green-500 text-white text-xs">Approved</Badge>;
  if (status === "rejected") return <Badge variant="destructive" className="text-xs">Rejected</Badge>;
  return <Badge variant="secondary" className="text-xs">Pending Review</Badge>;
}

export default function Gate2Page() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [drafts, setDrafts] = useState<ScenarioDraft[]>([]);
  const [axes, setAxes] = useState<ScenarioAxis[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedDraft, setExpandedDraft] = useState<string | null>(null);
  const [editingDraft, setEditingDraft] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<Partial<ScenarioDraft>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [acting, setActing] = useState<string | null>(null);
  const [approvingAll, setApprovingAll] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [dr, ax] = await Promise.all([
        api.scenarioPipeline.drafts(id),
        api.scenarioPipeline.axes(id),
      ]);
      setDrafts(dr);
      setAxes(ax);
      // Auto-expand first pending draft
      const firstPending = dr.find((d) => d.status === "draft");
      if (firstPending) setExpandedDraft(firstPending.id);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [id]);

  function startEdit(draft: ScenarioDraft) {
    setEditingDraft(draft.id);
    setEditDraft({
      name: draft.name,
      narrative: draft.narrative,
      key_characteristics: draft.key_characteristics,
      stakeholder_implications: draft.stakeholder_implications,
      early_indicators: draft.early_indicators,
      opportunities: draft.opportunities,
      threats: draft.threats,
      user_notes: draft.user_notes,
    });
  }

  async function saveEdit(draftId: string) {
    setSaving(draftId);
    try {
      const updated = await api.scenarioPipeline.updateDraft(draftId, editDraft);
      setDrafts((prev) => prev.map((d) => (d.id === draftId ? updated : d)));
      setEditingDraft(null);
    } finally {
      setSaving(null);
    }
  }

  async function approve(draftId: string) {
    setActing(draftId);
    setError(null);
    try {
      const updated = await api.scenarioPipeline.approveDraft(draftId);
      setDrafts((prev) => prev.map((d) => (d.id === draftId ? updated : d)));
      // Auto-expand next pending
      const nextPending = drafts.find((d) => d.id !== draftId && d.status === "draft");
      if (nextPending) setExpandedDraft(nextPending.id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setActing(null);
    }
  }

  async function reject(draftId: string) {
    setActing(draftId);
    try {
      const updated = await api.scenarioPipeline.rejectDraft(draftId);
      setDrafts((prev) => prev.map((d) => (d.id === draftId ? updated : d)));
    } finally {
      setActing(null);
    }
  }

  async function approveAll() {
    setApprovingAll(true);
    setError(null);
    try {
      const updated = await api.scenarioPipeline.approveAll(id);
      // Merge updated drafts
      const updatedMap = Object.fromEntries(updated.map((d) => [d.id, d]));
      setDrafts((prev) => prev.map((d) => updatedMap[d.id] ?? d));
      router.push(`/themes/${id}/scenarios`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setApprovingAll(false);
    }
  }

  if (loading) return <div className="p-8 text-muted-foreground">Loading…</div>;

  const pendingCount = drafts.filter((d) => d.status === "draft").length;
  const approvedCount = drafts.filter((d) => d.status === "approved").length;
  const axis1 = axes.find((a) => a.axis_number === 1);
  const axis2 = axes.find((a) => a.axis_number === 2);

  function getQuadrantDescription(draft: ScenarioDraft) {
    const p1 = draft.axis1_pole === "high" ? axis1?.pole_high : axis1?.pole_low;
    const p2 = draft.axis2_pole === "high" ? axis2?.pole_high : axis2?.pole_low;
    return `${axis1?.driver_name || "Axis 1"}: ${p1 || draft.axis1_pole} · ${axis2?.driver_name || "Axis 2"}: ${p2 || draft.axis2_pole}`;
  }

  return (
    <div className="max-w-4xl mx-auto p-8">
      <div className="mb-2">
        <Link href={`/themes/${id}/scenario-pipeline`} className="text-sm text-muted-foreground hover:underline">
          ← Scenario Pipeline
        </Link>
      </div>

      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">Gate 2 — Scenario Review</h1>
            <Badge variant="secondary">Review Required</Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-2 max-w-2xl">
            Review each generated scenario draft. Edit the narrative, characteristics, and early indicators as needed,
            then approve to promote the scenario to live monitoring.
          </p>
        </div>
        {pendingCount > 0 && (
          <Button onClick={approveAll} disabled={approvingAll} variant="outline" size="sm">
            {approvingAll ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : null}
            Approve All ({pendingCount})
          </Button>
        )}
      </div>

      {error && (
        <div className="mb-4 px-3 py-2 rounded bg-destructive/10 border border-destructive/30 text-destructive text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)}><X className="h-4 w-4" /></button>
        </div>
      )}

      {/* Progress bar */}
      <div className="mb-6 flex items-center gap-3">
        <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-primary rounded-full transition-all"
            style={{ width: `${drafts.length > 0 ? (approvedCount / drafts.length) * 100 : 0}%` }}
          />
        </div>
        <span className="text-sm text-muted-foreground">{approvedCount}/{drafts.length} approved</span>
      </div>

      {drafts.length === 0 && (
        <Card className="border-dashed">
          <CardContent className="pt-6 text-center text-muted-foreground text-sm">
            No scenario drafts yet. Complete Gate 1 to generate scenarios.
          </CardContent>
        </Card>
      )}

      <div className="space-y-4">
        {drafts.map((draft) => {
          const isExpanded = expandedDraft === draft.id;
          const isEditing = editingDraft === draft.id;

          return (
            <Card key={draft.id} className={
              draft.status === "approved" ? "border-green-300" :
              draft.status === "rejected" ? "opacity-60 border-muted" : ""
            }>
              {/* Header — always visible */}
              <CardHeader
                className="pb-2 cursor-pointer"
                onClick={() => setExpandedDraft(isExpanded ? null : draft.id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-xs font-mono text-muted-foreground shrink-0">{draft.quadrant}</span>
                    <CardTitle className="text-base truncate">{draft.name}</CardTitle>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <StatusBadge status={draft.status} />
                    {isExpanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">{getQuadrantDescription(draft)}</p>
              </CardHeader>

              {isExpanded && (
                <CardContent>
                  {isEditing ? (
                    /* Edit form */
                    <div className="space-y-4">
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">Scenario Name</label>
                        <input
                          className="mt-1 w-full rounded border px-3 py-1.5 text-sm bg-background"
                          value={editDraft.name || ""}
                          onChange={(e) => setEditDraft((d) => ({ ...d, name: e.target.value }))}
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">Narrative</label>
                        <textarea
                          className="mt-1 w-full rounded border px-3 py-2 text-sm bg-background resize-none"
                          rows={8}
                          value={editDraft.narrative || ""}
                          onChange={(e) => setEditDraft((d) => ({ ...d, narrative: e.target.value }))}
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">
                          Key Characteristics (one per line)
                        </label>
                        <textarea
                          className="mt-1 w-full rounded border px-3 py-2 text-sm bg-background resize-none"
                          rows={4}
                          value={(editDraft.key_characteristics || []).join("\n")}
                          onChange={(e) =>
                            setEditDraft((d) => ({ ...d, key_characteristics: e.target.value.split("\n").filter(Boolean) }))
                          }
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">
                          Early Indicators (one per line — these become monitoring queries)
                        </label>
                        <textarea
                          className="mt-1 w-full rounded border px-3 py-2 text-sm bg-background resize-none"
                          rows={4}
                          value={(editDraft.early_indicators || []).join("\n")}
                          onChange={(e) =>
                            setEditDraft((d) => ({ ...d, early_indicators: e.target.value.split("\n").filter(Boolean) }))
                          }
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">Reviewer Notes</label>
                        <textarea
                          className="mt-1 w-full rounded border px-3 py-2 text-sm bg-background resize-none"
                          rows={2}
                          value={editDraft.user_notes || ""}
                          onChange={(e) => setEditDraft((d) => ({ ...d, user_notes: e.target.value }))}
                        />
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => saveEdit(draft.id)} disabled={saving === draft.id}>
                          {saving === draft.id ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" /> : null}
                          Save Changes
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setEditingDraft(null)}>Cancel</Button>
                      </div>
                    </div>
                  ) : (
                    /* Read view */
                    <div className="space-y-4">
                      {draft.narrative && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground mb-1">Narrative</p>
                          <p className="text-sm leading-relaxed whitespace-pre-line">{draft.narrative}</p>
                        </div>
                      )}

                      {draft.key_characteristics.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground mb-1">Key Characteristics</p>
                          <ul className="space-y-1">
                            {draft.key_characteristics.map((c, i) => (
                              <li key={i} className="text-sm flex gap-2">
                                <span className="text-muted-foreground shrink-0">·</span>{c}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {draft.stakeholder_implications && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground mb-1">Stakeholder Implications</p>
                          <p className="text-sm text-muted-foreground">{draft.stakeholder_implications}</p>
                        </div>
                      )}

                      <div className="grid grid-cols-2 gap-4">
                        {draft.opportunities.length > 0 && (
                          <div>
                            <p className="text-xs font-medium text-green-700 mb-1">Opportunities</p>
                            <ul className="space-y-1">
                              {draft.opportunities.map((o, i) => <li key={i} className="text-xs text-muted-foreground">+ {o}</li>)}
                            </ul>
                          </div>
                        )}
                        {draft.threats.length > 0 && (
                          <div>
                            <p className="text-xs font-medium text-red-700 mb-1">Threats</p>
                            <ul className="space-y-1">
                              {draft.threats.map((t, i) => <li key={i} className="text-xs text-muted-foreground">– {t}</li>)}
                            </ul>
                          </div>
                        )}
                      </div>

                      {draft.early_indicators.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground mb-1">
                            Early Indicators <span className="font-normal">(will be monitored after approval)</span>
                          </p>
                          <div className="space-y-1">
                            {draft.early_indicators.map((ind, i) => (
                              <div key={i} className="flex gap-2 items-start text-xs">
                                <span className="text-muted-foreground shrink-0 mt-0.5">◉</span>
                                <span>{ind}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {draft.user_notes && (
                        <div className="border rounded p-3 bg-muted/20">
                          <p className="text-xs font-medium text-muted-foreground mb-1">Reviewer Notes</p>
                          <p className="text-xs">{draft.user_notes}</p>
                        </div>
                      )}

                      {/* Actions */}
                      {draft.status === "draft" && (
                        <div className="flex gap-2 pt-2 border-t">
                          <Button
                            size="sm"
                            onClick={() => approve(draft.id)}
                            disabled={acting === draft.id}
                            className="gap-1.5"
                          >
                            {acting === draft.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                            Approve & Activate
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => startEdit(draft)}
                            disabled={!!acting}
                          >
                            Edit
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-destructive hover:text-destructive ml-auto"
                            onClick={() => reject(draft.id)}
                            disabled={acting === draft.id}
                          >
                            Reject
                          </Button>
                        </div>
                      )}

                      {draft.status === "approved" && (
                        <div className="flex items-center gap-2 pt-2 border-t text-green-700 text-sm">
                          <CheckCircle2 className="h-4 w-4" />
                          Approved{draft.approved_at ? ` · ${new Date(draft.approved_at).toLocaleString()}` : ""}
                          {draft.approved_scenario_id && (
                            <Link
                              href={`/themes/${id}/scenarios`}
                              className="ml-auto text-xs text-muted-foreground hover:underline"
                            >
                              View scenario →
                            </Link>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              )}
            </Card>
          );
        })}
      </div>

      {approvedCount === drafts.length && drafts.length > 0 && (
        <div className="mt-8 border border-green-300 rounded-lg p-4 bg-green-50 text-green-800 text-sm flex items-center gap-3">
          <CheckCircle2 className="h-5 w-5 shrink-0" />
          <div>
            All {drafts.length} scenarios approved and live.{" "}
            <Link href={`/themes/${id}/scenarios`} className="underline">View scenarios</Link>{" "}
            or{" "}
            <Link href={`/themes/${id}/scenario-pipeline`} className="underline">return to pipeline</Link>.
          </div>
        </div>
      )}
    </div>
  );
}
