'use server';

import bcrypt from 'bcryptjs';
import crypto from 'node:crypto';
import { revalidatePath } from 'next/cache';
import { config } from '@/lib/config';
import { execute, normalizeCode, query } from '@/lib/db';
import { getEvent, getPeriods } from '@/lib/data';
import { destroyAllSessions, requireAdmin } from '@/lib/auth';
import { sendMail } from '@/lib/mail';
import { writeEntry } from '@/lib/revenue';
import { invalidateLeaderboardCache } from '@/lib/leaderboard';
import { removeDemoData, seedDemoData } from '@/lib/demo';
import { backupAdminExists, createBackup, parseBackupFile, readBackup, restoreBackup } from '@/lib/backup';
import { deleteAvatar } from '@/lib/uploads';
import { fromLocalInput } from '@/lib/time';
import { MAX_REVENUE, parseMoney } from '@/lib/validation';
import type { FormState } from './types';

const str = (fd: FormData, key: string) => String(fd.get(key) ?? '');
const ids = (fd: FormData) =>
  fd
    .getAll('ids')
    .map((v) => Number(v))
    .filter((n) => Number.isInteger(n) && n > 0);

function refresh() {
  invalidateLeaderboardCache();
  revalidatePath('/', 'layout');
}

export async function approveUsersAction(fd: FormData): Promise<void> {
  const admin = await requireAdmin();
  const list = ids(fd);
  if (list.length === 0) return;
  const users = await query<{ id: number; email: string }>(
    `SELECT id, email FROM users WHERE id IN (?) AND status IN ('pending','rejected')`,
    [list],
  );
  if (users.length === 0) return;
  await execute(`UPDATE users SET status = 'active', verified_by = ?, verified_at = ?, updated_at = ? WHERE id IN (?)`, [
    admin.id,
    new Date(),
    new Date(),
    users.map((u) => u.id),
  ]);
  refresh();

  if (config.sendApprovalEmails) {
    const event = await getEvent();
    // Sent in the background so bulk approval stays fast; failures only end up in the log.
    void (async () => {
      for (const u of users) {
        try {
          await sendMail(
            u.email,
            `${event.name} — Twoje konto jest aktywne`,
            `Cześć!\n\nTwoje konto zostało zaakceptowane. Możesz już dodawać swój przychód i walczyć o miejsce w rankingu:\n\n${config.appUrl}/konto\n\nPowodzenia!`,
          );
        } catch (err) {
          console.error('[mail] approval mail failed', u.id, err);
        }
      }
    })();
  }
}

export async function setUserStatusAction(fd: FormData): Promise<void> {
  const admin = await requireAdmin();
  const id = Number(str(fd, 'id'));
  const status = str(fd, 'status');
  if (!['active', 'rejected', 'suspended', 'pending'].includes(status) || id === admin.id) return;
  await execute(`UPDATE users SET status = ?, updated_at = ? WHERE id = ? AND status <> 'deleted'`, [status, new Date(), id]);
  refresh();
}

/** Removes personal data but keeps the audit trail consistent. Irreversible. */
export async function anonymizeUserAction(fd: FormData): Promise<void> {
  const admin = await requireAdmin();
  const id = Number(str(fd, 'id'));
  if (!id || id === admin.id || str(fd, 'confirm') !== 'USUŃ') return;
  const rows = await query<{ avatar_file: string | null }>('SELECT avatar_file FROM users WHERE id = ?', [id]);
  if (!rows[0]) return;
  await execute(
    `UPDATE users SET status = 'deleted', email = ?, discord_nickname = '', public_nickname = ?, avatar_file = NULL,
       avatar_preset = 'rocket', password_hash = ?, updated_at = ? WHERE id = ?`,
    [`deleted-${id}@deleted.invalid`, `usuniety-${id}`, crypto.randomBytes(24).toString('hex'), new Date(), id],
  );
  await execute('DELETE FROM revenue_entries WHERE user_id = ?', [id]);
  await execute('DELETE FROM correction_requests WHERE user_id = ?', [id]);
  await execute('DELETE FROM password_resets WHERE user_id = ?', [id]);
  await destroyAllSessions(id);
  await deleteAvatar(rows[0].avatar_file);
  refresh();
}

