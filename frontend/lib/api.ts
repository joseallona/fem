const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(error || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  themes: {
    list: () => request<Theme[]>("/themes"),
    get: (id: string) => request<Theme>(`/themes/${id}`),
    create: (body: ThemeCreate) => request<Theme>("/themes", { method: "POST", body: JSON.stringify(body) }),
    update: (id: string, body: Partial<ThemeCreate>) => request<Theme>(`/themes/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    delete: (id: string) => request<void>(`/themes/${id}`, { method: "DELETE" }),
    activate: (id: string) => request<Theme>(`/themes/${id}/activate`, { method: "POST" }),
    reset: (id: string) => request<void>(`/themes/${id}/reset`, { method: "POST" }),
    resetScenarios: (id: string) => request<void>(`/themes/${id}/reset-scenarios`, { method: "POST" }),
  },
  sources: {
    list: (themeId: string, status?: string) =>
      request<Source[]>(`/themes/${themeId}/sources${status ? `?status=${status}` : ""}`),
    add: (themeId: string, body: SourceCreate) =>
      request<Source>(`/themes/${themeId}/sources`, { method: "POST", body: JSON.stringify(body) }),
    update: (sourceId: string, body: SourceUpdate) =>
      request<Source>(`/sources/${sourceId}`, { method: "PATCH", body: JSON.stringify(body) }),
    delete: (sourceId: string) => request<void>(`/sources/${sourceId}`, { method: "DELETE" }),
    discover: (themeId: string, useLlm = false) =>
      request<Source[]>(`/themes/${themeId}/source-discovery?use_llm=${useLlm}`, { method: "POST" }),
    discoverAsync: (themeId: string) =>
      request<DiscoveryJobResult>(`/themes/${themeId}/source-discovery/async`, { method: "POST" }),
  },
  jobs: {
    get: (jobId: string) => request<DiscoveryJobResult>(`/jobs/${jobId}`),
  },
  signals: {
    list: (themeId: string, params?: Record<string, string>) => {
      const merged = { limit: "500", ...params };
      const qs = "?" + new URLSearchParams(merged).toString();
      return request<Signal[]>(`/themes/${themeId}/signals${qs}`);
    },
    create: (themeId: string, body: SignalCreate) =>
      request<Signal>(`/themes/${themeId}/signals`, { method: "POST", body: JSON.stringify(body) }),
    update: (signalId: string, body: SignalUpdate) =>
      request<Signal>(`/signals/${signalId}`, { method: "PATCH", body: JSON.stringify(body) }),
    feedback: (signalId: string, body: FeedbackCreate) =>
      request<Feedback>(`/signals/${signalId}/feedback`, { method: "POST", body: JSON.stringify(body) }),
    explanation: (signalId: string) => request<SignalExplanation>(`/signals/${signalId}/explanation`),
    runClustering: (themeId: string) =>
      request<Record<string, string[]>>(`/themes/${themeId}/signal-clusters`, { method: "POST" }),
    getClusters: (themeId: string) =>
      request<Record<string, Signal[]>>(`/themes/${themeId}/signal-clusters`),
  },
  scenarios: {
    list: (themeId: string) => request<Scenario[]>(`/themes/${themeId}/scenarios`),
    get: (scenarioId: string) => request<Scenario>(`/scenarios/${scenarioId}`),
    create: (themeId: string, body: ScenarioCreate) =>
      request<Scenario>(`/themes/${themeId}/scenarios`, { method: "POST", body: JSON.stringify(body) }),
    update: (scenarioId: string, body: Partial<ScenarioCreate>) =>
      request<Scenario>(`/scenarios/${scenarioId}`, { method: "PATCH", body: JSON.stringify(body) }),
    delete: (scenarioId: string) => request<void>(`/scenarios/${scenarioId}`, { method: "DELETE" }),
    getSignals: (scenarioId: string) => request<SignalLinkOut[]>(`/scenarios/${scenarioId}/signals`),
    linkSignal: (scenarioId: string, body: SignalLinkCreate) =>
      request<void>(`/scenarios/${scenarioId}/signals`, { method: "POST", body: JSON.stringify(body) }),
    unlinkSignal: (scenarioId: string, signalId: string) =>
      request<void>(`/scenarios/${scenarioId}/signals/${signalId}`, { method: "DELETE" }),
  },
  settings: {
    getLlm: () => request<LlmSettings>("/settings/llm"),
    patchLlm: (body: LlmSettingsPatch) =>
      request<LlmSettings>("/settings/llm", { method: "PATCH", body: JSON.stringify(body) }),
    testLlm: () => request<LlmTestResult>("/settings/llm/test", { method: "POST" }),
    getPipeline: () => request<PipelineSettings>("/settings/pipeline"),
    patchPipeline: (body: Partial<PipelineSettings>) =>
      request<PipelineSettings>("/settings/pipeline", { method: "PATCH", body: JSON.stringify(body) }),
  },
  sourceStats: {
    get: (themeId: string) => request<Record<string, SourceStats>>(`/themes/${themeId}/source-stats`),
  },
  briefs: {
    generate: (themeId: string, body: BriefGenerateRequest) =>
      request<Brief>(`/themes/${themeId}/briefs/generate`, { method: "POST", body: JSON.stringify(body) }),
    list: (themeId: string) => request<Brief[]>(`/themes/${themeId}/briefs`),
    latest: (themeId: string) => request<Brief>(`/themes/${themeId}/briefs/latest`),
    get: (briefId: string) => request<Brief>(`/briefs/${briefId}`),
  },
  runs: {
    list: (themeId: string) => request<Run[]>(`/themes/${themeId}/runs`),
    trigger: (themeId: string) =>
      request<Run>(`/themes/${themeId}/runs/trigger`, { method: "POST" }),
    cancel: (runId: string) =>
      request<Run>(`/runs/${runId}/cancel`, { method: "POST" }),
  },
  scenarioPipeline: {
    status: (themeId: string) =>
      request<PipelineStatus>(`/themes/${themeId}/scenario-pipeline/status`),
    trends: (themeId: string) =>
      request<Trend[]>(`/themes/${themeId}/trends`),
    drivers: (themeId: string) =>
      request<Driver[]>(`/themes/${themeId}/drivers`),
    axes: (themeId: string) =>
      request<ScenarioAxis[]>(`/themes/${themeId}/scenario-axes`),
    updateAxis: (axisId: string, body: Partial<ScenarioAxisUpdate>) =>
      request<ScenarioAxis>(`/scenario-axes/${axisId}`, { method: "PATCH", body: JSON.stringify(body) }),
    confirmAxes: (themeId: string) =>
      request<{ message: string; theme_id: string }>(`/themes/${themeId}/scenario-axes/confirm`, { method: "POST" }),
    rebuildAxes: (themeId: string) =>
      request<{ message: string; theme_id: string }>(`/themes/${themeId}/scenario-axes/rebuild`, { method: "POST" }),
    drafts: (themeId: string) =>
      request<ScenarioDraft[]>(`/themes/${themeId}/scenario-drafts`),
    updateDraft: (draftId: string, body: Partial<ScenarioDraftUpdate>) =>
      request<ScenarioDraft>(`/scenario-drafts/${draftId}`, { method: "PATCH", body: JSON.stringify(body) }),
    approveDraft: (draftId: string) =>
      request<ScenarioDraft>(`/scenario-drafts/${draftId}/approve`, { method: "POST" }),
    rejectDraft: (draftId: string) =>
      request<ScenarioDraft>(`/scenario-drafts/${draftId}/reject`, { method: "POST" }),
    approveAll: (themeId: string) =>
      request<ScenarioDraft[]>(`/themes/${themeId}/scenario-drafts/approve-all`, { method: "POST" }),
    monitoring: (themeId: string) =>
      request<MonitoringStatus>(`/themes/${themeId}/scenario-monitoring`),
    indicators: (scenarioId: string) =>
      request<ScenarioIndicator[]>(`/scenarios/${scenarioId}/indicators`),
    trendScenarioMatrix: (themeId: string) =>
      request<TrendScenarioMatrix>(`/themes/${themeId}/trend-scenario-matrix`),
  },
};

// Types
export interface Theme {
  id: string; name: string; description?: string; primary_subject?: string;
  focal_question?: string; time_horizon?: string; stakeholders_json: unknown[];
  related_subjects_json: string[]; scope_text?: string; status: string;
  created_at: string; updated_at: string;
}
export interface ThemeCreate {
  name: string; description?: string; primary_subject?: string; focal_question?: string;
  time_horizon?: string; stakeholders_json?: unknown[]; related_subjects_json?: string[];
  scope_text?: string; status?: string;
}

export interface Source {
  id: string; theme_id: string; name?: string; domain?: string; url: string;
  source_type?: string; discovery_mode: string; relevance_score: number;
  trust_score: number; crawl_frequency: string; status: string;
  last_crawled_at?: string; initial_crawl_done: boolean; created_at: string;
}
export interface SourceCreate { url: string; name?: string; source_type?: string; crawl_frequency?: string; status?: string; }
export interface SourceUpdate { name?: string; source_type?: string; crawl_frequency?: string; trust_score?: number; relevance_score?: number; status?: string; }

export interface ScoreBreakdown {
  relevance: number; novelty: number; impact: number; source_trust: number; recency: number;
  final_score: number;
  weights: { relevance: number; novelty: number; impact: number; source_trust: number; recency: number };
  weighted_contributions: { relevance: number; novelty: number; impact: number; source_trust: number; recency: number };
}
export interface SignalExplanation {
  signal_id: string; title: string; importance_score: number; score_breakdown: ScoreBreakdown;
}

export interface Signal {
  id: string; theme_id: string; source_id?: string; title: string; summary?: string;
  signal_type?: string; steep_category?: string; horizon?: string;
  importance_score: number; novelty_score: number; relevance_score: number;
  status: string; cluster_id?: string; score_breakdown?: ScoreBreakdown; created_at: string;
  source_url?: string;
}
export interface SignalCreate { title: string; summary?: string; signal_type?: string; steep_category?: string; horizon?: string; importance_score?: number; }
export interface SignalUpdate { title?: string; summary?: string; signal_type?: string; steep_category?: string; horizon?: string; importance_score?: number; status?: string; }
export interface FeedbackCreate { feedback_type: string; old_value?: string; new_value?: string; note?: string; }
export interface Feedback { id: string; signal_id: string; feedback_type: string; note?: string; created_at: string; }

export interface Scenario {
  id: string; theme_id: string; name: string; narrative?: string;
  assumptions: unknown[]; confidence_level: string; momentum_state: string;
  support_score: number; contradiction_score: number; internal_score: number;
  recent_delta: number; created_at: string; updated_at: string;
}
export interface ScenarioCreate { name: string; narrative?: string; assumptions?: unknown[]; confidence_level?: string; momentum_state?: string; }
export interface SignalLinkCreate { signal_id: string; relationship_type: string; relationship_score?: number; explanation_text?: string; user_confirmed?: boolean; }
export interface SignalLinkOut { signal_id: string; scenario_id: string; relationship_type: string; relationship_score: number; user_confirmed: boolean; explanation_text?: string; signal_title?: string; signal_type?: string; steep_category?: string; horizon?: string; importance_score?: number; source_url?: string; }

export interface DiscoveryJobResult {
  job_id: string;
  status: string; // queued | started | finished | failed | not_found
  result?: { sources_added: number };
  error?: string;
}

export interface LlmSettings {
  llm_provider: string;
  ollama_base_url: string;
  ollama_model: string;
  groq_api_key_set: boolean;
  llm_routing: string;
}
export interface LlmSettingsPatch {
  llm_provider?: string;
  ollama_base_url?: string;
  ollama_model?: string;
  groq_api_key?: string;
  llm_routing?: string;
}
export interface LlmTestResult {
  ok: boolean;
  provider: string;
  response: string;
  error?: string;
}

export interface PipelineSettings {
  scoring_w_relevance: number;
  scoring_w_novelty: number;
  scoring_w_impact: number;
  scoring_w_source_trust: number;
  scoring_w_recency: number;
  relevance_threshold: number;
  scenario_window_days: number;
  matrix_signal_gate: number;
  matrix_opposition_threshold: number;
}

export interface SourceStats {
  docs_fetched: number;
  signals_yielded: number;
  yield_rate: number;
  avg_importance: number;
}

export interface Brief {
  id: string; theme_id: string; period_start?: string; period_end?: string;
  generation_mode: string; status: string; structured_payload_json: Record<string, unknown>;
  rendered_text?: string; created_at: string;
}
export interface BriefGenerateRequest { generation_mode?: string; period_start?: string; period_end?: string; }

export interface Run {
  id: string; theme_id: string; started_at: string; completed_at?: string;
  status: string; sources_scanned: number; documents_fetched: number;
  signals_created: number; notes?: string;
  current_stage?: string;
  estimated_duration_seconds?: number;
}

// ── Scenario Pipeline ────────────────────────────────────────────────────

export interface Trend {
  id: string; theme_id: string; name: string; description?: string;
  steep_domains: string[]; signal_count: number; momentum: number;
  s_curve_position: string; horizon?: string; supporting_signal_ids: string[];
  ontology_alignment: number; cluster_id?: string;
  created_at: string; updated_at: string;
}

export interface Driver {
  id: string; theme_id: string; trend_id?: string; name: string;
  description?: string; impact_score: number; uncertainty_score: number;
  is_predetermined: boolean; steep_domain?: string; cross_impacts: Record<string, string>;
  created_at: string; updated_at: string;
}

export interface ScenarioAxis {
  id: string; theme_id: string; axis_number: number; driver_id?: string;
  driver_name?: string; pole_low?: string; pole_high?: string; rationale?: string;
  user_confirmed: boolean; confirmed_at?: string; axis_locked: boolean;
  created_at: string; updated_at: string;
}
export interface ScenarioAxisUpdate {
  driver_name?: string; pole_low?: string; pole_high?: string; rationale?: string;
  axis_locked?: boolean;
}

export interface ScenarioDraft {
  id: string; theme_id: string; quadrant: string;
  axis1_pole?: string; axis2_pole?: string;
  name: string; narrative?: string; key_characteristics: string[];
  stakeholder_implications?: string; early_indicators: string[];
  opportunities: string[]; threats: string[];
  status: string; user_notes?: string;
  approved_at?: string; approved_scenario_id?: string;
  created_at: string; updated_at: string;
}
export interface ScenarioDraftUpdate {
  name?: string; narrative?: string; key_characteristics?: string[];
  stakeholder_implications?: string; early_indicators?: string[];
  opportunities?: string[]; threats?: string[]; user_notes?: string;
}

export interface ScenarioIndicator {
  id: string; scenario_id: string; theme_id: string;
  description: string; monitoring_query?: string;
  last_signal_id?: string; last_match_at?: string;
  match_count: number; created_at: string;
}

export interface PipelineStatus {
  state: "no_data" | "trends_ready" | "axes_pending" | "axes_confirmed" | "scenarios_pending" | "monitoring";
  trend_count: number; driver_count: number;
  axes: ScenarioAxis[];
  draft_count: number; drafts_approved: number;
  live_scenario_count: number; monitoring_active: boolean;
  alerts: Array<{ level: string; scenario_id?: string; scenario_name?: string; message: string }>;
}

export interface TrendScenarioMatrix {
  trends: Array<{ id: string; name: string; signal_count: number; horizon: string; steep_domains: string[] }>;
  scenarios: Array<{ id: string; name: string; confidence_level: string; momentum_state: string; axis1_pole?: string; axis2_pole?: string; support_score?: number }>;
  cells: Array<{ trend_id: string; scenario_id: string; overlap: number; supports: number; weakens: number }>;
  axes: Array<{ axis_number: number; driver_name: string; pole_high: string; pole_low: string }>;
}

export interface MonitoringStatus {
  theme_id: string; monitoring_active: boolean;
  scenarios: Array<{
    scenario_id: string; name: string; support_score: number; relative_weight: number;
    momentum_state: string; confidence_level: string;
    indicator_count: number; indicators_matched: number; total_matches: number;
    last_match_at?: string;
  }>;
}
