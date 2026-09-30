'use server';

import bcrypt from 'bcryptjs';
import { revalidatePath } from 'next/cache';
import { after } from 'next/server';
import { ensureDailyBackup } from '@/lib/backup';
import { writeBlockedMessage } from '@/lib/maintenance';
import { execute, query } from '@/lib/db';
import { AVATAR_PRESETS, getEvent, getPeriods } from '@/lib/data';
import { getCurrentUser } from '@/lib/auth';
import { currentPeriodState, isPeriodOpen } from '@/lib/periods';
import { previousCumulative, writeEntry } from '@/lib/revenue';
import { invalidateLeaderboardCache } from '@/lib/leaderboard';
import { deleteAvatar, saveAvatarDataUrl } from '@/lib/uploads';
import { MAX_REVENUE, formatPln, parseMoney, validateDiscord, validateNickname, validatePassword } from '@/lib/validation';
import type { FormState } from './types';

const str = (fd: FormData, key: string) => String(fd.get(key) ?? '');

async function activeUser() {
  const user = await getCurrentUser();
  if (!user) return { error: 'Zaloguj się ponownie.' } as const;
  if (user.status !== 'active') return { error: 'Twoje konto nie jest aktywne.' } as const;
  const blocked = writeBlockedMessage(await getEvent(), user);
  if (blocked) return { error: blocked } as const;
  return { user } as const;
}

async function openPeriod() {
  const event = await getEvent();
  const periods = await getPeriods(event.id);
  const now = new Date();
  const state = currentPeriodState(periods, now);
  if (state.phase === 'before') return { error: 'Raportowanie jeszcze się nie rozpoczęło.' } as const;
  if (state.phase === 'finished') return { error: 'Event się zakończył — wyniki są zamknięte.' } as const;
  const period = periods[state.index];
  if (!isPeriodOpen(period, now)) return { error: `Tydzień ${period.weekNumber} jest już zamknięty.` } as const;
  return { event, period, isFirstWeek: state.index === 0 } as const;
}

export async function saveRevenueAction(_prev: FormState, fd: FormData): Promise<FormState> {
  const auth = await activeUser();
  if ('error' in auth) return { error: auth.error };
  const open = await openPeriod();
  if ('error' in open) return { error: open.error };
  const { event, period, isFirstWeek } = open;
  const user = auth.user;

  const raw = str(fd, 'revenue');
  const value = parseMoney(raw);
  if (value === null) return { error: 'Wpisz kwotę w złotych, np. 25 000.', fields: { revenue: raw } };
  if (value < 0) return { error: 'Kwota nie może być ujemna.', fields: { revenue: raw } };
  if (value > MAX_REVENUE) return { error: 'Ta kwota wygląda na pomyłkę. Sprawdź ją jeszcze raz.', fields: { revenue: raw } };

  const previous = await previousCumulative(user.id, event.id, period.weekNumber);
  const floor = previous ?? 0;
  if (value < floor) {
    return {
      error: `Wynik narastający nie może być niższy niż ostatnio zgłoszony (${formatPln(floor)}). Jeśli wcześniej wpisałeś błędną kwotę, zgłoś korektę organizatorowi.`,
      fields: { revenue: raw },
      correctionFor: value,
    };
  }

  const { oldValue } = await writeEntry({
    eventId: event.id,
    userId: user.id,
    periodId: period.id,
    value,
    changedBy: user.id,
    reason: null,
  });
  revalidatePath('/', 'layout');
  after(() => ensureDailyBackup().catch((err) => console.error('[backup] daily backup failed', err)));

  const parts = [`Zapisano: ${formatPln(value)} od początku Q4.`];
  if (previous === null && !isFirstWeek) {
    // Late joiner: the first entry holds all sales since the start of Q4, so it only counts for the Q4 ranking.
    parts.push('To Twój pierwszy wpis — liczy się do rankingu całego Q4. W rankingu tygodniowym pojawisz się od następnego tygodnia.');
  } else {
    parts.push(`Przyrost w tygodniu ${period.weekNumber}: +${formatPln(value - floor)}.`);
  }
  if (oldValue !== null && oldValue !== value) parts.push(`(Poprzedni wpis w tym tygodniu: ${formatPln(oldValue)}.)`);
  return { success: parts.join(' ') };
}

