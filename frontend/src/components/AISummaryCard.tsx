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
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4 shadow-sm">
      <div className="mb-3 text-sm font-medium text-gray-700 dark:text-gray-300">AI Summary</div>

      {loading && <div className="text-sm text-gray-400 dark:text-gray-500">Generating summary...</div>}
      {error && <div className="text-sm text-red-600 dark:text-red-400">{error}</div>}

      {!loading && !error && summary && (
        <div className="space-y-4">
          <div className="border-l-2 border-blue-500 pl-3">
            <div className="text-xs font-semibold tracking-wide text-blue-600 dark:text-blue-400 uppercase">
              What Happened
            </div>
            <p className="mt-1 text-sm leading-relaxed text-gray-700 dark:text-gray-300">{summary.summary}</p>
          </div>

          <div className="border-l-2 border-amber-500 pl-3">
            <div className="text-xs font-semibold tracking-wide text-amber-600 dark:text-amber-400 uppercase">
              What's Next
            </div>
            <p className="mt-1 text-sm leading-relaxed text-gray-700 dark:text-gray-300">{summary.next_steps}</p>
          </div>
        </div>
      )}
    </div>
  );
}
