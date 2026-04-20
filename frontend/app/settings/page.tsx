"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle, XCircle, Loader2, Info } from "lucide-react";
import { api, type LlmSettings, type LlmSettingsPatch, type PipelineSettings } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type TestState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; provider: string; response: string }
  | { status: "error"; provider: string; error: string };

const WEIGHT_KEYS: Array<{ key: keyof PipelineSettings; label: string; hint: string }> = [
  { key: "scoring_w_relevance",    label: "Relevance",    hint: "How well the signal matches the theme vocabulary. Broad themes benefit from higher relevance weight." },
  { key: "scoring_w_novelty",      label: "Novelty",      hint: "LLM-assigned score for how new or surprising the signal is. Increase to surface unexpected developments." },
  { key: "scoring_w_impact",       label: "Impact",       hint: "Keyword heuristic (breakthrough, ban, crisis…). Increase to prioritise high-stakes events." },
  { key: "scoring_w_source_trust", label: "Source trust", hint: "Trust score set per source. Increase to let source quality dominate over content." },
  { key: "scoring_w_recency",      label: "Recency",      hint: "Decay from 1.0 (≤3 days) to 0.0 (30 days). Increase for fast-moving themes." },
];

function pct(v: number) { return `${Math.round(v * 100)}%`; }

export default function SettingsPage() {
  // ── LLM settings ──────────────────────────────────────────────────────────
  const [llmForm, setLlmForm] = useState<LlmSettingsPatch & { llm_provider: string }>({
    llm_provider: "ollama",
    ollama_base_url: "",
    ollama_model: "",
    groq_api_key: "",
    llm_routing: "",
  });
  const [groqKeyPlaceholder, setGroqKeyPlaceholder] = useState("");
  const [llmSaving, setLlmSaving] = useState(false);
  const [llmSaved, setLlmSaved] = useState(false);
  const [testState, setTestState] = useState<TestState>({ status: "idle" });

  // ── Pipeline settings ──────────────────────────────────────────────────────
  const [pipeline, setPipeline] = useState<PipelineSettings>({
    scoring_w_relevance: 0.30,
    scoring_w_novelty: 0.25,
    scoring_w_impact: 0.20,
    scoring_w_source_trust: 0.15,
    scoring_w_recency: 0.10,
    relevance_threshold: 0.07,
    scenario_window_days: 30,
    matrix_signal_gate: 10,
    matrix_opposition_threshold: 0.6,
  });
  const [pipelineSaving, setPipelineSaving] = useState(false);
  const [pipelineSaved, setPipelineSaved] = useState(false);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  useEffect(() => {
    api.settings.getLlm().then((s: LlmSettings) => {
      setLlmForm({
        llm_provider: s.llm_provider,
        ollama_base_url: s.ollama_base_url,
        ollama_model: s.ollama_model,
        groq_api_key: "",
        llm_routing: s.llm_routing,
      });
      setGroqKeyPlaceholder(s.groq_api_key_set ? "••••••••••••" : "");
    });
    api.settings.getPipeline().then(setPipeline);
  }, []);

  // LLM form helpers
  function setLlm(key: keyof typeof llmForm, value: string) {
    setLlmForm((prev) => ({ ...prev, [key]: value }));
    setLlmSaved(false);
  }

  async function handleLlmSave(e: React.FormEvent) {
    e.preventDefault();
    setLlmSaving(true);
    const patch: LlmSettingsPatch = {
      llm_provider: llmForm.llm_provider,
      ollama_base_url: llmForm.ollama_base_url,
      ollama_model: llmForm.ollama_model,
      llm_routing: llmForm.llm_routing,
    };
    if (llmForm.groq_api_key) patch.groq_api_key = llmForm.groq_api_key;
    await api.settings.patchLlm(patch);
    setLlmSaving(false);
    setLlmSaved(true);
  }

  async function handleTest() {
    setTestState({ status: "loading" });
    const result = await api.settings.testLlm();
    if (result.ok) {
      setTestState({ status: "ok", provider: result.provider, response: result.response });
    } else {
      setTestState({ status: "error", provider: result.provider, error: result.error ?? "Unknown error" });
    }
  }

  // Pipeline form helpers
  function setWeight(key: keyof PipelineSettings, raw: string) {
    const val = parseFloat(raw);
    if (!isNaN(val)) {
      setPipeline((prev) => ({ ...prev, [key]: parseFloat(val.toFixed(2)) }));
      setPipelineSaved(false);
      setPipelineError(null);
    }
  }

  const weightSum = WEIGHT_KEYS.reduce((acc, { key }) => acc + (pipeline[key] as number), 0);
  const weightSumOk = Math.abs(weightSum - 1.0) < 0.011;

  async function handlePipelineSave(e: React.FormEvent) {
    e.preventDefault();
    if (!weightSumOk) {
      setPipelineError(`Weights must sum to 1.0 — current sum: ${weightSum.toFixed(2)}`);
      return;
    }
    setPipelineSaving(true);
    setPipelineError(null);
    try {
      const saved = await api.settings.patchPipeline(pipeline);
      setPipeline(saved);
      setPipelineSaved(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      try { setPipelineError(JSON.parse(msg)?.detail ?? msg); } catch { setPipelineError(msg); }
    } finally {
      setPipelineSaving(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-8 space-y-8">
      <div className="mb-2">
        <Link href="/themes" className="text-sm text-muted-foreground hover:underline">← Themes</Link>
      </div>
      <h1 className="text-2xl font-bold">Settings</h1>

      {/* ── LLM Provider ─────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">LLM Provider</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLlmSave} className="space-y-5">
            <div className="space-y-1">
              <Label>Provider</Label>
              <Select value={llmForm.llm_provider} onValueChange={(v) => setLlm("llm_provider", v)}>
                <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="ollama">Ollama (local)</SelectItem>
                  <SelectItem value="groq">Groq (cloud)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {llmForm.llm_provider === "ollama" && (
              <>
                <div className="space-y-1">
                  <Label>Ollama base URL</Label>
                  <Input value={llmForm.ollama_base_url} onChange={(e) => setLlm("ollama_base_url", e.target.value)} placeholder="http://host.docker.internal:11434" />
                </div>
                <div className="space-y-1">
                  <Label>Model</Label>
                  <Input value={llmForm.ollama_model} onChange={(e) => setLlm("ollama_model", e.target.value)} placeholder="llama3.1" />
                </div>
              </>
            )}

            {llmForm.llm_provider === "groq" && (
              <div className="space-y-1">
                <Label>Groq API key</Label>
                <Input type="password" value={llmForm.groq_api_key} onChange={(e) => setLlm("groq_api_key", e.target.value)} placeholder={groqKeyPlaceholder || "sk-..."} autoComplete="off" />
                {groqKeyPlaceholder && !llmForm.groq_api_key && (
                  <p className="text-xs text-muted-foreground">Key already set — leave blank to keep current.</p>
                )}
              </div>
            )}

            <div className="space-y-1">
              <Label>Per-job routing overrides <span className="text-xs text-muted-foreground">(optional)</span></Label>
              <Input value={llmForm.llm_routing} onChange={(e) => setLlm("llm_routing", e.target.value)} placeholder="brief:groq,extraction:ollama" />
              <p className="text-xs text-muted-foreground">Comma-separated job:provider pairs. Jobs: triage, extraction, classification, summary, brief.</p>
            </div>

            <div className="flex items-center gap-3 pt-2">
              <Button type="submit" disabled={llmSaving}>
                {llmSaving ? <><Loader2 className="h-4 w-4 animate-spin" /> Saving…</> : "Save"}
              </Button>
              {llmSaved && <span className="text-sm text-green-600 flex items-center gap-1"><CheckCircle className="h-4 w-4" /> Saved</span>}
            </div>
          </form>

          <div className="mt-6 pt-5 border-t space-y-3">
            <div className="flex items-center gap-3">
              <Button variant="outline" onClick={handleTest} disabled={testState.status === "loading"}>
                {testState.status === "loading" ? <><Loader2 className="h-4 w-4 animate-spin" /> Testing…</> : "Test connection"}
              </Button>
              {testState.status === "ok" && (
                <span className="text-sm text-green-600 flex items-center gap-1"><CheckCircle className="h-4 w-4" /> {testState.provider} responded</span>
              )}
              {testState.status === "error" && (
                <span className="text-sm text-red-500 flex items-center gap-1"><XCircle className="h-4 w-4" /> {testState.provider}: {testState.error}</span>
              )}
            </div>
            {testState.status === "ok" && (
              <p className="text-xs font-mono bg-muted/50 rounded p-2 text-muted-foreground">{testState.response}</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* ── Signal Scoring Weights ────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Signal Scoring Weights</CardTitle>
          <p className="text-xs text-muted-foreground mt-0.5">
            Every signal gets an importance score (0–1) composed of five factors. Adjust how much each factor contributes.
            Weights must sum to exactly 1.0.
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handlePipelineSave} className="space-y-5">
            {WEIGHT_KEYS.map(({ key, label, hint }) => {
              const val = pipeline[key] as number;
              return (
                <div key={key} className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <Label className="text-sm">{label}</Label>
                    <span className="text-sm font-mono tabular-nums w-10 text-right">{pct(val)}</span>
                  </div>
                  <input
                    type="range"
                    min={0} max={1} step={0.05}
                    value={val}
                    onChange={(e) => setWeight(key, e.target.value)}
                    className="w-full h-1.5 accent-primary"
                  />
                  <p className="text-xs text-muted-foreground flex items-start gap-1">
                    <Info className="h-3 w-3 mt-0.5 shrink-0" />{hint}
                  </p>
                </div>
              );
            })}

            {/* Weight sum indicator */}
            <div className={`flex items-center gap-2 text-sm font-medium ${weightSumOk ? "text-green-600" : "text-amber-600"}`}>
              {weightSumOk
                ? <><CheckCircle className="h-4 w-4" /> Weights sum to 100%</>
                : <>Weights sum to {Math.round(weightSum * 100)}% — adjust to reach 100%</>
              }
            </div>

            {/* Relevance threshold */}
            <div className="pt-4 border-t space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-sm">Relevance pre-filter threshold</Label>
                <span className="text-sm font-mono tabular-nums w-14 text-right">{pipeline.relevance_threshold.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min={0} max={0.5} step={0.01}
                value={pipeline.relevance_threshold}
                onChange={(e) => { setPipeline((p) => ({ ...p, relevance_threshold: parseFloat(e.target.value) })); setPipelineSaved(false); }}
                className="w-full h-1.5 accent-primary"
              />
              <p className="text-xs text-muted-foreground flex items-start gap-1">
                <Info className="h-3 w-3 mt-0.5 shrink-0" />
                Documents scoring below this threshold are discarded before the LLM sees them. Very low (0.07) = permissive, LLM is the real filter. Higher = stricter pre-filter, fewer LLM calls but may miss edge-relevant articles.
              </p>
            </div>

            {/* Scenario window */}
            <div className="pt-4 border-t space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-sm">Scenario signal window</Label>
                <span className="text-sm font-mono tabular-nums w-14 text-right">{pipeline.scenario_window_days}d</span>
              </div>
              <input
                type="range"
                min={7} max={90} step={1}
                value={pipeline.scenario_window_days}
                onChange={(e) => { setPipeline((p) => ({ ...p, scenario_window_days: parseInt(e.target.value) })); setPipelineSaved(false); }}
                className="w-full h-1.5 accent-primary"
              />
              <p className="text-xs text-muted-foreground flex items-start gap-1">
                <Info className="h-3 w-3 mt-0.5 shrink-0" />
                Only signals created within this window contribute to scenario confidence and momentum. Shorter windows react faster to new evidence; longer windows give more stable scores.
              </p>
            </div>

            {/* Matrix signal gate */}
            <div className="pt-4 border-t space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-sm">Matrix signal gate</Label>
                <span className="text-sm font-mono tabular-nums w-14 text-right">{pipeline.matrix_signal_gate} signals</span>
              </div>
              <input
                type="range"
                min={1} max={100} step={1}
                value={pipeline.matrix_signal_gate}
                onChange={(e) => { setPipeline((p) => ({ ...p, matrix_signal_gate: parseInt(e.target.value) })); setPipelineSaved(false); }}
                className="w-full h-1.5 accent-primary"
              />
              <p className="text-xs text-muted-foreground flex items-start gap-1">
                <Info className="h-3 w-3 mt-0.5 shrink-0" />
                Minimum signal count a candidate driving force must have to be eligible as a matrix axis. Lower values allow axis selection earlier in a project; higher values require stronger evidence.
              </p>
            </div>

            {/* Matrix opposition threshold */}
            <div className="pt-4 border-t space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-sm">Pole opposition threshold</Label>
                <span className="text-sm font-mono tabular-nums w-14 text-right">{pipeline.matrix_opposition_threshold.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min={0.3} max={0.9} step={0.05}
                value={pipeline.matrix_opposition_threshold}
                onChange={(e) => { setPipeline((p) => ({ ...p, matrix_opposition_threshold: parseFloat(e.target.value) })); setPipelineSaved(false); }}
                className="w-full h-1.5 accent-primary"
              />
              <p className="text-xs text-muted-foreground flex items-start gap-1">
                <Info className="h-3 w-3 mt-0.5 shrink-0" />
                Minimum opposition score for a driving force's pole labels to be eligible as an axis. Higher values enforce more genuine opposites; lower values are more permissive.
              </p>
            </div>

            {pipelineError && <p className="text-sm text-destructive">{pipelineError}</p>}

            <div className="flex items-center gap-3 pt-2">
              <Button type="submit" disabled={pipelineSaving || !weightSumOk}>
                {pipelineSaving ? <><Loader2 className="h-4 w-4 animate-spin" /> Saving…</> : "Save pipeline settings"}
              </Button>
              {pipelineSaved && <span className="text-sm text-green-600 flex items-center gap-1"><CheckCircle className="h-4 w-4" /> Saved</span>}
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
