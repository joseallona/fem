"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Plus, BookOpen, Rss, Zap, Target, FileText, GitBranch,
  CheckCircle, PauseCircle, XCircle, Search, Loader2,
  ChevronDown, ChevronUp, FileText as DocIcon, Activity,
} from "lucide-react";
import { api, type Source, type SourceStats } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const STATUS_ACTIONS: Record<string, { next: string; label: string; icon: React.ElementType }> = {
  suggested: { next: "approved", label: "Approve", icon: CheckCircle },
  approved: { next: "paused", label: "Pause", icon: PauseCircle },
  paused: { next: "approved", label: "Resume", icon: CheckCircle },
};

const STATUS_BADGE: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  suggested: "outline",
  approved: "default",
  paused: "secondary",
  blocked: "destructive",
};

function yieldColor(rate: number): string {
  if (rate >= 0.15) return "text-green-600";
  if (rate >= 0.05) return "text-amber-600";
  return "text-red-500";
}

function scoreBar(value: number, max = 1): string {
  const pct = Math.round((value / max) * 100);
  return `${pct}%`;
}

function friendlyAddError(raw: string): string {
  try {
    const parsed = JSON.parse(raw);
    if (parsed?.detail) return String(parsed.detail);
  } catch { /* not JSON */ }
  if (raw.toLowerCase().includes("failed to fetch") || raw.toLowerCase().includes("networkerror")) {
    return "Could not reach the backend. Make sure it is running.";
  }
  return raw;
}

interface EditingSource {
  trustScore: string;
  crawlFrequency: string;
}

