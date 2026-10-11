import { lazy, Suspense, useEffect, useState } from "react";
import { Logo } from "./components/Logo";
import { PortfolioPage } from "./pages/PortfolioPage";
import { useTheme } from "./theme";

// Loaded on first visit: the globe pulls in three.js, which the portfolio page doesn't need.
const WorldPage = lazy(() => import("./pages/WorldPage"));
const SectorsPage = lazy(() => import("./pages/SectorsPage"));

type Page = "portfolio" | "world" | "sectors";

const NAV: { page: Page; label: string; hash: string }[] = [
  { page: "portfolio", label: "Portfolio", hash: "#/" },
  { page: "world", label: "World", hash: "#/world" },
  { page: "sectors", label: "Sectors", hash: "#/sectors" },
];

// Hash-based so the back button and bookmarks work without a router dependency.
function pageFromHash(): Page {
  return NAV.find((item) => item.hash === window.location.hash)?.page ?? "portfolio";
}

export default function App() {
  const [page, setPage] = useState<Page>(pageFromHash);
  const [theme, toggleTheme] = useTheme();

  useEffect(() => {
    const onHashChange = () => setPage(pageFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  return (
    <div className="mx-auto max-w-6xl p-6">
      <header className="mb-4 flex items-center justify-between">
        <h1>
          <Logo />
        </h1>
        <div className="flex items-center gap-3">
          <nav className="flex rounded-lg bg-gray-100 p-1 text-sm font-medium dark:bg-gray-800">
            {NAV.map((item) => (
              <a
                key={item.page}
                href={item.hash}
                aria-current={page === item.page ? "page" : undefined}
                className={`rounded-md px-3 py-1 ${
                  page === item.page
                    ? "bg-white shadow-sm dark:bg-gray-700 dark:text-gray-100"
                    : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                }`}
              >
                {item.label}
              </a>
            ))}
          </nav>
          <button
            onClick={toggleTheme}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-900 dark:hover:bg-gray-800"
          >
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
        </div>
      </header>

      {page === "portfolio" ? (
        <PortfolioPage />
      ) : (
        <Suspense fallback={<div className="text-sm text-gray-500 dark:text-gray-400">Loading...</div>}>
          {page === "world" ? <WorldPage theme={theme} /> : <SectorsPage theme={theme} />}
        </Suspense>
      )}
    </div>
  );
}
