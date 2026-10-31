import { api } from "@/lib/api";
import { MarketList } from "@/components/MarketList";
import { ThemeToggle } from "@/components/ThemeToggle";

export const dynamic = "force-dynamic";

const TAGS = ["geopolitics", "finance", "culture", "tech"];

const TAG_LABELS: Record<string, string> = {
  geopolitics: "Geopolitics",
  finance: "Finance",
  culture: "Culture",
  tech: "Tech",
};

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ tag?: string }>;
}) {
  const { tag: rawTag } = await searchParams;
  const tag = TAGS.includes(rawTag ?? "") ? (rawTag as string) : TAGS[0];

  let markets: Awaited<ReturnType<typeof api.markets.list>>;
  let fetchError: string | null = null;
  try {
    markets = await api.markets.list({ category: tag });
  } catch (e) {
    markets = [];
    fetchError = e instanceof Error ? e.message : "Failed to load markets";
  }

  return (
    <div style={{ minHeight: "100dvh", backgroundColor: "var(--bg-page)" }}>
      {/* ── Header ── */}
      <header className="glass-header" style={{ position: "sticky", top: 0, zIndex: 40 }}>
        <div style={{ maxWidth: 880, margin: "0 auto", padding: "0 20px" }}>
          <div className="header-inner">
            {/* Logo */}
            <div style={{ display: "flex", alignItems: "baseline", minWidth: 0 }}>
              <span style={{
                fontSize: 15,
                fontWeight: 700,
                letterSpacing: "-0.03em",
                color: "var(--text-primary)",
                whiteSpace: "nowrap",
              }}>
                Polymarket News
              </span>
            </div>

            {/* Category pills — center column, scrollable on mobile */}
            <nav className="header-nav" style={{
              display: "flex",
              gap: 4,
              background: "var(--bg-nav)",
              borderRadius: 100,
              padding: "3px 4px",
              flexShrink: 0,
            }}>
              {TAGS.map((t) => {
                const active = t === tag;
                return (
                  <a
                    key={t}
                    href={`/?tag=${t}`}
                    style={{
                      display: "inline-block",
                      padding: "5px 14px",
                      borderRadius: 100,
                      fontSize: 12,
                      fontWeight: active ? 600 : 450,
                      color: active ? "var(--text-primary)" : "var(--text-secondary)",
                      background: active ? "var(--bg-pill-active)" : "transparent",
                      boxShadow: active ? "var(--shadow-pill)" : "none",
                      textDecoration: "none",
                      transition: "background 150ms ease-out, color 150ms ease-out, box-shadow 150ms ease-out",
                      letterSpacing: "-0.01em",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {TAG_LABELS[t]}
                  </a>
                );
              })}
            </nav>

            {/* Theme toggle — right-justified */}
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <ThemeToggle />
            </div>
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 880, margin: "0 auto", padding: "36px 20px 100px" }}>
        {/* ── Section heading ── */}
        <div style={{ marginBottom: 24 }}>
          <h1 style={{
            fontSize: 26,
            fontWeight: 700,
            letterSpacing: "-0.035em",
            color: "var(--text-primary)",
            margin: 0,
            lineHeight: 1.2,
          }}>
            {TAG_LABELS[tag]}
          </h1>
          <p style={{
            fontSize: 13,
            color: "var(--text-muted)",
            margin: "6px 0 0",
            letterSpacing: "-0.01em",
          }}>
            Most traded markets across prediction-market platforms
          </p>
        </div>

        {fetchError && (
          <div style={{
            marginBottom: 20,
            padding: "12px 16px",
            borderRadius: 14,
            background: "var(--bg-error)",
            color: "var(--color-red)",
            fontSize: 13,
            border: "1px solid rgba(239,68,68,0.20)",
          }}>
            {fetchError}
          </div>
        )}

        {markets.length === 0 ? (
          <div style={{
            textAlign: "center",
            padding: "100px 0",
            color: "var(--text-muted)",
            fontSize: 15,
          }}>
            No markets yet. They appear after the first fetch, or run <code>make seed</code> for the thesis sample markets.
          </div>
        ) : (
          <MarketList markets={markets} />
        )}
      </main>
    </div>
  );
}
