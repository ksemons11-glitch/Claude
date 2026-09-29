'use client';

import { useEffect, useState } from 'react';
import type { PublicRow, RankingView } from '@/lib/leaderboard';
import { formatPln } from '@/lib/validation';
import { Avatar } from './Avatar';
import { ChangeBadge } from './ChangeBadge';

const PAGE = 25;

function Row({ row, weekly }: { row: PublicRow; weekly: boolean }) {
  return (
    <li className={`flex items-center gap-3 px-3 py-2.5 ${row.isMe ? 'bg-accent/10 ring-1 ring-inset ring-accent/40' : ''}`}>
      <span className="w-9 shrink-0 text-right text-sm font-bold tabular-nums text-muted">{row.rank}.</span>
      <Avatar src={row.avatarUrl} size={36} />
      <span className="min-w-0 flex-1 truncate font-medium">{row.nickname}</span>
      <span className="font-bold tabular-nums">{weekly ? `+${formatPln(row.value)}` : formatPln(row.value)}</span>
      {!weekly && (
        <span className="w-10 shrink-0 text-right">
          <ChangeBadge change={row.change} isNew={row.isNew} />
        </span>
      )}
    </li>
  );
}

async function fetchRows(params: Record<string, string>): Promise<{ rows: PublicRow[]; total: number }> {
  const res = await fetch(`/api/ranking?${new URLSearchParams(params)}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(String(res.status));
  return res.json();
}

export function FullRanking({ view, startOffset, total }: { view: RankingView; startOffset: number; total: number }) {
  const weekly = view !== 'q4';
  const [rows, setRows] = useState<PublicRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [q, setQ] = useState('');
  const [results, setResults] = useState<PublicRow[] | null>(null);

  const remaining = total - startOffset - rows.length;

  async function loadMore() {
    setLoading(true);
    setError(false);
    try {
      const data = await fetchRows({ view, offset: String(startOffset + rows.length), limit: String(PAGE) });
      setRows((r) => [...r, ...data.rows]);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) {
      setResults(null);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const data = await fetchRows({ view, q: term, limit: '25' });
        setResults(data.rows);
      } catch {
        setResults([]);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [q, view]);

  return (
    <section className="mt-6" aria-label="Pełny ranking">
      <label className="relative block">
        <span className="sr-only">Szukaj po nicku</span>
        <input
          type="search"
          className="input pl-11"
          placeholder="Szukaj uczestnika po nicku…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-muted" aria-hidden>
          ⌕
        </span>
      </label>

      {results !== null ? (
        <div className="card mt-3 overflow-hidden">
          {results.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-muted">Nie znaleziono uczestnika o takim nicku.</p>
          ) : (
            <ul className="divide-y divide-line">
              {results.map((r) => (
                <Row key={`s-${r.rank}-${r.nickname}`} row={r} weekly={weekly} />
              ))}
            </ul>
          )}
        </div>
      ) : (
        total > startOffset && (
          <>
            {rows.length > 0 && (
              <ul className="card mt-3 divide-y divide-line overflow-hidden">
                {rows.map((r) => (
                  <Row key={`${r.rank}-${r.nickname}`} row={r} weekly={weekly} />
                ))}
              </ul>
            )}
            {error && <p className="alert-error mt-3">Nie udało się wczytać rankingu. Spróbuj ponownie.</p>}
            {remaining > 0 && (
              <button type="button" onClick={loadMore} disabled={loading} className="btn-ghost mt-3 w-full">
                {loading
                  ? 'Wczytywanie…'
                  : rows.length === 0
                    ? `Pokaż pełny ranking (jeszcze ${remaining})`
                    : `Pokaż kolejne ${Math.min(PAGE, remaining)}`}
              </button>
            )}
          </>
        )
      )}
    </section>
  );
}
