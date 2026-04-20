from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_runtime_setting, settings
from app.core.database import get_db
from app.models.setting import SystemSetting

router = APIRouter(tags=["settings"])

# ── Pipeline setting defaults (mirrors service constants) ──────────────────────
_PIPELINE_DEFAULTS: dict[str, float] = {
    "scoring_w_relevance": 0.30,
    "scoring_w_novelty": 0.25,
    "scoring_w_impact": 0.20,
    "scoring_w_source_trust": 0.15,
    "scoring_w_recency": 0.10,
    "relevance_threshold": 0.07,
    "scenario_window_days": 30.0,
    "matrix_signal_gate": 10.0,
    "matrix_opposition_threshold": 0.6,
}


class LlmSettingsOut(BaseModel):
    llm_provider: str
    ollama_base_url: str
    ollama_model: str
    groq_api_key_set: bool
    llm_routing: str


class LlmSettingsPatch(BaseModel):
    llm_provider: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None
    groq_api_key: Optional[str] = None
    llm_routing: Optional[str] = None


class LlmTestResult(BaseModel):
    ok: bool
    provider: str
    response: str
    error: Optional[str] = None


def _upsert(db: Session, key: str, value: str):
    row = db.get(SystemSetting, key)
    if row:
        row.value = value
        row.updated_at = datetime.now(timezone.utc)
    else:
        db.add(SystemSetting(key=key, value=value, updated_at=datetime.now(timezone.utc)))


@router.get("/settings/llm", response_model=LlmSettingsOut)
def get_llm_settings():
    groq_key = get_runtime_setting("groq_api_key", settings.GROQ_API_KEY)
    return LlmSettingsOut(
        llm_provider=get_runtime_setting("llm_provider", settings.LLM_PROVIDER),
        ollama_base_url=get_runtime_setting("ollama_base_url", settings.OLLAMA_BASE_URL),
        ollama_model=get_runtime_setting("ollama_model", settings.OLLAMA_MODEL),
        groq_api_key_set=bool(groq_key),
        llm_routing=get_runtime_setting("llm_routing", settings.LLM_ROUTING),
    )


@router.patch("/settings/llm", response_model=LlmSettingsOut)
def patch_llm_settings(body: LlmSettingsPatch, db: Session = Depends(get_db)):
    if body.llm_provider is not None:
        _upsert(db, "llm_provider", body.llm_provider)
    if body.ollama_base_url is not None:
        _upsert(db, "ollama_base_url", body.ollama_base_url)
    if body.ollama_model is not None:
        _upsert(db, "ollama_model", body.ollama_model)
    if body.groq_api_key is not None:
        _upsert(db, "groq_api_key", body.groq_api_key)
    if body.llm_routing is not None:
        _upsert(db, "llm_routing", body.llm_routing)
    db.commit()
    return get_llm_settings()


@router.post("/settings/llm/test", response_model=LlmTestResult)
def test_llm_connection():
    from app.services.llm_gateway import _resolve_provider, call_llm
    provider = _resolve_provider("triage")
    try:
        response = call_llm("Reply with the single word OK.", job_type="triage")
        return LlmTestResult(ok=True, provider=provider, response=response[:200])
    except Exception as e:
        return LlmTestResult(ok=False, provider=provider, response="", error=str(e))


# ── Pipeline settings ──────────────────────────────────────────────────────────

class PipelineSettingsOut(BaseModel):
    scoring_w_relevance: float
    scoring_w_novelty: float
    scoring_w_impact: float
    scoring_w_source_trust: float
    scoring_w_recency: float
    relevance_threshold: float
    scenario_window_days: int
    matrix_signal_gate: int
    matrix_opposition_threshold: float


class PipelineSettingsPatch(BaseModel):
    scoring_w_relevance: Optional[float] = None
    scoring_w_novelty: Optional[float] = None
    scoring_w_impact: Optional[float] = None
    scoring_w_source_trust: Optional[float] = None
    scoring_w_recency: Optional[float] = None
    relevance_threshold: Optional[float] = None
    scenario_window_days: Optional[int] = None
    matrix_signal_gate: Optional[int] = None
    matrix_opposition_threshold: Optional[float] = None


def _get_pipeline_settings() -> PipelineSettingsOut:
    return PipelineSettingsOut(**{
        k: float(get_runtime_setting(k, str(v)))
        for k, v in _PIPELINE_DEFAULTS.items()
    })


@router.get("/settings/pipeline", response_model=PipelineSettingsOut)
def get_pipeline_settings():
    return _get_pipeline_settings()


@router.patch("/settings/pipeline", response_model=PipelineSettingsOut)
def patch_pipeline_settings(body: PipelineSettingsPatch, db: Session = Depends(get_db)):
    patch = body.model_dump(exclude_none=True)

    # Validate weight sum if any weights are being changed
    weight_keys = {"scoring_w_relevance", "scoring_w_novelty", "scoring_w_impact",
                   "scoring_w_source_trust", "scoring_w_recency"}
    new_weights = {k: patch[k] for k in weight_keys if k in patch}
    if new_weights:
        current = _get_pipeline_settings()
        merged = {
            "scoring_w_relevance": current.scoring_w_relevance,
            "scoring_w_novelty": current.scoring_w_novelty,
            "scoring_w_impact": current.scoring_w_impact,
            "scoring_w_source_trust": current.scoring_w_source_trust,
            "scoring_w_recency": current.scoring_w_recency,
        }
        merged.update(new_weights)
        weight_sum = round(sum(merged.values()), 6)
        if abs(weight_sum - 1.0) > 0.01:
            raise HTTPException(
                status_code=422,
                detail=f"Scoring weights must sum to 1.0 (current sum: {weight_sum:.4f}). "
                       "Adjust the other weights to compensate."
            )

    for key, value in patch.items():
        _upsert(db, key, str(value))
    db.commit()
    return _get_pipeline_settings()
