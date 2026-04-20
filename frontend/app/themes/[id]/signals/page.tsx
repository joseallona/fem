"use client";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Plus, BookOpen, Rss, Zap, Target, FileText, GitBranch, Link2, X, HelpCircle, ChevronDown } from "lucide-react";
import { api, type Signal, type Scenario, type SignalExplanation } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";

// ── Classification glossary ────────────────────────────────────────────────

const TYPE_COLOR: Record<string, string> = {
  trend:       "bg-blue-50 text-blue-700 border-blue-200",
  weak_signal: "bg-amber-50 text-amber-700 border-amber-200",
  wildcard:    "bg-red-50 text-red-700 border-red-200",
  driver:      "bg-purple-50 text-purple-700 border-purple-200",
  indicator:   "bg-teal-50 text-teal-700 border-teal-200",
};

const TYPE_INFO: Record<string, { label: string; how: string; example: string }> = {
  trend: {
    label: "Trend",
    how: "Detected when the LLM finds language of direction or continuity — words like growing, rising, declining, shift, momentum. The pipeline also looks for these keywords deterministically as a fallback.",
    example: "\"EV adoption is rising steadily across European markets.\"",
  },
  weak_signal: {
    label: "Weak Signal",
    how: "Assigned when the text describes something emerging, niche, experimental or nascent — early evidence of a change that hasn't become mainstream yet. High novelty score from the LLM reinforces this.",
    example: "\"A handful of biotech startups are piloting RNA-based crop protection.\"",
  },
  wildcard: {
    label: "Wildcard",
    how: "Triggered by language of surprise or rupture — unprecedented, unexpected, shock, sudden. Low probability but potentially paradigm-shifting.",
    example: "\"An unexpected blackout disabled grid infrastructure across three states simultaneously.\"",
  },
  driver: {
    label: "Driver",
    how: "Assigned when the text names a fundamental or structural force — a root cause rather than a symptom. Keywords: fundamental, structural, underlying, catalyst, force, pressure.",
    example: "\"Demographic ageing is the structural pressure behind pension system reform across the OECD.\"",
  },
  indicator: {
    label: "Indicator",
    how: "Assigned to signals that are measurable data points rather than events or narratives. Keywords: measure, metric, index, rate, data shows, statistics.",
    example: "\"US core inflation index fell to 2.4% in Q3, the lowest reading in two years.\"",
  },
};

const STEEP_INFO: Record<string, { label: string; description: string }> = {
  social: {
    label: "Social",
    description: "Demographics, culture, lifestyle, inequality, education, health behaviour, workforce, migration, consumer values.",
  },
  technological: {
    label: "Technological",
    description: "AI, robotics, automation, software platforms, patents, R&D breakthroughs, semiconductors, quantum computing.",
  },
  economic: {
    label: "Economic",
    description: "Markets, investment, GDP, finance, labour, employment, trade, tariffs, revenue, pensions.",
  },
  environmental: {
    label: "Environmental",
    description: "Climate change, carbon emissions, renewable energy, pollution, biodiversity, sustainability transitions.",
  },
  political: {
    label: "Political",
    description: "Policy, regulation, legislation, government decisions, elections, FDA approvals, drug/therapy regulation, compliance.",
  },
};

const HORIZON_INFO: Record<string, { label: string; description: string }> = {
  H1: {
    label: "H1 — Present (0–2 yrs)",
    description: "Current dominant systems. Observable right now. Keywords: today, now, this year, present, existing, immediate. Also triggered by years ≤2 years from now.",
  },
  H2: {
    label: "H2 — Transition (2–7 yrs)",
    description: "Emerging innovations disrupting the present. The contested middle ground where old meets new. Keywords: transition, emerging, disrupt, shift, medium-term. Years 2–7 years ahead.",
  },
  H3: {
    label: "H3 — Future (7+ yrs)",
    description: "Seeds of future systems — currently marginal but may become dominant. Keywords: long-term, decade, next generation, visionary, speculative. Years 7+ ahead.",
  },
};

