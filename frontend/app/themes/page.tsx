"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Plus, ArrowRight, CheckCircle, XCircle, Loader2, Search } from "lucide-react";
import { api, type Theme, type DiscoveryJobResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";

type DiscoveryState =
  | { phase: "idle" }
  | { phase: "running"; jobId: string }
  | { phase: "done"; sourcesAdded: number; themeId: string }
  | { phase: "failed"; error: string };

export default function ThemesPage() {
  const [themes, setThemes] = useState<Theme[]>([]);
  const [creatingTheme, setCreatingTheme] = useState(false);
  const [themeName, setThemeName] = useState("");
  const [themeSubject, setThemeSubject] = useState("");
  const [themeFQ, setThemeFQ] = useState("");
  const [themeHorizon, setThemeHorizon] = useState("");
  const [newTheme, setNewTheme] = useState<Theme | null>(null);
  const [discovery, setDiscovery] = useState<DiscoveryState>({ phase: "idle" });
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    api.themes.list().then(setThemes).catch(console.error);
  }, []);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  async function handleCreateTheme(e: React.FormEvent) {
    e.preventDefault();
    if (!themeName.trim()) return;
    const theme = await api.themes.create({
      name: themeName,
      primary_subject: themeSubject,
      focal_question: themeFQ,
      time_horizon: themeHorizon,
      status: "draft",
    });
    setThemes((prev) => [...prev, theme]);
    setNewTheme(theme);
    setThemeName(""); setThemeSubject(""); setThemeFQ(""); setThemeHorizon("");
  }

  async function handleRunDiscovery() {
    if (!newTheme) return;
    const job: DiscoveryJobResult = await api.sources.discoverAsync(newTheme.id);
    setDiscovery({ phase: "running", jobId: job.job_id });
    pollRef.current = setInterval(async () => {
      const status = await api.jobs.get(job.job_id);
      if (status.status === "finished") {
        clearInterval(pollRef.current!);
        setDiscovery({ phase: "done", sourcesAdded: status.result?.sources_added ?? 0, themeId: newTheme.id });
      } else if (status.status === "failed" || status.status === "not_found") {
        clearInterval(pollRef.current!);
        setDiscovery({ phase: "failed", error: status.error ?? "Discovery failed" });
      }
    }, 3000);
  }

  function handleClose() {
    if (pollRef.current) clearInterval(pollRef.current);
    setCreatingTheme(false);
    setNewTheme(null);
    setDiscovery({ phase: "idle" });
  }

  return (
    <div className="max-w-4xl mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">Themes</h1>
          <p className="text-muted-foreground text-sm mt-1">Strategic monitoring workspaces</p>
        </div>
        <Button onClick={() => setCreatingTheme(true)}>
          <Plus className="h-4 w-4" /> New Theme
        </Button>
      </div>

      {creatingTheme && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>{newTheme ? "Theme Created" : "New Theme"}</CardTitle>
            <CardDescription>
              {newTheme
                ? `"${newTheme.name}" is ready. Discover sources to start monitoring.`
                : "Define the strategic lens for this monitoring workspace"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!newTheme ? (
              <form onSubmit={handleCreateTheme} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <Label>Theme Name *</Label>
                    <Input value={themeName} onChange={(e) => setThemeName(e.target.value)} placeholder="e.g. Longevity" autoFocus />
                  </div>
                  <div className="space-y-1">
                    <Label>Primary Subject</Label>
                    <Input value={themeSubject} onChange={(e) => setThemeSubject(e.target.value)} placeholder="e.g. Human longevity" />
                  </div>
                </div>
                <div className="space-y-1">
                  <Label>Focal Question</Label>
                  <Textarea value={themeFQ} onChange={(e) => setThemeFQ(e.target.value)} placeholder="e.g. How might advances in longevity reshape consumer behavior over the next 15 years?" rows={2} />
                </div>
                <div className="space-y-1">
                  <Label>Time Horizon</Label>
                  <Input value={themeHorizon} onChange={(e) => setThemeHorizon(e.target.value)} placeholder="e.g. 15 years" />
                </div>
                <div className="flex gap-2">
                  <Button type="submit">Create Theme</Button>
                  <Button type="button" variant="ghost" onClick={handleClose}>Cancel</Button>
                </div>
              </form>
            ) : (
              <div className="space-y-4">
                <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <Search className="h-4 w-4 text-muted-foreground" />
                    <p className="text-sm font-medium">Source Discovery</p>
                    <Badge variant="outline" className="text-xs">optional</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Automatically find relevant sources for this theme. New sources will be added as pending for your review.
                  </p>

                  {discovery.phase === "idle" && (
                    <Button size="sm" onClick={handleRunDiscovery}>
                      <Search className="h-3.5 w-3.5" /> Run Discovery
                    </Button>
                  )}
                  {discovery.phase === "running" && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Searching for sources…
                    </div>
                  )}
                  {discovery.phase === "done" && (
                    <div className="flex items-center gap-2 text-sm text-green-700">
                      <CheckCircle className="h-4 w-4" />
                      {discovery.sourcesAdded} source{discovery.sourcesAdded !== 1 ? "s" : ""} found —{" "}
                      <Link href={`/themes/${discovery.themeId}/sources`} className="underline hover:no-underline">
                        review in Sources tab
                      </Link>
                    </div>
                  )}
                  {discovery.phase === "failed" && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-sm text-red-600">
                        <XCircle className="h-4 w-4" />
                        {discovery.error}
                      </div>
                      <Button size="sm" variant="outline" onClick={() => setDiscovery({ phase: "idle" })}>
                        Retry
                      </Button>
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between">
                  <Link href={`/themes/${newTheme.id}`}>
                    <Button size="sm" variant="outline">
                      Open Theme <ArrowRight className="h-3.5 w-3.5" />
                    </Button>
                  </Link>
                  <button onClick={handleClose} className="text-xs text-muted-foreground hover:underline">
                    {discovery.phase === "done" ? "Close" : "Skip"}
                  </button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {themes.length === 0 ? (
        <p className="text-muted-foreground text-sm">No themes yet. Create one to start monitoring.</p>
      ) : (
        <div className="grid gap-3">
          {themes.map((t) => (
            <Link key={t.id} href={`/themes/${t.id}`}>
              <Card className="hover:border-primary/50 transition-colors cursor-pointer">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">{t.name}</CardTitle>
                    <div className="flex items-center gap-2">
                      <Badge variant={t.status === "active" ? "default" : "secondary"}>{t.status}</Badge>
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                    </div>
                  </div>
                  {t.focal_question && <CardDescription className="line-clamp-2">{t.focal_question}</CardDescription>}
                </CardHeader>
                {t.time_horizon && (
                  <CardContent className="pt-0">
                    <span className="text-xs text-muted-foreground">Horizon: {t.time_horizon}</span>
                  </CardContent>
                )}
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
