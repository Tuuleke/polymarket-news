"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Article, Market, MarketSnapshot } from "@/types";
import { api } from "@/lib/api";

interface Props {
  market: Market;
}

export function MarketCard({ market }: Props) {
  const router = useRouter();
  const [loadingExplain, setLoadingExplain] = useState(false);
  const [loadingUpdates, setLoadingUpdates] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatesMsg, setUpdatesMsg] = useState<string | null>(null);
  const [hovered, setHovered] = useState(false);

  const explanation = market.articles.find((a) => a.article_type === "explanation");
  const updates = market.articles
    .filter((a) => a.article_type === "update")
    .sort((a, b) => (b.snapshot_date ?? "").localeCompare(a.snapshot_date ?? ""));

  const prob = market.probability * 100;
  const probHex = prob >= 60 ? "#22c55e" : prob < 40 ? "#ef4444" : "#f59e0b";
  const probTrack = prob >= 60
    ? "rgba(34,197,94,0.20)"
    : prob < 40
    ? "rgba(239,68,68,0.20)"
    : "rgba(245,158,11,0.20)";

  const volumeStr = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumSignificantDigits: 3,
  }).format(market.volume);

  // ── End date countdown ──
  const endDateStr = (() => {
    if (!market.end_date) return null;
    const end = new Date(market.end_date);
    const now = new Date();
    const diffMs = end.getTime() - now.getTime();
    const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays < 0) return { label: "Resolved", color: "var(--text-muted)", weight: 400 };
    if (diffDays <= 7) return { label: `Ends in ${diffDays}d`, color: "#ef4444", weight: 600 };
    if (diffDays <= 30) return { label: `Ends in ${diffDays}d`, color: "#f59e0b", weight: 500 };
    return {
      label: `Ends ${end.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`,
      color: "var(--text-muted)",
      weight: 400,
    };
  })();

  // ── 7-day delta ──
  const sevenDayDelta = (() => {
    if (!market.snapshots || market.snapshots.length < 2) return null;
    const sorted = [...market.snapshots].sort((a, b) => a.date.localeCompare(b.date));
    const now = new Date();
    const target = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    // find snapshot closest to 7 days ago
    let best: MarketSnapshot | null = null;
    let bestDiff = Infinity;
    for (const s of sorted) {
      const d = new Date(s.date);
      const diff = Math.abs(d.getTime() - target.getTime());
      if (diff < bestDiff && d <= now) { bestDiff = diff; best = s; }
    }
    if (!best) return null;
    const latest = sorted[sorted.length - 1];
    if (latest.date === best.date) return null;
    const delta = (latest.probability - best.probability) * 100;
    if (Math.abs(delta) < 0.5) return null;
    return delta;
  })();

  async function handleExplain() {
    setLoadingExplain(true);
    setError(null);
    try {
      await api.markets.generateExplanation(market.id);
      router.refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to generate explanation");
    } finally {
      setLoadingExplain(false);
    }
  }

  async function handleUpdates() {
    setLoadingUpdates(true);
    setError(null);
    setUpdatesMsg(null);
    try {
      const result = await api.markets.generateUpdates(market.id);
      if (result.generated > 0) {
        router.refresh();
        setUpdatesMsg(`${result.generated} update article${result.generated !== 1 ? "s" : ""} generated`);
      } else {
        setUpdatesMsg("No significant moves found (>10pp)");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to generate updates");
    } finally {
      setLoadingUpdates(false);
    }
  }

  return (
    <article
      className="glass-card"
      style={{
        borderRadius: 20,
        overflow: "hidden",
        transition: "box-shadow 200ms ease-out, transform 200ms ease-out",
        transform: hovered ? "translateY(-2px)" : "translateY(0)",
        boxShadow: hovered ? "var(--shadow-card-hover)" : "var(--shadow-card)",
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* ── Card header ── */}
      <div style={{ padding: "22px 24px 16px" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 style={{
              fontSize: 15,
              fontWeight: 600,
              lineHeight: 1.45,
              letterSpacing: "-0.02em",
              color: "var(--text-primary)",
              margin: 0,
            }}>
              {market.question}
            </h2>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 5, flexWrap: "wrap" }}>
              <p style={{ fontSize: 12, color: "var(--text-muted)", margin: 0, letterSpacing: "-0.01em" }}>
                Vol {volumeStr}
              </p>
              {endDateStr && (
                <p style={{
                  fontSize: 12,
                  color: endDateStr.color,
                  fontWeight: endDateStr.weight,
                  margin: 0,
                  letterSpacing: "-0.01em",
                }}>
                  · {endDateStr.label}
                </p>
              )}
            </div>
          </div>

          <div style={{
            flexShrink: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-end",
          }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
              <span style={{
                fontSize: "2.4rem",
                fontWeight: 700,
                letterSpacing: "-0.04em",
                color: probHex,
                lineHeight: 1,
              }}>
                {prob.toFixed(1)}%
              </span>
              {sevenDayDelta !== null && (
                <span style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: sevenDayDelta > 0 ? "#22c55e" : "#ef4444",
                  letterSpacing: "-0.01em",
                  lineHeight: 1,
                  alignSelf: "flex-end",
                  marginBottom: 2,
                }}>
                  {sevenDayDelta > 0 ? "+" : ""}{sevenDayDelta.toFixed(1)}pp
                </span>
              )}
            </div>
            <span style={{
              fontSize: 10,
              color: "var(--text-muted)",
              marginTop: 3,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}>
              probability
            </span>
          </div>
        </div>

        {/* Probability bar */}
        <div style={{
          marginTop: 14,
          height: 5,
          borderRadius: 3,
          background: probTrack,
          overflow: "hidden",
        }}>
          <div style={{
            height: "100%",
            width: `${prob}%`,
            background: probHex,
            borderRadius: 3,
            transition: "width 600ms ease-out",
          }} />
        </div>

        {/* Sparkline */}
        {market.snapshots && market.snapshots.length >= 1 && (
          <div style={{ marginTop: 10 }}>
            <Sparkline snapshots={market.snapshots} color={probHex} currentProbability={market.probability} />
          </div>
        )}
      </div>

      {/* ── Feedback messages ── */}
      {(error || updatesMsg) && (
        <div style={{ padding: "0 24px 12px" }}>
          {error && (
            <div style={{
              padding: "10px 14px",
              borderRadius: 12,
              background: "var(--bg-error)",
              color: "var(--color-red)",
              fontSize: 13,
              fontWeight: 500,
              border: "1px solid rgba(239,68,68,0.20)",
            }}>
              {error}
            </div>
          )}
          {updatesMsg && (
            <div style={{
              padding: "10px 14px",
              borderRadius: 12,
              background: "var(--bg-success)",
              color: "var(--color-green)",
              fontSize: 13,
              fontWeight: 500,
              border: "1px solid rgba(34,197,94,0.20)",
            }}>
              {updatesMsg}
            </div>
          )}
        </div>
      )}

      {/* ── Actions ── */}
      <div style={{ padding: "0 24px 22px", display: "flex", gap: 8, flexWrap: "wrap" }}>
        <GlassButton
          onClick={handleExplain}
          disabled={loadingExplain}
          loading={loadingExplain}
          done={false}
          label={explanation ? "Re-explain" : "Explain"}
          doneLabel="Explain"
          loadingLabel="Explaining…"
          accentColor="#6366f1"
          bgColor="var(--bg-indigo)"
          borderColor="var(--border-indigo)"
        />
        <GlassButton
          onClick={handleUpdates}
          disabled={loadingUpdates}
          loading={loadingUpdates}
          done={false}
          label="Generate updates"
          doneLabel="Generate updates"
          loadingLabel="Generating…"
          accentColor="#8b5cf6"
          bgColor="var(--bg-violet)"
          borderColor="var(--border-violet)"
        />
      </div>

      {/* ── Explanation article ── */}
      {explanation && (
        <div style={{ padding: "0 16px 16px" }}>
          <ArticleBlock
            label="Explanation"
            accentColor="#6366f1"
            article={explanation}
            meta={`At ${(explanation.probability_at_generation * 100).toFixed(1)}% · ${explanation.llm_model}`}
          />
        </div>
      )}

      {/* ── Update articles ── */}
      {updates.length > 0 && (
        <div style={{ padding: "0 16px 16px" }}>
          <p style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: "var(--text-muted)",
            margin: "0 0 8px",
          }}>
            Moves · {updates.length}
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {updates.map((article) => {
              const change = article.probability_change;
              const isUp = change !== null && change > 0;
              const accentColor = change === null ? "#9aa0b8" : isUp ? "#22c55e" : "#ef4444";
              const changeStr = change !== null
                ? `${isUp ? "+" : ""}${(change * 100).toFixed(1)}pp`
                : null;
              const meta = [article.snapshot_date, changeStr].filter(Boolean).join(" · ");
              return (
                <ArticleBlock
                  key={article.id}
                  label={null}
                  accentColor={accentColor}
                  article={article}
                  meta={meta || undefined}
                />
              );
            })}
          </div>
        </div>
      )}
    </article>
  );
}