export async function adminSetEntryAction(_prev: FormState, fd: FormData): Promise<FormState> {
  const admin = await requireAdmin();
  const userId = Number(str(fd, 'user_id'));
  const periodId = Number(str(fd, 'period_id'));
  const reason = str(fd, 'reason').trim().slice(0, 255);
  const raw = str(fd, 'value').trim();
  if (!reason) return { error: 'Podaj powód korekty.' };

  const event = await getEvent();
  const periods = await getPeriods(event.id);
  if (!periods.some((p) => p.id === periodId)) return { error: 'Nieznany tydzień.' };
  const users = await query('SELECT id FROM users WHERE id = ?', [userId]);
  if (users.length === 0) return { error: 'Nieznany użytkownik.' };

  let value: number | null = null;
  if (raw !== '') {
    value = parseMoney(raw);
    if (value === null || value > MAX_REVENUE) return { error: 'Nieprawidłowa kwota.' };
  }
  await writeEntry({ eventId: event.id, userId, periodId, value, changedBy: admin.id, reason });

  const correctionId = Number(str(fd, 'correction_id'));
  if (correctionId) {
    await execute(`UPDATE correction_requests SET status = 'resolved', resolved_by = ?, resolved_at = ? WHERE id = ?`, [
      admin.id,
      new Date(),
      correctionId,
    ]);
  }
  refresh();
  return { success: value === null ? 'Wpis usunięty.' : 'Wynik zapisany.' };
}

export async function resolveCorrectionAction(fd: FormData): Promise<void> {
  const admin = await requireAdmin();
  const status = str(fd, 'status') === 'resolved' ? 'resolved' : 'dismissed';
  await execute('UPDATE correction_requests SET status = ?, resolved_by = ?, resolved_at = ? WHERE id = ?', [
    status,
    admin.id,
    new Date(),
    Number(str(fd, 'id')),
  ]);
  refresh();
}

export async function updatePeriodAction(_prev: FormState, fd: FormData): Promise<FormState> {
  await requireAdmin();
  const id = Number(str(fd, 'id'));
  const startsAt = fromLocalInput(str(fd, 'starts_at'));
  const endsAt = fromLocalInput(str(fd, 'ends_at'), 59);
  if (!startsAt || !endsAt) return { error: 'Uzupełnij obie daty.' };
  if (!(startsAt < endsAt)) return { error: 'Początek tygodnia musi być przed jego końcem.' };
  await execute('UPDATE reporting_periods SET starts_at = ?, ends_at = ?, entry_deadline = ? WHERE id = ?', [startsAt, endsAt, endsAt, id]);
  refresh();
  return { success: 'Tydzień zapisany.' };
}

export async function togglePeriodLockAction(fd: FormData): Promise<void> {
  await requireAdmin();
  await execute('UPDATE reporting_periods SET is_locked = ? WHERE id = ?', [str(fd, 'locked') === '1' ? 1 : 0, Number(str(fd, 'id'))]);
  refresh();
}

export async function addPeriodAction(): Promise<void> {
  await requireAdmin();
  const event = await getEvent();
  const periods = await getPeriods(event.id);
  const last = periods[periods.length - 1];
  if (!last) return;
  const week = 7 * 86_400_000;
  await execute(
    'INSERT INTO reporting_periods (event_id, week_number, starts_at, ends_at, entry_deadline) VALUES (?, ?, ?, ?, ?)',
    [
      event.id,
      last.weekNumber + 1,
      new Date(last.endsAt.getTime() + 1000),
      new Date(last.endsAt.getTime() + week),
      new Date(last.endsAt.getTime() + week),
    ],
  );
  refresh();
}

