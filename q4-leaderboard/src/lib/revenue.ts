import 'server-only';
import type { RowDataPacket } from 'mysql2/promise';
import { query, transaction } from './db';

/** Latest cumulative value the user reported in weeks before `weekNumber` (0 if none). */
export async function previousCumulative(userId: number, eventId: number, weekNumber: number): Promise<number> {
  const rows = await query<{ v: number | string }>(
    `SELECT e.cumulative_revenue AS v
     FROM revenue_entries e JOIN reporting_periods p ON p.id = e.reporting_period_id
     WHERE e.user_id = ? AND p.event_id = ? AND p.week_number < ?
     ORDER BY p.week_number DESC LIMIT 1`,
    [userId, eventId, weekNumber],
  );
  return rows[0] ? Number(rows[0].v) : 0;
}

export async function entryFor(userId: number, periodId: number): Promise<number | null> {
  const rows = await query<{ v: number | string }>(
    'SELECT cumulative_revenue AS v FROM revenue_entries WHERE user_id = ? AND reporting_period_id = ?',
    [userId, periodId],
  );
  return rows[0] ? Number(rows[0].v) : null;
}

/**
 * Creates, updates or (value = null) removes the entry of one user for one week,
 * and always writes an audit-log row with the old and new value.
 */
export async function writeEntry(opts: {
  eventId: number;
  userId: number;
  periodId: number;
  value: number | null;
  changedBy: number;
  reason: string | null;
}): Promise<{ oldValue: number | null }> {
  return transaction(async (conn) => {
    const [rows] = await conn.query<RowDataPacket[]>(
      'SELECT id, cumulative_revenue AS v FROM revenue_entries WHERE user_id = ? AND reporting_period_id = ? FOR UPDATE',
      [opts.userId, opts.periodId],
    );
    const existing = rows[0] as { id: number; v: number | string } | undefined;
    const oldValue = existing ? Number(existing.v) : null;
    if (oldValue === opts.value) return { oldValue };

    const now = new Date();
    let entryId: number | null = existing?.id ?? null;
    if (opts.value === null) {
      if (existing) await conn.query('DELETE FROM revenue_entries WHERE id = ?', [existing.id]);
      entryId = null;
    } else if (existing) {
      await conn.query('UPDATE revenue_entries SET cumulative_revenue = ?, updated_at = ? WHERE id = ?', [opts.value, now, existing.id]);
    } else {
      const [res] = await conn.query<import('mysql2/promise').ResultSetHeader>(
        `INSERT INTO revenue_entries (event_id, user_id, reporting_period_id, cumulative_revenue, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?)`,
        [opts.eventId, opts.userId, opts.periodId, opts.value, now, now],
      );
      entryId = res.insertId;
    }
    await conn.query(
      `INSERT INTO revenue_entry_audit_log
         (revenue_entry_id, user_id, reporting_period_id, changed_by_user_id, old_value, new_value, change_reason, changed_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      [entryId, opts.userId, opts.periodId, opts.changedBy, oldValue, opts.value, opts.reason, now],
    );
    return { oldValue };
  });
}
