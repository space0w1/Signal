"""Prompt templates for AI-generated summaries, loaded from the .md files in
this directory — kept separate from services/summaries.py so wording can be
tuned by editing plain text, without touching business logic."""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent

PORTFOLIO_SUMMARY_PROMPT = (_PROMPTS_DIR / "portfolio_summary.md").read_text().strip()
STOCK_SUMMARY_PROMPT = (_PROMPTS_DIR / "stock_summary.md").read_text().strip()
