"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Plus, BookOpen, Rss, Zap, Target, FileText, GitBranch, Trash2 } from "lucide-react";
import { api, type Scenario } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const MOMENTUM_ICON: Record<string, string> = { increasing: "↑", stable: "→", decreasing: "↓" };
const MOMENTUM_COLOR: Record<string, string> = { increasing: "text-green-600", stable: "text-muted-foreground", decreasing: "text-red-500" };
const CONFIDENCE_VARIANT: Record<string, "default" | "secondary" | "outline"> = { high: "default", medium: "secondary", low: "outline" };

export default function ScenariosPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [narrative, setNarrative] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    api.scenarios.list(id).then(setScenarios);
  }, [id]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    const sc = await api.scenarios.create(id, { name, narrative });
    setScenarios((prev) => [...prev, sc]);
    setName(""); setNarrative(""); setAdding(false);
  }

  async function handleDelete(e: React.MouseEvent, scenarioId: string) {
    e.stopPropagation();
    if (!confirm("Delete this scenario?")) return;
    setDeletingId(scenarioId);
    await api.scenarios.delete(scenarioId);
    setScenarios((prev) => prev.filter((s) => s.id !== scenarioId));
    setDeletingId(null);
  }

  return (
    <div className="max-w-5xl mx-auto p-8">
      <div className="mb-2">
        <Link href="/themes" className="text-sm text-muted-foreground hover:underline">← Themes</Link>
      </div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Scenarios</h1>
        <Button onClick={() => setAdding(true)}><Plus className="h-4 w-4" /> New Scenario</Button>
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
          <Link key={href} href={href} className={`flex items-center gap-1.5 px-4 py-2 text-sm border-b-2 transition-colors ${href === `/themes/${id}/scenarios` ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground hover:border-primary"}`}>
            <Icon className="h-3.5 w-3.5" />{label}
          </Link>
        ))}
      </div>

      {adding && (
        <Card className="mb-6 p-4">
          <form onSubmit={handleAdd} className="space-y-3">
            <div className="space-y-1">
              <Label>Scenario Name *</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Longevity as elite health privilege" autoFocus />
            </div>
            <div className="space-y-1">
              <Label>Narrative</Label>
              <Textarea value={narrative} onChange={(e) => setNarrative(e.target.value)} placeholder="Describe this possible future..." rows={3} />
            </div>
            <div className="flex gap-2">
              <Button type="submit">Create</Button>
              <Button type="button" variant="ghost" onClick={() => setAdding(false)}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      {scenarios.length === 0 ? (
        <p className="text-muted-foreground text-sm">No scenarios yet. Define the possible futures you want to track.</p>
      ) : (
        <div className="grid gap-3">
          {scenarios.map((sc) => (
            <Card
              key={sc.id}
              className="cursor-pointer hover:border-primary/50 transition-colors"
              onClick={() => router.push(`/themes/${id}/scenarios/${sc.id}`)}
            >
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{sc.name}</CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge variant={CONFIDENCE_VARIANT[sc.confidence_level] ?? "outline"}>
                      {sc.confidence_level}
                    </Badge>
                    <span className={`text-lg font-bold ${MOMENTUM_COLOR[sc.momentum_state]}`} title={sc.momentum_state}>
                      {MOMENTUM_ICON[sc.momentum_state] ?? "→"}
                    </span>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7 text-muted-foreground hover:text-destructive"
                      disabled={deletingId === sc.id}
                      onClick={(e) => handleDelete(e, sc.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              {sc.narrative && (
                <CardContent className="pt-0">
                  <p className="text-sm text-muted-foreground line-clamp-2">{sc.narrative}</p>
                  <div className="flex gap-4 mt-2 text-xs text-muted-foreground">
                    <span>Support {sc.support_score.toFixed(1)}</span>
                    <span>Contradiction {sc.contradiction_score.toFixed(1)}</span>
                    <span>Net {sc.internal_score.toFixed(1)}</span>
                  </div>
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
