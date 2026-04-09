"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { Article, Market } from "@/types";
import { api } from "@/lib/api";

interface Props {
  market: Market;
}

export function MarketCard({ market: initialMarket }: Props) {
  const router = useRouter();
  const [market, setMarket] = useState(initialMarket);
  const [loadingExplain, setLoadingExplain] = useState(false);
  const [loadingUpdates, setLoadingUpdates] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatesMsg, setUpdatesMsg] = useState<string | null>(null);

  useEffect(() => { setMarket(initialMarket); }, [initialMarket]);

  const explanation = market.articles.find((a) => a.article_type === "explanation");
  const updates = market.articles
    .filter((a) => a.article_type === "update")
    .sort((a, b) => (b.snapshot_date ?? "").localeCompare(a.snapshot_date ?? ""));

  const prob = market.probability * 100;
  const probColor = prob >= 60 ? "#34c759" : prob <= 40 ? "#ff3b30" : "#ff9f0a";

  async function handleExplain() {
    setLoadingExplain(true);
    setError(null);
    try {
      await api.markets.generateExplanation(market.id);
      router.refresh();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to generate explanation";
      setError(msg.includes("409") ? "Explanation already exists" : msg);
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
    <article style={{
      background: "var(--color-card)",
      borderRadius: "var(--radius-lg)",
      boxShadow: "var(--shadow-md)",
      border: "1px solid var(--color-border)",
      overflow: "hidden",
      transition: "box-shadow var(--transition-normal), transform var(--transition-normal)",
    }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.boxShadow = "var(--shadow-lg)";
        (e.currentTarget as HTMLElement).style.transform = "translateY(-1px)";
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.boxShadow = "var(--shadow-md)";
        (e.currentTarget as HTMLElement).style.transform = "translateY(0)";
      }}
    >
      {/* ── Card header ── */}
      <div style={{ padding: "20px 24px 16px" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 style={{
              fontSize: 15,
              fontWeight: 600,
              lineHeight: 1.45,
              letterSpacing: "-0.01em",
              color: "var(--color-text-primary)",
              margin: 0,
            }}>
              {market.question}
            </h2>
            <p style={{ fontSize: 12, color: "var(--color-text-tertiary)", marginTop: 6 }}>
              Vol ${market.volume >= 1_000_000
                ? `${(market.volume / 1_000_000).toFixed(1)}M`
                : market.volume >= 1_000
                ? `${(market.volume / 1_000).toFixed(0)}K`
                : market.volume.toFixed(0)}
            </p>
          </div>

          {/* Probability pill */}
          <div style={{
            flexShrink: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-end",
          }}>
            <span style={{
              fontSize: 22,
              fontWeight: 700,
              letterSpacing: "-0.03em",
              color: probColor,
              lineHeight: 1,
            }}>
              {prob.toFixed(1)}%
            </span>
            <span style={{ fontSize: 10, color: "var(--color-text-tertiary)", marginTop: 3, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              probability
            </span>
          </div>
        </div>

        {/* Probability bar */}
        <div style={{
          marginTop: 12,
          height: 3,
          borderRadius: 2,
          background: "rgba(0,0,0,0.06)",
          overflow: "hidden",
        }}>
          <div style={{
            height: "100%",
            width: `${prob}%`,
            background: probColor,
            borderRadius: 2,
            transition: "width var(--transition-slow)",
          }} />
        </div>
      </div>

      {/* ── Feedback messages ── */}
      {(error || updatesMsg) && (
        <div style={{ padding: "0 24px 12px" }}>
          {error && (
            <div style={{
              padding: "10px 14px",
              borderRadius: "var(--radius-sm)",
              background: "var(--color-danger-light)",
              color: "var(--color-danger)",
              fontSize: 13,
              fontWeight: 500,
            }}>
              {error}
            </div>
          )}
          {updatesMsg && (
            <div style={{
              padding: "10px 14px",
              borderRadius: "var(--radius-sm)",
              background: "var(--color-success-light)",
              color: "#1a7a35",
              fontSize: 13,
              fontWeight: 500,
            }}>
              {updatesMsg}
            </div>
          )}
        </div>
      )}

      {/* ── Actions ── */}
      <div style={{
        padding: "0 24px 20px",
        display: "flex",
        gap: 8,
        flexWrap: "wrap",
      }}>
        <ActionButton
          onClick={handleExplain}
          disabled={loadingExplain || !!explanation}
          loading={loadingExplain}
          done={!!explanation}
          label="Explain"
          doneLabel="Explained"
          loadingLabel="Explaining…"
          color="var(--color-accent)"
          hoverColor="var(--color-accent-hover)"
        />
        <ActionButton
          onClick={handleUpdates}
          disabled={loadingUpdates}
          loading={loadingUpdates}
          done={false}
          label="Generate updates"
          doneLabel="Generate updates"
          loadingLabel="Generating…"
          color="var(--color-violet)"
          hoverColor="var(--color-violet-hover)"
        />
      </div>

      {/* ── Explanation article ── */}
      {explanation && (
        <div style={{
          margin: "0 16px 16px",
          borderRadius: "var(--radius-md)",
          background: "var(--color-accent-light)",
          padding: "16px 18px",
          borderLeft: "3px solid var(--color-accent)",
        }}>
          <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-accent)", margin: 0 }}>
            Explanation
          </p>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text-primary)", margin: "6px 0 8px", letterSpacing: "-0.01em", lineHeight: 1.4 }}>
            {explanation.title}
          </h3>
          <p style={{ fontSize: 13, color: "var(--color-text-secondary)", lineHeight: 1.65, margin: 0, whiteSpace: "pre-wrap" }}>
            {explanation.body}
          </p>
          <p style={{ fontSize: 11, color: "var(--color-text-tertiary)", marginTop: 10, marginBottom: 0 }}>
            At {(explanation.probability_at_generation * 100).toFixed(1)}% · {explanation.llm_model}
          </p>
        </div>
      )}

      {/* ── Update articles ── */}
      {updates.length > 0 && (
        <div style={{ margin: "0 16px 16px" }}>
          <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-text-tertiary)", marginBottom: 8 }}>
            Moves · {updates.length}
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {updates.map((article) => {
              const change = article.probability_change;
              const isUp = change !== null && change > 0;
              const changeColor = change === null ? "var(--color-text-tertiary)" : isUp ? "var(--color-up)" : "var(--color-down)";
              return (
                <div key={article.id} style={{
                  borderRadius: "var(--radius-md)",
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  padding: "14px 16px",
                }}>
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
                    <h4 style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-primary)", margin: 0, letterSpacing: "-0.01em", lineHeight: 1.4 }}>
                      {article.title}
                    </h4>
                    <div style={{ flexShrink: 0, textAlign: "right" }}>
                      {article.snapshot_date && (
                        <span style={{ fontSize: 11, color: "var(--color-text-tertiary)", display: "block" }}>
                          {article.snapshot_date}
                        </span>
                      )}
                      {change !== null && (
                        <span style={{ fontSize: 12, fontWeight: 600, color: changeColor, display: "block", marginTop: 2 }}>
                          {isUp ? "+" : ""}{(change * 100).toFixed(1)}pp
                        </span>
                      )}
                    </div>
                  </div>
                  <p style={{ fontSize: 13, color: "var(--color-text-secondary)", lineHeight: 1.65, margin: "8px 0 0", whiteSpace: "pre-wrap" }}>
                    {article.body}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </article>
  );
}

interface ActionButtonProps {
  onClick: () => void;
  disabled: boolean;
  loading: boolean;
  done: boolean;
  label: string;
  doneLabel: string;
  loadingLabel: string;
  color: string;
  hoverColor: string;
}

function ActionButton({ onClick, disabled, loading, done, label, doneLabel, loadingLabel, color, hoverColor }: ActionButtonProps) {
  const [hovered, setHovered] = useState(false);

  const bg = done
    ? "rgba(0,0,0,0.05)"
    : disabled && !loading
    ? "rgba(0,0,0,0.05)"
    : hovered
    ? hoverColor
    : color;

  const textColor = done || (disabled && !loading) ? "var(--color-text-tertiary)" : "#fff";
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
        padding: "8px 16px",
        borderRadius: "var(--radius-pill)",
        border: "none",
        fontSize: 13,
        fontWeight: 550,
        color: textColor,
        background: bg,
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "all var(--transition-fast)",
        letterSpacing: "-0.01em",
        outline: "none",
        transform: hovered && !disabled ? "scale(1.02)" : "scale(1)",
        opacity: disabled && !done ? 0.5 : 1,
        fontFamily: "inherit",
      }}
    >
      {loading && (
        <span style={{
          width: 12,
          height: 12,
          border: "1.5px solid rgba(255,255,255,0.4)",
          borderTopColor: "#fff",
          borderRadius: "50%",
          display: "inline-block",
          animation: "spin 0.7s linear infinite",
        }} />
      )}
      {displayLabel}
    </button>
  );
}
