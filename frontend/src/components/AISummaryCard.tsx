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
      <div className="mb-3 text-sm font-medium text-gray-700">AI Summary</div>

      {loading && <div className="text-sm text-gray-400">Generating summary...</div>}
      {error && <div className="text-sm text-red-600">{error}</div>}

      {!loading && !error && summary && (
        <div className="space-y-4">
          <div className="border-l-2 border-blue-500 pl-3">
            <div className="text-xs font-semibold tracking-wide text-blue-600 uppercase">
              What Happened
            </div>
            <p className="mt-1 text-sm leading-relaxed text-gray-700">{summary.summary}</p>
          </div>

          <div className="border-l-2 border-amber-500 pl-3">
            <div className="text-xs font-semibold tracking-wide text-amber-600 uppercase">
              What's Next
            </div>
            <p className="mt-1 text-sm leading-relaxed text-gray-700">{summary.next_steps}</p>
          </div>
        </div>
      )}
    </div>
  );
}
