import type { NewsItem } from "../api/client";
import { formatRelativeTime } from "../utils/format";

interface Props {
  items: NewsItem[];
  emptyMessage: string;
  showTicker?: boolean;
}

export function NewsList({ items, emptyMessage, showTicker = false }: Props) {
  if (items.length === 0) {
    return <div className="text-sm text-gray-400">{emptyMessage}</div>;
  }

  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.id} className="rounded-lg border border-gray-100 px-3 py-2">
          <a
            href={item.url ?? undefined}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-start gap-3"
          >
            <div className="min-w-0 flex-1">
              <div className="line-clamp-2 text-sm font-semibold text-gray-800 hover:text-blue-600">
                {item.headline}
              </div>
              <div className="mt-1 text-xs text-gray-400">
                {showTicker && <span className="font-medium text-gray-500">{item.ticker}</span>}
                {showTicker && item.source && " · "}
                {item.source}
                {item.published_at && ` · ${formatRelativeTime(item.published_at)}`}
              </div>
            </div>
            {item.thumbnail_url && (
              <img
                src={item.thumbnail_url}
                alt=""
                className="h-14 w-14 shrink-0 rounded-md object-cover"
              />
            )}
          </a>
        </li>
      ))}
    </ul>
  );
}