// ── Sparkline ──────────────────────────────────────────────────────────────

interface SparklineProps {
  snapshots: MarketSnapshot[];
  color: string;
  currentProbability: number;
}

function Sparkline({ snapshots, color, currentProbability }: SparklineProps) {
  const sorted = [...snapshots].sort((a, b) => a.date.localeCompare(b.date));
  if (sorted.length === 0) return null;

  // With only one historical snapshot, synthesise a second point at today's probability
  // so there's always a visible line showing at least the current level/direction.
  const today = new Date().toISOString().slice(0, 10);
  const points: { date: string; probability: number }[] =
    sorted.length === 1 && sorted[0].date !== today
      ? [...sorted, { date: today, probability: currentProbability }]
      : sorted;

  const W = 200;
  const H = 36;
  const PAD = 2; // vertical padding in px so line isn't clipped

  const probs = points.map((s) => s.probability);
  const minP = Math.min(...probs);
  const maxP = Math.max(...probs);
  const range = maxP - minP || 0.01;

  const toX = (i: number) => (i / (points.length - 1)) * W;
  const toY = (p: number) => PAD + (1 - (p - minP) / range) * (H - PAD * 2);

  const linePoints = points.map((s, i) => `${toX(i)},${toY(s.probability)}`).join(" ");

  // closed path for the filled area
  const areaD = [
    `M ${toX(0)},${H}`,
    ...points.map((s, i) => `L ${toX(i)},${toY(s.probability)}`),
    `L ${toX(points.length - 1)},${H}`,
    "Z",
  ].join(" ");

  // derive a hex color with 18% opacity for the fill
  const fillColor = color.startsWith("#")
    ? color + "2e"
    : color.replace(")", ", 0.18)").replace("rgb(", "rgba(");

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      style={{ width: "100%", height: H, display: "block" }}
      aria-hidden="true"
    >
      <path d={areaD} fill={fillColor} />
      <polyline
        points={linePoints}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ── ArticleBlock ───────────────────────────────────────────────────────────

interface ArticleBlockProps {
  label: string | null;
  accentColor: string;
  article: Article;
  meta?: string;
}

function ArticleBlock({ label, accentColor, article, meta }: ArticleBlockProps) {
  return (
    <div
      className="glass-article"
      style={{
        borderRadius: 14,
        padding: "14px 16px",
        borderTop: "1px solid var(--border-card)",
        borderRight: "1px solid var(--border-card)",
        borderBottom: "1px solid var(--border-card)",
        borderLeft: `3px solid ${accentColor}`,
      }}
    >
      {label && (
        <p style={{
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: accentColor,
          margin: "0 0 6px",
        }}>
          {label}
        </p>
      )}
      <h3 style={{
        fontSize: 13,
        fontWeight: 600,
        color: "var(--text-primary)",
        margin: 0,
        letterSpacing: "-0.01em",
        lineHeight: 1.4,
      }}>
        {article.title}
      </h3>
      <p style={{
        fontSize: 13,
        color: "var(--text-secondary)",
        lineHeight: 1.65,
        margin: "8px 0 0",
        whiteSpace: "pre-wrap",
      }}>
        {article.body}
      </p>
      {meta && (
        <p style={{
          fontSize: 11,
          color: "var(--text-muted)",
          margin: "8px 0 0",
          letterSpacing: "-0.01em",
        }}>
          {meta}
        </p>
      )}
    </div>
  );
}

// ── GlassButton ────────────────────────────────────────────────────────────

interface GlassButtonProps {
  onClick: () => void;
  disabled: boolean;
  loading: boolean;
  done: boolean;
  label: string;
  doneLabel: string;
  loadingLabel: string;
  accentColor: string;
  bgColor: string;
  borderColor: string;
}

function GlassButton({
  onClick, disabled, loading, done,
  label, doneLabel, loadingLabel,
  accentColor, bgColor, borderColor,
}: GlassButtonProps) {
  const [hovered, setHovered] = useState(false);
  const inactive = done || (disabled && !loading);
  const displayLabel = loading ? loadingLabel : done ? doneLabel : label;

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "7px 16px",
        borderRadius: 100,
        border: `1px solid ${inactive ? "var(--border-card)" : borderColor}`,
        fontSize: 13,
        fontWeight: 550,
        color: inactive ? "var(--text-muted)" : accentColor,
        background: inactive ? "transparent" : bgColor,
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "all 150ms ease-out",
        letterSpacing: "-0.01em",
        outline: "none",
        opacity: inactive ? 0.55 : 1,
        fontFamily: "inherit",
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
        transform: hovered && !disabled ? "scale(1.02)" : "scale(1)",
      }}
    >
      {loading && <span className="spinner" />}
      {displayLabel}
    </button>
  );
}
