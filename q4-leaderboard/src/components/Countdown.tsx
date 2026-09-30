'use client';

import { useEffect, useState } from 'react';

function parts(ms: number) {
  const total = Math.max(0, Math.floor(ms / 1000));
  return {
    d: Math.floor(total / 86400),
    h: Math.floor((total % 86400) / 3600),
    m: Math.floor((total % 3600) / 60),
    s: total % 60,
  };
}

export function Countdown({ target, label }: { target: string; label: string }) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    setNow(Date.now());
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const p = parts(new Date(target).getTime() - (now ?? Date.now()));
  const cell = (v: number, unit: string) => (
    <div className="min-w-[58px] rounded-2xl border border-white/10 bg-black/50 px-2 py-2 text-center">
      <div className="font-display text-2xl font-extrabold tabular-nums" suppressHydrationWarning>
        {String(v).padStart(2, '0')}
      </div>
      <div className="text-[10px] uppercase tracking-wider text-muted">{unit}</div>
    </div>
  );
  return (
    <div>
      <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">{label}</div>
      <div className="flex gap-2">
        {cell(p.d, 'dni')}
        {cell(p.h, 'godz')}
        {cell(p.m, 'min')}
        {cell(p.s, 'sek')}
      </div>
    </div>
  );
}
