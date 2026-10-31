"use client";

import { useState, useMemo } from "react";
import type { Market, MarketSnapshot } from "@/types";
import { MarketCard } from "@/components/MarketCard";

type SortKey = "volume" | "probability" | "change";

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "volume", label: "Volume" },
  { key: "probability", label: "Probability" },
  { key: "change", label: "7-day change" },
];

function get7dDelta(snapshots: MarketSnapshot[], currentProb: number): number {
  if (!snapshots || snapshots.length < 2) return 0;
  const sorted = [...snapshots].sort((a, b) => a.date.localeCompare(b.date));
  const now = new Date();
  const target = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  let best: MarketSnapshot | null = null;
  let bestDiff = Infinity;
  for (const s of sorted) {
    const d = new Date(s.date);
    const diff = Math.abs(d.getTime() - target.getTime());
    if (diff < bestDiff && d <= now) { bestDiff = diff; best = s; }
  }
  if (!best) return 0;
  const latest = sorted[sorted.length - 1];
  if (latest.date === best.date) return 0;
  return (currentProb - best.probability) * 100;
}

interface Props {
  markets: Market[];
}

export function MarketList({ markets }: Props) {
  const [sort, setSort] = useState<SortKey>("volume");

  const sorted = useMemo(() => {
    const copy = [...markets];
    if (sort === "volume") {
      copy.sort((a, b) => b.volume - a.volume);
    } else if (sort === "probability") {
      copy.sort((a, b) => b.probability - a.probability);
    } else if (sort === "change") {
      copy.sort((a, b) =>
        Math.abs(get7dDelta(b.snapshots, b.probability)) -
        Math.abs(get7dDelta(a.snapshots, a.probability))
      );
    }
    return copy;
  }, [markets, sort]);

  return (
    <div>
      {/* Sort controls */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        marginBottom: 20,
      }}>
        <span style={{
          fontSize: 11,
          color: "var(--text-muted)",
          letterSpacing: "0.04em",
          textTransform: "uppercase",
          fontWeight: 600,
          marginRight: 2,
        }}>
          Sort
        </span>
        {SORT_OPTIONS.map(({ key, label }) => (
          <SortPill
            key={key}
            label={label}
            active={sort === key}
            onClick={() => setSort(key)}
          />
        ))}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {sorted.map((market) => (
          <MarketCard key={market.id} market={market} />
        ))}
      </div>
    </div>
  );
}

function SortPill({
  label, active, onClick,
}: { label: string; active: boolean; onClick: () => void }) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        padding: "4px 12px",
        borderRadius: 100,
        border: active ? "1px solid var(--border-indigo)" : "1px solid var(--border-card)",
        fontSize: 12,
        fontWeight: active ? 600 : 450,
        color: active ? "#6366f1" : "var(--text-secondary)",
        background: active ? "var(--bg-indigo)" : hovered ? "var(--bg-nav)" : "transparent",
        cursor: "pointer",
        transition: "all 150ms ease-out",
        letterSpacing: "-0.01em",
        outline: "none",
        fontFamily: "inherit",
      }}
    >
      {label}
    </button>
  );
}