const STEEP = Object.keys(STEEP_INFO);
const TYPES = Object.keys(TYPE_INFO);
const HORIZONS = Object.keys(HORIZON_INFO);

// ── Selection rationale ───────────────────────────────────────────────────

function whySelected(s: { signal_type?: string; novelty_score: number; relevance_score: number; importance_score: number; steep_category?: string; horizon?: string }): string {
  const parts: string[] = [];

  // Primary reason comes from the signal type
  switch (s.signal_type) {
    case "trend":        parts.push("persistent pattern detected across multiple sources"); break;
    case "weak_signal":  parts.push("early-stage indicator of emerging change"); break;
    case "wildcard":     parts.push("low-probability, high-impact discontinuity"); break;
    case "driver":       parts.push("structural force shaping multiple future outcomes"); break;
    case "indicator":    parts.push("measurable data point tracking a trajectory"); break;
    default:             parts.push("detected as relevant to the theme focal question"); break;
  }

  // Secondary qualifiers from scores
  if (s.novelty_score >= 0.65)    parts.push("novel — not seen in previous pipeline runs");
  if (s.relevance_score >= 0.70)  parts.push("strongly relevant to focal question");
  if (s.importance_score >= 0.75) parts.push("high composite importance");

  return parts.join(" · ");
}

// ── Helper: labelled select with a tooltip on the label ──────────────────

function LabelWithHelp({ children, tip }: { children: React.ReactNode; tip: React.ReactNode }) {
  return (
    <div className="flex items-center gap-1">
      <Label className="text-sm">{children}</Label>
      <Tooltip content={tip} side="right">
        <span className="cursor-help text-muted-foreground">
          <HelpCircle className="h-3.5 w-3.5" />
        </span>
      </Tooltip>
    </div>
  );
}

// ── Tooltip content blocks ────────────────────────────────────────────────

function TypeTip({ t }: { t: string }) {
  const info = TYPE_INFO[t];
  if (!info) return <span>{t}</span>;
  return (
    <div className="space-y-1.5">
      <p className="font-semibold">{info.label}</p>
      <p className="text-muted-foreground leading-relaxed">{info.how}</p>
      <p className="italic text-muted-foreground border-t pt-1 mt-1">{info.example}</p>
    </div>
  );
}

function SteepTip({ t }: { t: string }) {
  const info = STEEP_INFO[t];
  if (!info) return <span>{t}</span>;
  return (
    <div className="space-y-1">
      <p className="font-semibold">{info.label}</p>
      <p className="text-muted-foreground leading-relaxed">{info.description}</p>
    </div>
  );
}

function HorizonTip({ t }: { t: string }) {
  const info = HORIZON_INFO[t];
  if (!info) return <span>{t}</span>;
  return (
    <div className="space-y-1">
      <p className="font-semibold">{info.label}</p>
      <p className="text-muted-foreground leading-relaxed">{info.description}</p>
    </div>
  );
}

// ── Filter select (native <select> with chevron) ──────────────────────────

function FilterSelect({ value, onChange, children }: {
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 appearance-none rounded-md border border-input bg-transparent pl-2 pr-7 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 opacity-50" />
    </div>
  );
}

// ── Filter chip ──────────────────────────────────────────────────────────

function Chip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
      {label}
      <button onClick={onRemove} className="hover:text-foreground leading-none">×</button>
    </span>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────

