"""
Configuration for the prompt evaluation system.

Writer models (web_evaluate.py — all use openrouter:web_search):
    deepseek/deepseek-v3.2
    google/gemini-3-flash-preview
    minimax/minimax-m2.7

Judge model (fixed for consistent scoring):
    deepseek/deepseek-v3.2
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (one level up from this file)
load_dotenv(Path(__file__).parent.parent / ".env")

WRITER_MODELS = [
    "deepseek/deepseek-v3.2",
    "google/gemini-3-flash-preview",
    "minimax/minimax-m2.7",
]
JUDGE_MODEL = "deepseek/deepseek-v3.2"


@dataclass
class EvalConfig:
    openrouter_api_key: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_API_KEY", "")
    )

    # Only used when calling ArticleEvaluator directly; web_evaluate.py sets this to JUDGE_MODEL
    evaluator_model: str = field(
        default_factory=lambda: os.getenv("EVAL_EVALUATOR_MODEL", JUDGE_MODEL)
    )

    evaluator_max_tokens: int = 1024

    results_dir: str = field(
        default_factory=lambda: os.path.join(os.path.dirname(__file__), "results")
    )
