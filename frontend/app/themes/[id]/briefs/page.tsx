"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { FileText, BookOpen, Rss, Zap, Target, GitBranch, RefreshCw } from "lucide-react";
import { api, type Brief } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function BriefsPage() {
  const { id } = useParams<{ id: string }>();
  const [briefs, setBriefs] = useState<Brief[]>([]);
  const [selected, setSelected] = useState<Brief | null>(null);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    api.briefs.list(id).then(setBriefs);
  }, [id]);

  async function handleGenerate() {
    setGenerating(true);
    try {
      const brief = await api.briefs.generate(id, { generation_mode: "on_demand" });
      setBriefs((prev) => [brief, ...prev]);
      // Poll for completion
      const poll = setInterval(async () => {
        const updated = await api.briefs.get(brief.id);
        setBriefs((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
        if (updated.status !== "generating") {
          clearInterval(poll);
          setSelected(updated);
          setGenerating(false);
        }
      }, 2000);
    } catch (e) {
      alert(String(e));
      setGenerating(false);
    }
  }

  return (
    <div className="max-w-5xl mx-auto p-8">
      <div className="mb-2">
        <Link href="/themes" className="text-sm text-muted-foreground hover:underline">← Themes</Link>
      </div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Strategic Briefs</h1>
        <Button onClick={handleGenerate} disabled={generating}>
          <RefreshCw className={`h-4 w-4 ${generating ? "animate-spin" : ""}`} />
          {generating ? "Generating..." : "Generate Brief"}
        </Button>
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
          <Link key={href} href={href} className={`flex items-center gap-1.5 px-4 py-2 text-sm border-b-2 transition-colors ${href === `/themes/${id}/briefs` ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground hover:border-primary"}`}>
            <Icon className="h-3.5 w-3.5" />{label}
          </Link>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-1 space-y-2">
          {briefs.length === 0 ? (
            <p className="text-muted-foreground text-sm">No briefs yet. Generate one.</p>
          ) : (
            briefs.map((b) => (
              <Card
                key={b.id}
                className={`cursor-pointer transition-colors ${selected?.id === b.id ? "border-primary" : "hover:border-primary/50"}`}
                onClick={() => setSelected(b)}
              >
                <CardHeader className="pb-1 pt-3 px-4">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-xs font-medium">
                      {b.generation_mode === "weekly" ? "Weekly" : "On-demand"}
                    </CardTitle>
                    <Badge variant={b.status === "completed" ? "default" : b.status === "generating" ? "secondary" : "destructive"} className="text-xs">
                      {b.status}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="px-4 pb-3">
                  <p className="text-xs text-muted-foreground">{new Date(b.created_at).toLocaleString()}</p>
                </CardContent>
              </Card>
            ))
          )}
        </div>

        <div className="col-span-2">
          {selected ? (
            <Card className="h-full">
              <CardContent className="p-6">
                {selected.status === "generating" ? (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span className="text-sm">Generating brief...</span>
                  </div>
                ) : selected.rendered_text ? (
                  <div className="prose prose-sm max-w-none">
                    <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{selected.rendered_text}</pre>
                  </div>
                ) : (
                  <p className="text-muted-foreground text-sm">No content available.</p>
                )}
              </CardContent>
            </Card>
          ) : (
            <div className="flex items-center justify-center h-48 text-muted-foreground text-sm border rounded-xl">
              Select a brief to view
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