export default function SignalsPage() {
  const { id } = useParams<{ id: string }>();
  const [signals, setSignals] = useState<Signal[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [signalType, setSignalType] = useState("trend");
  const [steep, setSteep] = useState("social");
  const [horizon, setHorizon] = useState("H2");
  const [linkingSignalId, setLinkingSignalId] = useState<string | null>(null);
  const [linkScenarioId, setLinkScenarioId] = useState("");
  const [linkRelType, setLinkRelType] = useState("supports");
  const [explanations, setExplanations] = useState<Record<string, SignalExplanation>>({});
  const [expandedExplanation, setExpandedExplanation] = useState<string | null>(null);

  // Filters & sort
  const [filterType, setFilterType] = useState("");
  const [filterSteep, setFilterSteep] = useState("");
  const [filterHorizon, setFilterHorizon] = useState("");
  const [filterStatus, setFilterStatus] = useState("active");
  const [sortBy, setSortBy] = useState("importance_desc");
  const [search, setSearch] = useState("");

  const displayed = useMemo(() => {
    let list = [...signals];
    if (filterType)    list = list.filter((s) => s.signal_type === filterType);
    if (filterSteep)   list = list.filter((s) => s.steep_category === filterSteep);
    if (filterHorizon) list = list.filter((s) => s.horizon === filterHorizon);
    if (filterStatus)  list = list.filter((s) => s.status === filterStatus);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter((s) => s.title.toLowerCase().includes(q) || s.summary?.toLowerCase().includes(q));
    }
    list.sort((a, b) => {
      switch (sortBy) {
        case "importance_desc": return b.importance_score - a.importance_score;
        case "importance_asc":  return a.importance_score - b.importance_score;
        case "novelty_desc":    return b.novelty_score - a.novelty_score;
        case "relevance_desc":  return b.relevance_score - a.relevance_score;
        case "newest":          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        case "title_asc":       return a.title.localeCompare(b.title);
        default: return 0;
      }
    });
    return list;
  }, [signals, filterType, filterSteep, filterHorizon, filterStatus, sortBy, search]);

  useEffect(() => {
    Promise.all([api.signals.list(id), api.scenarios.list(id)]).then(
      ([sigs, scs]) => { setSignals(sigs); setScenarios(scs); }
    );
  }, [id]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    const s = await api.signals.create(id, { title, summary, signal_type: signalType, steep_category: steep, horizon });
    setSignals((prev) => [s, ...prev]);
    setTitle(""); setSummary(""); setAdding(false);
  }

  async function handleArchive(signal: Signal) {
    const updated = await api.signals.update(signal.id, { status: "archived" });
    setSignals((prev) => prev.map((s) => (s.id === signal.id ? updated : s)));
  }

  async function handleToggleExplanation(signalId: string) {
    if (expandedExplanation === signalId) { setExpandedExplanation(null); return; }
    if (!explanations[signalId]) {
      const exp = await api.signals.explanation(signalId);
      setExplanations((prev) => ({ ...prev, [signalId]: exp }));
    }
    setExpandedExplanation(signalId);
  }

  async function handleLinkToScenario(e: React.FormEvent) {
    e.preventDefault();
    if (!linkingSignalId || !linkScenarioId) return;
    await api.scenarios.linkSignal(linkScenarioId, {
      signal_id: linkingSignalId,
      relationship_type: linkRelType,
      relationship_score: 0.5,
      user_confirmed: true,
    });
    setLinkingSignalId(null);
    setLinkScenarioId("");
  }

  return (
    <TooltipProvider>
      <div className="max-w-5xl mx-auto p-8">
        <div className="mb-2">
          <Link href="/themes" className="text-sm text-muted-foreground hover:underline">← Themes</Link>
        </div>
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Signals</h1>
          <Button onClick={() => setAdding(true)}><Plus className="h-4 w-4" /> Add Signal</Button>
        </div>

        <div className="flex gap-1 mb-8 border-b">
          {[
            { label: "Dashboard", href: `/themes/${id}`, icon: BookOpen },
            { label: "Sources", href: `/themes/${id}/sources`, icon: Rss },
            { label: "Signals", href: `/themes/${id}/signals`, icon: Zap },
            { label: "Scenarios", href: `/themes/${id}/scenarios`, icon: Target },
            { label: "Scenario Pipeline", href: `/themes/${id}/scenario-pipeline`, icon: GitBranch },
            { label: "Briefs", href: `/themes/${id}/briefs`, icon: FileText },
          ].map(({ label, href, icon: Icon }) => (
            <Link key={href} href={href} className={`flex items-center gap-1.5 px-4 py-2 text-sm border-b-2 transition-colors ${href === `/themes/${id}/signals` ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground hover:border-primary"}`}>
              <Icon className="h-3.5 w-3.5" />{label}
            </Link>
          ))}
        </div>

        {adding && (
          <Card className="mb-6 p-4">
            <form onSubmit={handleAdd} className="space-y-3">
              <div className="space-y-1">
                <Label>Title *</Label>
                <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Signal title" autoFocus />
              </div>
              <div className="space-y-1">
                <Label>Summary</Label>
                <Textarea value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="Brief description of the signal" rows={2} />
              </div>
              <div className="grid grid-cols-3 gap-3">
                {/* Type */}
                <div className="space-y-1">
                  <LabelWithHelp tip={
                    <div className="space-y-3">
                      <p className="font-semibold">Signal types</p>
                      {TYPES.map((t) => (
                        <div key={t} className="space-y-0.5">
                          <p className="font-medium">{TYPE_INFO[t].label}</p>
                          <p className="text-muted-foreground">{TYPE_INFO[t].how}</p>
                        </div>
                      ))}
                    </div>
                  }>
                    Type
                  </LabelWithHelp>
                  <Select value={signalType} onValueChange={setSignalType}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {TYPES.map((t) => (
                        <SelectItem key={t} value={t}>{TYPE_INFO[t].label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* STEEP */}
                <div className="space-y-1">
                  <LabelWithHelp tip={
                    <div className="space-y-2">
                      <p className="font-semibold">STEEP categories</p>
                      <p className="text-muted-foreground">A foresight framework that organises signals by the domain of change they belong to.</p>
                      {STEEP.map((t) => (
                        <div key={t} className="space-y-0.5">
                          <p className="font-medium">{STEEP_INFO[t].label}</p>
                          <p className="text-muted-foreground">{STEEP_INFO[t].description}</p>
                        </div>
                      ))}
                    </div>
                  }>
                    STEEP
                  </LabelWithHelp>
                  <Select value={steep} onValueChange={setSteep}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {STEEP.map((t) => (
                        <SelectItem key={t} value={t}>{STEEP_INFO[t].label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Horizon */}
                <div className="space-y-1">
                  <LabelWithHelp tip={
                    <div className="space-y-2">
                      <p className="font-semibold">Three Horizons</p>
                      <p className="text-muted-foreground">A foresight framework describing where a signal sits in the timeline of change.</p>
                      {HORIZONS.map((t) => (
                        <div key={t} className="space-y-0.5">
                          <p className="font-medium">{HORIZON_INFO[t].label}</p>
                          <p className="text-muted-foreground">{HORIZON_INFO[t].description}</p>
                        </div>
                      ))}
                    </div>
                  }>
                    Horizon
                  </LabelWithHelp>
                  <Select value={horizon} onValueChange={setHorizon}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {HORIZONS.map((t) => (
                        <SelectItem key={t} value={t}>{HORIZON_INFO[t].label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex gap-2">
                <Button type="submit">Add Signal</Button>
                <Button type="button" variant="ghost" onClick={() => setAdding(false)}>Cancel</Button>
              </div>
            </form>
          </Card>
        )}

        {/* Filter / sort bar */}
        {signals.length > 0 && (
          <div className="mb-4 space-y-2">
            <div className="flex flex-wrap gap-2 items-center">
              <input
                type="search"
                placeholder="Search signals…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8 rounded-md border border-input bg-transparent px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring w-48"
              />

              <FilterSelect value={filterType} onChange={setFilterType}>
                <option value="">All types</option>
                {TYPES.map((t) => <option key={t} value={t}>{TYPE_INFO[t].label}</option>)}
              </FilterSelect>

              <FilterSelect value={filterSteep} onChange={setFilterSteep}>
                <option value="">All domains</option>
                {STEEP.map((t) => <option key={t} value={t}>{STEEP_INFO[t].label}</option>)}
              </FilterSelect>

              <FilterSelect value={filterHorizon} onChange={setFilterHorizon}>
                <option value="">All horizons</option>
                {HORIZONS.map((t) => <option key={t} value={t}>{t}</option>)}
              </FilterSelect>

              <FilterSelect value={filterStatus} onChange={setFilterStatus}>
                <option value="">All statuses</option>
                <option value="active">Active</option>
                <option value="archived">Archived</option>
              </FilterSelect>

              <div className="ml-auto flex items-center gap-2">
                <span className="text-xs text-muted-foreground">{displayed.length} of {signals.length}</span>
                <FilterSelect value={sortBy} onChange={setSortBy}>
                  <option value="importance_desc">Importance ↓</option>
                  <option value="importance_asc">Importance ↑</option>
                  <option value="novelty_desc">Novelty ↓</option>
                  <option value="relevance_desc">Relevance ↓</option>
                  <option value="newest">Newest first</option>
                  <option value="title_asc">Title A–Z</option>
                </FilterSelect>
              </div>
            </div>

            {/* Active filter chips */}
            {(filterType || filterSteep || filterHorizon || filterStatus !== "active" || search) && (
              <div className="flex flex-wrap gap-1.5 items-center">
                <span className="text-xs text-muted-foreground">Filters:</span>
                {filterType    && <Chip label={TYPE_INFO[filterType]?.label ?? filterType}   onRemove={() => setFilterType("")} />}
                {filterSteep   && <Chip label={STEEP_INFO[filterSteep]?.label ?? filterSteep} onRemove={() => setFilterSteep("")} />}
                {filterHorizon && <Chip label={filterHorizon}                                  onRemove={() => setFilterHorizon("")} />}
                {filterStatus !== "active" && filterStatus && <Chip label={filterStatus}       onRemove={() => setFilterStatus("active")} />}
                {search        && <Chip label={`"${search}"`}                                  onRemove={() => setSearch("")} />}
                <button onClick={() => { setFilterType(""); setFilterSteep(""); setFilterHorizon(""); setFilterStatus("active"); setSearch(""); }}
                  className="text-xs text-muted-foreground hover:text-foreground underline">clear all</button>
              </div>
            )}
          </div>
        )}

        {signals.length === 0 ? (
          <p className="text-muted-foreground text-sm">No signals yet.</p>
        ) : displayed.length === 0 ? (
          <p className="text-muted-foreground text-sm">No signals match the current filters.</p>
        ) : (
          <div className="space-y-2">
            {displayed.map((s) => (
              <Card key={s.id}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        {s.source_url ? (
                          <a href={s.source_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium hover:underline">{s.title}</a>
                        ) : (
                          <p className="text-sm font-medium">{s.title}</p>
                        )}

                        {/* Type badge */}
                        {s.signal_type && (
                          <Tooltip content={<TypeTip t={s.signal_type} />}>
                            <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium cursor-help ${TYPE_COLOR[s.signal_type] ?? "bg-muted text-muted-foreground border-border"}`}>
                              {TYPE_INFO[s.signal_type]?.label ?? s.signal_type}
                            </span>
                          </Tooltip>
                        )}

                        {/* STEEP badge */}
                        {s.steep_category && (
                          <Tooltip content={<SteepTip t={s.steep_category} />}>
                            <Badge variant="secondary" className="text-xs cursor-help">{STEEP_INFO[s.steep_category]?.label ?? s.steep_category}</Badge>
                          </Tooltip>
                        )}

                        {/* Horizon badge */}
                        {s.horizon && (
                          <Tooltip content={<HorizonTip t={s.horizon} />}>
                            <Badge variant="outline" className="text-xs cursor-help">{s.horizon}</Badge>
                          </Tooltip>
                        )}

                        {s.cluster_id && !s.cluster_id.startsWith("solo_") && (
                          <Tooltip content="This signal has been grouped with others that share similar vocabulary and were published within the same time window. Clusters become Trends in the scenario pipeline.">
                            <Badge variant="outline" className="text-xs font-mono text-purple-600 border-purple-200 cursor-help">cluster</Badge>
                          </Tooltip>
                        )}

                        <button
                          onClick={() => handleToggleExplanation(s.id)}
                          className="text-xs text-muted-foreground hover:text-foreground font-mono"
                          title="Show score breakdown"
                        >
                          score {s.importance_score.toFixed(2)}
                        </button>
                      </div>

                      <p className="text-xs text-muted-foreground/70 mt-0.5 italic">{whySelected(s)}</p>
                      {s.summary && <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{s.summary}</p>}

                      {expandedExplanation === s.id && explanations[s.id] && (
                        <div className="mt-2 p-3 bg-muted/50 rounded text-xs space-y-1.5">
                          <p className="font-semibold text-muted-foreground mb-1">Score breakdown</p>
                          {Object.entries(explanations[s.id].score_breakdown.weighted_contributions).map(([key, val]) => {
                            const weight = explanations[s.id].score_breakdown.weights[key as keyof typeof explanations[string]["score_breakdown"]["weights"]];
                            const raw = explanations[s.id].score_breakdown[key as keyof typeof explanations[string]["score_breakdown"]] as number;
                            return (
                              <div key={key} className="flex items-center gap-2">
                                <Tooltip side="right" content={
                                  <div className="space-y-1">
                                    <p className="font-semibold capitalize">{key.replace(/_/g, " ")}</p>
                                    <p>Raw value: <span className="font-mono">{typeof raw === "number" ? raw.toFixed(3) : "–"}</span></p>
                                    <p>Weight: <span className="font-mono">{typeof weight === "number" ? (weight * 100).toFixed(0) : "–"}%</span></p>
                                    <p>Contribution: <span className="font-mono">{(val as number).toFixed(3)}</span></p>
                                  </div>
                                }>
                                  <span className="w-24 text-muted-foreground capitalize cursor-help hover:text-foreground">{key.replace(/_/g, " ")}</span>
                                </Tooltip>
                                <div className="flex-1 bg-border rounded-full h-1.5">
                                  <div className="bg-primary h-1.5 rounded-full" style={{ width: `${Math.round((val as number) * 100)}%` }} />
                                </div>
                                <span className="w-8 text-right font-mono">{(val as number).toFixed(2)}</span>
                              </div>
                            );
                          })}
                          <p className="text-muted-foreground pt-1 border-t mt-1">
                            Final score: <span className="font-mono font-semibold text-foreground">{explanations[s.id].score_breakdown.final_score.toFixed(3)}</span>
                          </p>
                        </div>
                      )}

                      {linkingSignalId === s.id && (
                        <form onSubmit={handleLinkToScenario} className="mt-3 flex items-end gap-2">
                          <div className="space-y-1">
                            <Label className="text-xs">Scenario</Label>
                            <Select value={linkScenarioId} onValueChange={setLinkScenarioId}>
                              <SelectTrigger className="h-8 text-xs w-44"><SelectValue placeholder="Pick scenario..." /></SelectTrigger>
                              <SelectContent>
                                {scenarios.map((sc) => <SelectItem key={sc.id} value={sc.id}>{sc.name}</SelectItem>)}
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs">Relationship</Label>
                            <Select value={linkRelType} onValueChange={setLinkRelType}>
                              <SelectTrigger className="h-8 text-xs w-32"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="supports">Supports</SelectItem>
                                <SelectItem value="weakens">Weakens</SelectItem>
                                <SelectItem value="neutral">Neutral</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <Button type="submit" size="sm" className="h-8" disabled={!linkScenarioId}>Link</Button>
                          <Button type="button" size="sm" variant="ghost" className="h-8" onClick={() => setLinkingSignalId(null)}>
                            <X className="h-3.5 w-3.5" />
                          </Button>
                        </form>
                      )}
                    </div>

                    <div className="flex gap-1 shrink-0">
                      {scenarios.length > 0 && s.status === "active" && linkingSignalId !== s.id && (
                        <Button size="sm" variant="ghost" className="text-muted-foreground"
                          onClick={() => { setLinkingSignalId(s.id); setLinkScenarioId(""); }}>
                          <Link2 className="h-3.5 w-3.5" />
                        </Button>
                      )}
                      {s.status === "active" && (
                        <Button size="sm" variant="ghost" className="text-muted-foreground" onClick={() => handleArchive(s)}>
                          Archive
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </TooltipProvider>
  );
}
