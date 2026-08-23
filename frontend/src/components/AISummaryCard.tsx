import { useEffect, useState } from "react";
import { getSummary, type Summary } from "../api/client";

interface Props {
  target: string;
  date: string;
}

export function AISummaryCard({ target, date }: Props) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getSummary(target, date)
      .then(setSummary)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load summary"))
      .finally(() => setLoading(false));
  }, [target, date]);

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-2 text-sm font-medium text-gray-700">AI Summary</div>

      {loading && <div className="text-sm text-gray-400">Generating summary...</div>}
      {error && <div className="text-sm text-red-600">{error}</div>}

      {!loading && !error && summary && (
        <div>
          <p className="text-sm leading-relaxed text-gray-700">{summary.summary}</p>
          {summary.cited_news.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {summary.cited_news.map((item) => (
                <a
                  key={item.id}
                  href={item.url ?? undefined}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="max-w-full truncate rounded-full bg-gray-100 px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-200 hover:text-blue-600"
                  title={item.headline}
                >
                  {item.headline}
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