export async function updateSettingsAction(_prev: FormState, fd: FormData): Promise<FormState> {
  await requireAdmin();
  const event = await getEvent();
  const name = str(fd, 'name').trim().slice(0, 120);
  const motivation = str(fd, 'motivation_text').trim().slice(0, 255);
  if (!name) return { error: 'Nazwa eventu jest wymagana.' };
  const newCode = str(fd, 'access_code').trim();
  const codeRequired = fd.get('access_code_required') === 'on';
  let codeHash = event.accessCodeHash;
  if (newCode) {
    if (newCode.length < 4) return { error: 'Kod dostępu musi mieć co najmniej 4 znaki.' };
    codeHash = await bcrypt.hash(normalizeCode(newCode), 10);
  }
  if (codeRequired && !codeHash) return { error: 'Ustaw kod dostępu albo wyłącz jego wymaganie.' };
  const revealRaw = str(fd, 'ranking_reveal_at').trim();
  const revealAt = revealRaw ? fromLocalInput(revealRaw) : null;
  if (revealRaw && !revealAt) return { error: 'Nieprawidłowa data odsłonięcia rankingu.' };

  await execute(
    `UPDATE events SET name = ?, motivation_text = ?, access_code_hash = ?, access_code_required = ?,
       registration_open = ?, is_public_leaderboard = ?, ranking_reveal_at = ? WHERE id = ?`,
    [
      name,
      motivation,
      codeHash,
      codeRequired ? 1 : 0,
      fd.get('registration_open') === 'on' ? 1 : 0,
      fd.get('is_public_leaderboard') === 'on' ? 1 : 0,
      revealAt,
      event.id,
    ],
  );
  refresh();
  return { success: newCode ? 'Zapisano. Nowy kod dostępu jest aktywny.' : 'Ustawienia zapisane.' };
}

export async function seedDemoAction(_prev: FormState, _fd: FormData): Promise<FormState> {
  await requireAdmin();
  const event = await getEvent();
  const created = await seedDemoData(event.id, 50);
  refresh();
  return created > 0
    ? { success: `Dodano ${created} kont testowych z wynikami. Zobacz ranking na stronie głównej.` }
    : { error: 'Konta testowe już istnieją — najpierw je usuń.' };
}

export async function removeDemoAction(_prev: FormState, _fd: FormData): Promise<FormState> {
  await requireAdmin();
  const removed = await removeDemoData();
  refresh();
  return { success: `Usunięto ${removed} kont testowych wraz z ich wynikami.` };
}

export async function createBackupAction(_prev: FormState, _fd: FormData): Promise<FormState> {
  const admin = await requireAdmin();
  const { summary } = await createBackup('Ręczna kopia administratora', admin.id);
  revalidatePath('/admin/kopie');
  return { success: `Kopia zapisana (${summary}).` };
}

export async function restoreBackupAction(_prev: FormState, fd: FormData): Promise<FormState> {
  const admin = await requireAdmin();
  if (str(fd, 'confirm') !== 'PRZYWRÓĆ') return { error: 'Wpisz PRZYWRÓĆ, aby potwierdzić.' };
  let backup;
  const file = fd.get('file');
  if (file instanceof File && file.size > 0) {
    if (file.size > 4 * 1024 * 1024) return { error: 'Plik jest za duży (maks. 4 MB).' };
    const parsed = parseBackupFile(await file.text());
    if ('error' in parsed) return { error: parsed.error };
    backup = parsed;
  } else {
    backup = await readBackup(Number(str(fd, 'id')));
    if (!backup) return { error: 'Nie znaleziono kopii.' };
  }
  if (!(await backupAdminExists(backup, admin.id)) && str(fd, 'force') !== 'on') {
    return { error: 'W tej kopii nie ma Twojego konta administratora — po przywróceniu zostaniesz wylogowany. Zaznacz „Rozumiem”, aby kontynuować.' };
  }
  let summary: string;
  try {
    summary = await restoreBackup(backup, admin.id);
  } catch (err) {
    console.error('[backup] restore failed', err);
    return { error: 'Przywracanie nie powiodło się — dane pozostały bez zmian (operacja została wycofana w całości).' };
  }
  refresh();
  return { success: `Przywrócono kopię z ${new Date(backup.createdAt).toLocaleString('pl-PL', { timeZone: 'Europe/Warsaw' })} (${summary}). Stan sprzed przywrócenia zapisano jako osobną kopię.` };
}

export async function setMaintenanceAction(_prev: FormState, fd: FormData): Promise<FormState> {
  await requireAdmin();
  const mode = str(fd, 'mode');
  if (!['off', 'readonly', 'closed'].includes(mode)) return { error: 'Nieznany tryb.' };
  const event = await getEvent();
  await execute('UPDATE events SET maintenance_mode = ?, maintenance_message = ? WHERE id = ?', [
    mode,
    str(fd, 'message').trim().slice(0, 255) || null,
    event.id,
  ]);
  refresh();
  return {
    success:
      mode === 'off' ? 'Strona działa normalnie.' : mode === 'readonly' ? 'Włączono tryb „tylko odczyt”.' : 'Strona zamknięta dla uczestników (przerwa techniczna).',
  };
}
