interface Props {
  title: string;
  message?: string;
  className?: string;
}

export function PlaceholderCard({ title, message = "Coming soon.", className = "" }: Props) {
  return (
    <div
      className={`flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-300 bg-gray-50 p-6 text-center ${className}`}
    >
      <div className="font-medium text-gray-500">{title}</div>
      <div className="mt-1 text-sm text-gray-400">{message}</div>
    </div>
  );
}