export async function requestCorrectionAction(_prev: FormState, fd: FormData): Promise<FormState> {
  const auth = await activeUser();
  if ('error' in auth) return { error: auth.error };
  const open = await openPeriod();
  if ('error' in open) return { error: open.error };

  const value = parseMoney(str(fd, 'requested_value'));
  if (value === null || value > MAX_REVENUE) return { error: 'Nieprawidłowa kwota.' };
  const message = str(fd, 'message').trim().slice(0, 500);

  const openCount = await query<{ n: number }>(
    "SELECT COUNT(*) AS n FROM correction_requests WHERE user_id = ? AND status = 'open'",
    [auth.user.id],
  );
  if (Number(openCount[0]?.n ?? 0) >= 3) return { error: 'Masz już otwarte zgłoszenia — poczekaj na odpowiedź organizatora.' };

  await execute(
    'INSERT INTO correction_requests (user_id, reporting_period_id, requested_value, message, created_at) VALUES (?, ?, ?, ?, ?)',
    [auth.user.id, open.period.id, value, message, new Date()],
  );
  return { success: 'Zgłoszenie korekty zostało wysłane do organizatora.' };
}

export async function updateProfileAction(_prev: FormState, fd: FormData): Promise<FormState> {
  const user = await getCurrentUser();
  if (!user || user.status === 'deleted') return { error: 'Zaloguj się ponownie.' };
  const blocked = writeBlockedMessage(await getEvent(), user);
  if (blocked) return { error: blocked };

  const nickname = str(fd, 'nickname').trim().replace(/\s+/g, ' ');
  const discord = str(fd, 'discord').trim();
  const fields = { nickname, discord };
  const error = validateNickname(nickname) ?? validateDiscord(discord);
  if (error) return { error, fields };

  if (nickname.toLowerCase() !== user.publicNickname.toLowerCase()) {
    const taken = await query('SELECT id FROM users WHERE public_nickname = ? AND id <> ?', [nickname, user.id]);
    if (taken.length > 0) return { error: 'Ten nick jest już zajęty.', fields };
  }

  let avatarFile = user.avatarFile;
  let avatarPreset = user.avatarPreset;
  const mode = str(fd, 'avatar_mode');
  if (mode === 'upload' && str(fd, 'avatar_data')) {
    const saved = await saveAvatarDataUrl(str(fd, 'avatar_data'));
    if ('error' in saved) return { error: saved.error, fields };
    avatarFile = saved.file;
  } else if (mode === 'preset') {
    const preset = str(fd, 'avatar_preset');
    if (!AVATAR_PRESETS.includes(preset as (typeof AVATAR_PRESETS)[number])) return { error: 'Wybierz awatar z listy.', fields };
    avatarPreset = preset;
    avatarFile = null;
  }

  try {
    await execute(
      'UPDATE users SET public_nickname = ?, discord_nickname = ?, avatar_preset = ?, avatar_file = ?, updated_at = ? WHERE id = ?',
      [nickname, discord, avatarPreset, avatarFile, new Date(), user.id],
    );
  } catch (err) {
    if ((err as { code?: string }).code === 'ER_DUP_ENTRY') return { error: 'Ten nick jest już zajęty.', fields };
    throw err;
  }
  if (avatarFile !== user.avatarFile) await deleteAvatar(user.avatarFile);
  invalidateLeaderboardCache();
  revalidatePath('/', 'layout');
  return { success: 'Profil zapisany.' };
}

export async function changePasswordAction(_prev: FormState, fd: FormData): Promise<FormState> {
  const user = await getCurrentUser();
  if (!user) return { error: 'Zaloguj się ponownie.' };
  const rows = await query<{ password_hash: string }>('SELECT password_hash FROM users WHERE id = ?', [user.id]);
  if (!rows[0] || !(await bcrypt.compare(str(fd, 'current'), rows[0].password_hash))) return { error: 'Obecne hasło jest nieprawidłowe.' };
  const password = str(fd, 'password');
  const error = validatePassword(password) ?? (password !== str(fd, 'password2') ? 'Hasła nie są takie same.' : null);
  if (error) return { error };
  await execute('UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?', [await bcrypt.hash(password, 10), new Date(), user.id]);
  return { success: 'Hasło zostało zmienione.' };
}

export async function requestDeletionAction(_prev: FormState, _fd: FormData): Promise<FormState> {
  const user = await getCurrentUser();
  if (!user) return { error: 'Zaloguj się ponownie.' };
  const blocked = writeBlockedMessage(await getEvent(), user);
  if (blocked) return { error: blocked };
  await execute('UPDATE users SET deletion_requested_at = ?, updated_at = ? WHERE id = ?', [new Date(), new Date(), user.id]);
  return { success: 'Prośba o usunięcie konta została przekazana organizatorowi.' };
}
