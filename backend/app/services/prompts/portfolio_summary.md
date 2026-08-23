Portfolio snapshot as of {as_of}:
Total value: S${total_value:.2f}
Unrealized PnL: S${unrealized_pnl:.2f} ({unrealized_pnl_pct:.1f}%)
Realized PnL: S${realized_pnl:.2f}

Holdings:
{holdings_lines}

Recent news for these holdings:
{news_context}

Write two short sections, each 2-3 sentences, grounded in the news above:
1. "summary": what has actually happened recently across these holdings.
2. "next_steps": risks, catalysts, or developments worth watching going forward. This is observational context, not investment advice — describe what could matter, not what to buy or sell.

Cite the news_id of every article you drew on across both sections, ranked by relevance (most relevant first). If no news is relevant, return an empty list.
