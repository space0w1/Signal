function Candle({ color }: { color: string }) {
  return (
    <svg
      viewBox="0 0 10 20"
      style={{ height: "0.95em", width: "0.42em" }}
      className="inline-block align-text-bottom"
      aria-hidden="true"
    >
      <line x1="5" y1="0" x2="5" y2="6" stroke={color} strokeWidth="1.6" />
      <rect x="1.5" y="6" width="7" height="14" rx="0.5" fill={color} />
    </svg>
  );
}

export function Logo() {
  return (
    <span className="text-xl font-semibold tracking-tight text-gray-900">
      S
      <Candle color="#16a34a" />
      gna
      <span className="text-red-600">l</span>
    </span>
  );
}
