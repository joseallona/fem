"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Pencil, Trash2, Link2, Unlink, ArrowRightLeft } from "lucide-react";
import { api, type Scenario, type Signal, type SignalLinkOut } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const MOMENTUM_ICON: Record<string, string> = { increasing: "↑", stable: "→", decreasing: "↓" };
const MOMENTUM_COLOR: Record<string, string> = { increasing: "text-green-600", stable: "text-muted-foreground", decreasing: "text-red-500" };
const CONFIDENCE_VARIANT: Record<string, "default" | "secondary" | "outline"> = { high: "default", medium: "secondary", low: "outline" };
const REL_COLOR: Record<string, string> = { supports: "text-green-600", weakens: "text-red-500", neutral: "text-muted-foreground" };

export default function ScenarioDetailPage() {
  const { id: themeId, scenarioId } = useParams<{ id: string; scenarioId: string }>();
  const router = useRouter();

  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [links, setLinks] = useState<SignalLinkOut[]>([]);
  const [themeSignals, setThemeSignals] = useState<Signal[]>([]);
  const [allScenarios, setAllScenarios] = useState<Scenario[]>([]);

  // Edit state
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editNarrative, setEditNarrative] = useState("");

  // Link form state
  const [showLinkForm, setShowLinkForm] = useState(false);
  const [linkSignalId, setLinkSignalId] = useState("");
  const [linkRelType, setLinkRelType] = useState("supports");

  useEffect(() => {
    Promise.all([
      api.scenarios.get(scenarioId),
      api.scenarios.getSignals(scenarioId),
      api.signals.list(themeId, { limit: "100", status: "active" }),
      api.scenarios.list(themeId),
    ]).then(([sc, lks, sigs, scenarios]) => {
      setScenario(sc);
      setEditName(sc.name);
      setEditNarrative(sc.narrative ?? "");
      setLinks(lks);
      setThemeSignals(sigs);
      setAllScenarios(scenarios);
    });
  }, [scenarioId, themeId]);

  async function handleSaveEdit(e: React.FormEvent) {
    e.preventDefault();
    const updated = await api.scenarios.update(scenarioId, { name: editName, narrative: editNarrative });
    setScenario(updated);
    setEditing(false);
  }

  async function handleDelete() {
    if (!confirm("Delete this scenario? This cannot be undone.")) return;
    await api.scenarios.delete(scenarioId);
    router.push(`/themes/${themeId}/scenarios`);
  }

  async function handleUnlink(signalId: string) {
    await api.scenarios.unlinkSignal(scenarioId, signalId);
    setLinks((prev) => prev.filter((l) => l.signal_id !== signalId));
  }

  async function handleMoveTo(link: SignalLinkOut, targetScenarioId: string) {
    await api.scenarios.unlinkSignal(scenarioId, link.signal_id);
    await api.scenarios.linkSignal(targetScenarioId, {
      signal_id: link.signal_id,
      relationship_type: link.relationship_type,
      relationship_score: link.relationship_score,
      user_confirmed: true,
    });
    setLinks((prev) => prev.filter((l) => l.signal_id !== link.signal_id));
  }

  async function handleAddLink(e: React.FormEvent) {
    e.preventDefault();
    if (!linkSignalId) return;
    await api.scenarios.linkSignal(scenarioId, {
      signal_id: linkSignalId,
      relationship_type: linkRelType,
      relationship_score: 0.5,
      user_confirmed: true,
    });
    const freshLinks = await api.scenarios.getSignals(scenarioId);
    setLinks(freshLinks);
    setLinkSignalId(""); setShowLinkForm(false);
  }

  if (!scenario) return <div className="p-8 text-muted-foreground">Loading...</div>;

  const otherScenarios = allScenarios.filter((s) => s.id !== scenarioId);
  const confirmed = links.filter((l) => l.user_confirmed);
  const unconfirmed = links.filter((l) => !l.user_confirmed);
  const supports = confirmed.filter((l) => l.relationship_type === "supports");
  const weakens = confirmed.filter((l) => l.relationship_type === "weakens");
  const neutral = confirmed.filter((l) => l.relationship_type === "neutral");

  // Signals not yet linked to this scenario
  const linkedIds = new Set(links.map((l) => l.signal_id));
  const unlinkableSignals = themeSignals.filter((s) => !linkedIds.has(s.id));

  return (
    <div className="max-w-5xl mx-auto p-8">
      <div className="mb-2 flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/themes" className="hover:underline">Themes</Link>
        <span>/</span>
        <Link href={`/themes/${themeId}/scenarios`} className="hover:underline">Scenarios</Link>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        {editing ? (
          <form onSubmit={handleSaveEdit} className="flex-1 mr-4 space-y-3">
            <Input value={editName} onChange={(e) => setEditName(e.target.value)} className="text-xl font-bold" autoFocus />
            <Textarea value={editNarrative} onChange={(e) => setEditNarrative(e.target.value)} rows={3} placeholder="Narrative..." />
            <div className="flex gap-2">
              <Button type="submit" size="sm">Save</Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
            </div>
          </form>
        ) : (
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-2xl font-bold">{scenario.name}</h1>
              <Badge variant={CONFIDENCE_VARIANT[scenario.confidence_level] ?? "outline"}>
                {scenario.confidence_level} confidence
              </Badge>
              <span className={`text-xl font-bold ${MOMENTUM_COLOR[scenario.momentum_state]}`} title={scenario.momentum_state}>
                {MOMENTUM_ICON[scenario.momentum_state] ?? "→"}
              </span>
            </div>
            {scenario.narrative && (
              <p className="text-muted-foreground text-sm max-w-2xl">{scenario.narrative}</p>
            )}
          </div>
        )}
        {!editing && (
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              <Pencil className="h-3.5 w-3.5" /> Edit
            </Button>
            <Button size="sm" variant="ghost" className="text-destructive" onClick={handleDelete}>
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </div>

      {/* Rationale */}
      <Card className="mb-8">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Evidence Rationale</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-6 text-sm">
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Support</p>
              <p className="font-mono font-semibold text-green-600">{scenario.support_score.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Contradiction</p>
              <p className="font-mono font-semibold text-red-500">{scenario.contradiction_score.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Net score</p>
              <p className="font-mono font-semibold">{scenario.internal_score.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">7-day delta</p>
              <p className={`font-mono font-semibold ${scenario.recent_delta > 0 ? "text-green-600" : scenario.recent_delta < 0 ? "text-red-500" : ""}`}>
                {scenario.recent_delta >= 0 ? "+" : ""}{scenario.recent_delta.toFixed(2)}
              </p>
            </div>
            <div className="ml-auto text-xs text-muted-foreground self-end">
              High confidence ≥ 5.0 · Medium ≥ 2.0 · Momentum shifts at ±1.0
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Legacy unconfirmed signals (backfilled before this change) */}
      {unconfirmed.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold flex items-center gap-2">
              Unreviewed Mappings
              <Badge variant="secondary">{unconfirmed.length}</Badge>
            </h2>
          </div>
          <div className="space-y-2">
            {unconfirmed.map((link) => (
              <SignalCard
                key={link.signal_id}
                link={link}
                otherScenarios={otherScenarios}
                onUnlink={handleUnlink}
                onMoveTo={handleMoveTo}
              />
            ))}
          </div>
        </div>
      )}

      {/* Confirmed signal panels */}
      <div className="grid grid-cols-2 gap-6 mb-8">
        <div>
          <h2 className="text-sm font-semibold text-green-700 mb-3">Supports ({supports.length})</h2>
          {supports.length === 0 ? (
            <p className="text-xs text-muted-foreground">No supporting signals yet.</p>
          ) : (
            <div className="space-y-2">
              {supports.map((link) => (
                <SignalCard key={link.signal_id} link={link} otherScenarios={otherScenarios} onUnlink={handleUnlink} onMoveTo={handleMoveTo} />
              ))}
            </div>
          )}
        </div>
        <div>
          <h2 className="text-sm font-semibold text-red-600 mb-3">Weakens ({weakens.length})</h2>
          {weakens.length === 0 ? (
            <p className="text-xs text-muted-foreground">No weakening signals yet.</p>
          ) : (
            <div className="space-y-2">
              {weakens.map((link) => (
                <SignalCard key={link.signal_id} link={link} otherScenarios={otherScenarios} onUnlink={handleUnlink} onMoveTo={handleMoveTo} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Neutral signals */}
      {neutral.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-muted-foreground mb-3">Neutral ({neutral.length})</h2>
          <div className="space-y-2">
            {neutral.map((link) => (
              <SignalCard key={link.signal_id} link={link} otherScenarios={otherScenarios} onUnlink={handleUnlink} onMoveTo={handleMoveTo} />
            ))}
          </div>
        </div>
      )}

      {/* Add signal link */}
      <div>
        {showLinkForm ? (
          <Card className="p-4">
            <form onSubmit={handleAddLink} className="space-y-3">
              <h3 className="text-sm font-semibold">Link a Signal</h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Signal</Label>
                  <Select value={linkSignalId} onValueChange={setLinkSignalId}>
                    <SelectTrigger><SelectValue placeholder="Select signal..." /></SelectTrigger>
                    <SelectContent>
                      {unlinkableSignals.map((s) => (
                        <SelectItem key={s.id} value={s.id}>{s.title.slice(0, 60)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label>Relationship</Label>
                  <Select value={linkRelType} onValueChange={setLinkRelType}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="supports">Supports</SelectItem>
                      <SelectItem value="weakens">Weakens</SelectItem>
                      <SelectItem value="neutral">Neutral</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex gap-2">
                <Button type="submit" size="sm" disabled={!linkSignalId}>
                  <Link2 className="h-3.5 w-3.5" /> Link
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => setShowLinkForm(false)}>Cancel</Button>
              </div>
            </form>
          </Card>
        ) : (
          <Button variant="outline" size="sm" onClick={() => setShowLinkForm(true)}>
            <Link2 className="h-3.5 w-3.5" /> Link a Signal
          </Button>
        )}
      </div>
    </div>
  );
}

function SignalCard({
  link,
  otherScenarios,
  onUnlink,
  onMoveTo,
}: {
  link: SignalLinkOut;
  otherScenarios: Scenario[];
  onUnlink: (id: string) => void;
  onMoveTo: (link: SignalLinkOut, targetScenarioId: string) => void;
}) {
  return (
    <Card>
      <CardContent className="p-3 flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          {link.source_url ? (
            <a href={link.source_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium line-clamp-2 hover:underline block">{link.signal_title}</a>
          ) : (
            <p className="text-sm font-medium line-clamp-2">{link.signal_title}</p>
          )}
          <div className="flex gap-1.5 mt-1 flex-wrap">
            <span className={`text-xs font-medium ${REL_COLOR[link.relationship_type]}`}>{link.relationship_type}</span>
            {link.signal_type && <Badge variant="outline" className="text-xs">{link.signal_type}</Badge>}
            {link.steep_category && <Badge variant="secondary" className="text-xs">{link.steep_category}</Badge>}
            {link.horizon && <Badge variant="outline" className="text-xs">{link.horizon}</Badge>}
            {link.importance_score !== undefined && (
              <span className="text-xs text-muted-foreground">score {link.importance_score.toFixed(2)}</span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {otherScenarios.length > 0 && (
            <div className="relative">
              <select
                defaultValue=""
                onChange={(e) => {
                  if (e.target.value) onMoveTo(link, e.target.value);
                }}
                className="appearance-none h-7 pl-7 pr-2 text-xs border rounded-md bg-background text-muted-foreground hover:text-foreground hover:border-foreground/30 cursor-pointer focus:outline-none"
                title="Move to another scenario"
              >
                <option value="" disabled>Move to…</option>
                {otherScenarios.map((s) => (
                  <option key={s.id} value={s.id}>{s.name.slice(0, 35)}</option>
                ))}
              </select>
              <ArrowRightLeft className="pointer-events-none absolute left-1.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            </div>
          )}
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7 text-muted-foreground hover:text-destructive"
            onClick={() => onUnlink(link.signal_id)}
            title="Dismiss"
          >
            <Unlink className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
