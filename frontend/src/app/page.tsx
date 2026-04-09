import { api } from "@/lib/api";
import { MarketCard } from "@/components/MarketCard";

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
    <div style={{ minHeight: "100dvh", background: "var(--color-surface)" }}>
      {/* ── Top bar ── */}
      <header style={{
        background: "rgba(245,245,247,0.85)",
        backdropFilter: "saturate(180%) blur(20px)",
        WebkitBackdropFilter: "saturate(180%) blur(20px)",
        borderBottom: "1px solid var(--color-border)",
        position: "sticky",
        top: 0,
        zIndex: 40,
      }}>
        <div style={{ maxWidth: 860, margin: "0 auto", padding: "0 24px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", height: 56 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <span style={{ fontSize: 17, fontWeight: 700, letterSpacing: "-0.02em", color: "var(--color-text-primary)" }}>
                Polymarket News
              </span>
              <span style={{ fontSize: 12, color: "var(--color-text-tertiary)", fontWeight: 400 }}>
                AI-generated market analysis
              </span>
            </div>
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 860, margin: "0 auto", padding: "32px 24px 80px" }}>
        {/* ── Tab navigation ── */}
        <nav style={{
          display: "flex",
          gap: 6,
          marginBottom: 32,
          background: "rgba(0,0,0,0.04)",
          borderRadius: "var(--radius-pill)",
          padding: 4,
          width: "fit-content",
        }}>
          {TAGS.map((t) => {
            const active = t === tag;
            return (
              <a
                key={t}
                href={`/?tag=${t}`}
                style={{
                  display: "inline-block",
                  padding: "6px 18px",
                  borderRadius: "var(--radius-pill)",
                  fontSize: 13,
                  fontWeight: active ? 600 : 450,
                  color: active ? "var(--color-text-primary)" : "var(--color-text-secondary)",
                  background: active ? "var(--color-card)" : "transparent",
                  boxShadow: active ? "var(--shadow-sm)" : "none",
                  textDecoration: "none",
                  transition: "all var(--transition-fast)",
                  letterSpacing: "-0.01em",
                  whiteSpace: "nowrap",
                }}
              >
                {TAG_LABELS[t]}
              </a>
            );
          })}
        </nav>

        {/* ── Section heading ── */}
        <div style={{ marginBottom: 20 }}>
          <h1 style={{ fontSize: 28, fontWeight: 700, letterSpacing: "-0.03em", color: "var(--color-text-primary)", margin: 0 }}>
            {TAG_LABELS[tag]}
          </h1>
          <p style={{ fontSize: 14, color: "var(--color-text-secondary)", marginTop: 4 }}>
            Top markets by volume · updated every 30 minutes
          </p>
        </div>

        {fetchError && (
          <div style={{
            marginBottom: 20,
            padding: "12px 16px",
            borderRadius: "var(--radius-md)",
            background: "var(--color-danger-light)",
            color: "var(--color-danger)",
            fontSize: 13,
          }}>
            {fetchError}
          </div>
        )}

        {markets.length === 0 ? (
          <div style={{ textAlign: "center", padding: "80px 0", color: "var(--color-text-tertiary)", fontSize: 15 }}>
            No markets loaded yet — the scheduler populates them on startup.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {markets.map((market) => (
              <MarketCard key={market.id} market={market} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