export default function SourcesPage() {
  const { id } = useParams<{ id: string }>();
  const [sources, setSources] = useState<Source[]>([]);
  const [stats, setStats] = useState<Record<string, SourceStats>>({});
  const [adding, setAdding] = useState(false);
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [sourceType, setSourceType] = useState("news");
  const [submitting, setSubmitting] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [discovering, setDiscovering] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [editing, setEditing] = useState<Record<string, EditingSource>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});

  useEffect(() => {
    api.sources.list(id).then(setSources);
    api.sourceStats.get(id).then(setStats).catch(() => {/* stats optional */});
  }, [id]);

  function toggleExpand(sourceId: string) {
    setExpanded((prev) => ({ ...prev, [sourceId]: !prev[sourceId] }));
  }

  function startEdit(s: Source) {
    setEditing((prev) => ({
      ...prev,
      [s.id]: { trustScore: String(s.trust_score), crawlFrequency: s.crawl_frequency },
    }));
  }

  function cancelEdit(sourceId: string) {
    setEditing((prev) => { const n = { ...prev }; delete n[sourceId]; return n; });
  }

  async function saveEdit(s: Source) {
    const e = editing[s.id];
    if (!e) return;
    const trust = parseFloat(e.trustScore);
    if (isNaN(trust) || trust < 0 || trust > 1) return;
    setSaving((prev) => ({ ...prev, [s.id]: true }));
    try {
      const updated = await api.sources.update(s.id, {
        trust_score: trust,
        crawl_frequency: e.crawlFrequency,
      });
      setSources((prev) => prev.map((x) => (x.id === s.id ? updated : x)));
      cancelEdit(s.id);
    } finally {
      setSaving((prev) => ({ ...prev, [s.id]: false }));
    }
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    setAddError(null);
    setSubmitting(true);
    try {
      const s = await api.sources.add(id, { url: url.trim(), name, source_type: sourceType, status: "suggested" });
      setSources((prev) => [s, ...prev]);
      setUrl(""); setName(""); setAdding(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setAddError(friendlyAddError(msg));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleStatusChange(source: Source, nextStatus: string) {
    const updated = await api.sources.update(source.id, { status: nextStatus });
    setSources((prev) => prev.map((s) => (s.id === source.id ? updated : s)));
  }

  async function handleDiscover() {
    setDiscovering(true);
    try {
      const newSources = await api.sources.discover(id);
      if (newSources.length > 0) {
        setSources((prev) => {
          const existingIds = new Set(prev.map((s) => s.id));
          return [...prev, ...newSources.filter((s) => !existingIds.has(s.id))];
        });
      }
    } finally {
      setDiscovering(false);
    }
  }

  return (
    <div className="max-w-5xl mx-auto p-8">
      <div className="mb-2">
        <Link href="/themes" className="text-sm text-muted-foreground hover:underline">← Themes</Link>
      </div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Sources</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleDiscover} disabled={discovering}>
            {discovering ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            {discovering ? "Discovering..." : "Discover Sources"}
          </Button>
          <Button onClick={() => { setAdding(true); setAddError(null); }}>
            <Plus className="h-4 w-4" /> Add Source
          </Button>
        </div>
      </div>

      {/* Nav */}
      <div className="flex gap-1 mb-8 border-b">
        {[
          { label: "Dashboard", href: `/themes/${id}`, icon: BookOpen },
          { label: "Sources", href: `/themes/${id}/sources`, icon: Rss },
          { label: "Signals", href: `/themes/${id}/signals`, icon: Zap },
          { label: "Scenarios", href: `/themes/${id}/scenarios`, icon: Target },
          { label: "Scenario Pipeline", href: `/themes/${id}/scenario-pipeline`, icon: GitBranch },
          { label: "Briefs", href: `/themes/${id}/briefs`, icon: FileText },
        ].map(({ label, href, icon: Icon }) => (
          <Link key={href} href={href} className={`flex items-center gap-1.5 px-4 py-2 text-sm border-b-2 transition-colors ${href === `/themes/${id}/sources` ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground hover:border-primary"}`}>
            <Icon className="h-3.5 w-3.5" />{label}
          </Link>
        ))}
      </div>

      {adding && (
        <Card className="mb-6 p-4">
          <form onSubmit={handleAdd} className="space-y-3">
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2 space-y-1">
                <Label>URL *</Label>
                <Input
                  value={url}
                  onChange={(e) => { setUrl(e.target.value); setAddError(null); }}
                  placeholder="https://example.com or www.thelancet.com"
                  autoFocus
                  disabled={submitting}
                />
                <p className="text-xs text-muted-foreground">
                  Paste a homepage, article listing, or RSS feed URL. https:// is added automatically if omitted.
                </p>
              </div>
              <div className="space-y-1">
                <Label>Type</Label>
                <Select value={sourceType} onValueChange={submitting ? undefined : setSourceType}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {["news", "academic", "government", "blog", "patent", "newsletter"].map((t) => (
                      <SelectItem key={t} value={t}>{t}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1">
              <Label>Name (optional)</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Display name" disabled={submitting} />
            </div>
            {addError && <p className="text-sm text-destructive">{addError}</p>}
            <div className="flex gap-2">
              <Button type="submit" disabled={submitting || !url.trim()}>
                {submitting ? <><Loader2 className="h-4 w-4 animate-spin" /> Checking URL…</> : "Add"}
              </Button>
              <Button type="button" variant="ghost" onClick={() => { setAdding(false); setAddError(null); }} disabled={submitting}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}

      {sources.length === 0 ? (
        <p className="text-muted-foreground text-sm">No sources yet. Add one to start monitoring.</p>
      ) : (
        <div className="space-y-2">
          {sources.map((s) => {
            const action = STATUS_ACTIONS[s.status];
            const st = stats[s.id];
            const isExpanded = expanded[s.id];
            const ed = editing[s.id];

            return (
              <Card key={s.id}>
                <CardContent className="p-4">
                  {/* Top row */}
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-sm font-medium truncate">{s.name || s.domain}</p>
                        <Badge variant={STATUS_BADGE[s.status] || "outline"}>{s.status}</Badge>
                        {s.source_type && <Badge variant="outline" className="text-xs">{s.source_type}</Badge>}
                        {s.discovery_mode === "system" && (
                          <Badge variant="outline" className="text-xs text-blue-600 border-blue-200">auto-discovered</Badge>
                        )}
                        {s.status === "approved" && !s.initial_crawl_done && (
                          <Badge variant="outline" className="text-xs text-amber-600 border-amber-200">initial crawl pending</Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground truncate mt-0.5">{s.url}</p>
                      {s.last_crawled_at && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Last crawled: {new Date(s.last_crawled_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {action && (
                        <Button size="sm" variant="outline" onClick={() => handleStatusChange(s, action.next)}>
                          <action.icon className="h-3.5 w-3.5" /> {action.label}
                        </Button>
                      )}
                      <Button size="sm" variant="ghost" className="text-destructive" onClick={() => handleStatusChange(s, "blocked")}>
                        <XCircle className="h-3.5 w-3.5" />
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => { toggleExpand(s.id); if (!editing[s.id]) startEdit(s); }}>
                        {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                      </Button>
                    </div>
                  </div>

                  {/* Yield stats bar — always visible if data exists */}
                  {st && (
                    <div className="mt-3 flex items-center gap-5 text-xs text-muted-foreground border-t pt-3">
                      <span className="flex items-center gap-1">
                        <DocIcon className="h-3 w-3" />
                        <span className="font-medium text-foreground">{st.docs_fetched}</span> docs
                      </span>
                      <span className="flex items-center gap-1">
                        <Zap className="h-3 w-3" />
                        <span className="font-medium text-foreground">{st.signals_yielded}</span> signals
                      </span>
                      <span className="flex items-center gap-1">
                        <Activity className="h-3 w-3" />
                        yield&nbsp;
                        <span className={`font-medium ${yieldColor(st.yield_rate)}`}>
                          {(st.yield_rate * 100).toFixed(1)}%
                        </span>
                      </span>
                      {st.signals_yielded > 0 && (
                        <span className="flex items-center gap-1">
                          avg score&nbsp;
                          <span className="font-medium text-foreground">{st.avg_importance.toFixed(2)}</span>
                          {/* mini bar */}
                          <span className="inline-flex h-1.5 w-16 rounded-full bg-muted overflow-hidden ml-1">
                            <span className="h-full bg-primary rounded-full" style={{ width: scoreBar(st.avg_importance) }} />
                          </span>
                        </span>
                      )}
                      {st.docs_fetched === 0 && s.initial_crawl_done && (
                        <span className="text-destructive">no docs fetched — consider blocking</span>
                      )}
                    </div>
                  )}

                  {/* Expanded: trust score + crawl frequency editors */}
                  {isExpanded && ed && (
                    <div className="mt-4 pt-4 border-t grid grid-cols-2 gap-4">
                      {/* Trust score */}
                      <div className="space-y-2">
                        <Label className="text-xs">
                          Trust score
                          <span className="ml-1 font-normal text-muted-foreground">
                            (0–1 · affects signal importance)
                          </span>
                        </Label>
                        <div className="flex items-center gap-3">
                          <input
                            type="range"
                            min={0} max={1} step={0.05}
                            value={ed.trustScore}
                            onChange={(e) =>
                              setEditing((prev) => ({ ...prev, [s.id]: { ...prev[s.id], trustScore: e.target.value } }))
                            }
                            className="flex-1 h-1.5 accent-primary"
                          />
                          <span className="w-10 text-right text-sm font-mono">{parseFloat(ed.trustScore).toFixed(2)}</span>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Higher trust = source signals weighted more heavily. Academic/government sources typically 0.7–0.9. Blogs 0.3–0.5.
                        </p>
                      </div>

                      {/* Crawl frequency */}
                      <div className="space-y-2">
                        <Label className="text-xs">
                          Crawl frequency
                          <span className="ml-1 font-normal text-muted-foreground">
                            (how often the scheduler revisits)
                          </span>
                        </Label>
                        <Select
                          value={ed.crawlFrequency}
                          onValueChange={(v) =>
                            setEditing((prev) => ({ ...prev, [s.id]: { ...prev[s.id], crawlFrequency: v } }))
                          }
                        >
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="hourly">Hourly</SelectItem>
                            <SelectItem value="daily">Daily</SelectItem>
                            <SelectItem value="weekly">Weekly</SelectItem>
                            <SelectItem value="manual">Manual only</SelectItem>
                          </SelectContent>
                        </Select>
                        <p className="text-xs text-muted-foreground">
                          High-yield sources are worth daily. Low-yield sources can stay weekly to reduce noise.
                        </p>
                      </div>

                      <div className="col-span-2 flex gap-2 pt-1">
                        <Button
                          size="sm"
                          onClick={() => saveEdit(s)}
                          disabled={saving[s.id]}
                        >
                          {saving[s.id] ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Saving…</> : "Save"}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => { cancelEdit(s.id); toggleExpand(s.id); }}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
