"use client";

import Link from "next/link";
import type { PeerStock } from "@/lib/types";

interface PeerListProps {
  peers: PeerStock[];
}

export function PeerList({ peers }: PeerListProps) {
  if (!peers.length) {
    return (
      <p className="py-4 text-sm text-foreground/50">No peers found</p>
    );
  }

  return (
    <ul className="divide-y divide-foreground/10">
      {peers.map((peer) => (
        <li key={peer.symbol}>
          <Link
            href={`/stocks/${peer.symbol}`}
            className="flex items-center justify-between px-2 py-3 transition-colors hover:bg-foreground/5"
          >
            <div>
              <span className="font-semibold">{peer.symbol}</span>
              <span className="ml-2 text-sm text-foreground/60">
                {peer.name}
              </span>
            </div>
            <span className="text-xs text-foreground/40">{peer.industry}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
