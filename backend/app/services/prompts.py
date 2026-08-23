"""Prompt templates for AI-generated summaries, kept separate from the code
that gathers the data filling them in — edit these without touching
services/summaries.py."""

PORTFOLIO_SUMMARY_PROMPT = """Portfolio snapshot as of {as_of}:
Total value: S${total_value:.2f}
Unrealized PnL: S${unrealized_pnl:.2f} ({unrealized_pnl_pct:.1f}%)
Realized PnL: S${realized_pnl:.2f}

Holdings:
{holdings_lines}

Recent news for these holdings:
{news_context}

Write a concise (2-4 sentence) market analysis of this portfolio's current state and risks, grounded in the news above. Cite the news_id of every article you actually drew on, ranked by relevance (most relevant first). If no news is relevant, return an empty list."""

STOCK_SUMMARY_PROMPT = """Stock: {ticker}, as of {as_of}
Position: {position_line}

Recent news:
{news_context}

Write a concise (2-4 sentence) market analysis of this stock's current state and risks, grounded in the news above."""
