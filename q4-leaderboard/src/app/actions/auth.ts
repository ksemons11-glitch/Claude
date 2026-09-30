'use server';

import bcrypt from 'bcryptjs';
import { redirect } from 'next/navigation';
import { config } from '@/lib/config';
import { execute, normalizeCode, query } from '@/lib/db';
import { AVATAR_PRESETS, getEvent } from '@/lib/data';
import { createSession, destroyAllSessions, destroySession, randomToken, sha256 } from '@/lib/auth';
import { clientIp, hit } from '@/lib/rate-limit';
import { sendMail } from '@/lib/mail';
import { saveAvatarDataUrl } from '@/lib/uploads';
import { writeBlockedMessage } from '@/lib/maintenance';
import { normalizeEmail, validateDiscord, validateEmail, validateNickname, validatePassword } from '@/lib/validation';
import type { FormState } from './types';

const str = (fd: FormData, key: string) => String(fd.get(key) ?? '');
// Used to keep login timing identical whether or not the e-mail exists.
let dummyHash: string | undefined;
const getDummyHash = async () => (dummyHash ??= await bcrypt.hash('timing-equalizer', 10));

export async function registerAction(_prev: FormState, fd: FormData): Promise<FormState> {
  const fields = {
    email: str(fd, 'email').trim(),
    discord: str(fd, 'discord').trim(),
    nickname: str(fd, 'nickname').trim().replace(/\s+/g, ' '),
    avatar_preset: str(fd, 'avatar_preset'),
  };
  const fail = (error: string): FormState => ({ error, fields });

  if (!(await hit(`register:${await clientIp()}`, 60, 3_600_000))) return fail('Zbyt wiele prób. Spróbuj ponownie za godzinę.');

  const event = await getEvent();
  if (!event.registrationOpen) return fail('Rejestracja jest obecnie zamknięta.');
  const blocked = writeBlockedMessage(event, null);
  if (blocked) return fail(blocked);

  if (event.accessCodeRequired && event.accessCodeHash) {
    const ok = await bcrypt.compare(normalizeCode(str(fd, 'access_code')), event.accessCodeHash);
    if (!ok) return fail('Nieprawidłowy kod dostępu do eventu.');
  }

  const email = normalizeEmail(fields.email);
  const password = str(fd, 'password');
  const error =
    validateEmail(email) ??
    validatePassword(password) ??
    (password !== str(fd, 'password2') ? 'Hasła nie są takie same.' : null) ??
    validateDiscord(fields.discord) ??
    validateNickname(fields.nickname) ??
    (fd.get('terms') !== 'on' ? 'Zaakceptuj regulamin i politykę prywatności.' : null) ??
    (fd.get('public_consent') !== 'on'
      ? 'Zgoda na publiczne wyświetlanie pseudonimu, awatara i wyniku jest wymagana, aby brać udział w rankingu.'
      : null);
  if (error) return fail(error);

  const existing = await query<{ email: string; public_nickname: string }>(
    'SELECT email, public_nickname FROM users WHERE email = ? OR public_nickname = ?',
    [email, fields.nickname],
  );
  if (existing.some((u) => u.email === email)) return fail('Konto z tym adresem e-mail już istnieje. Zaloguj się lub zresetuj hasło.');
  if (existing.length > 0) return fail('Ten nick rankingowy jest już zajęty. Wybierz inny.');

  let avatarFile: string | null = null;
  const avatarData = str(fd, 'avatar_data');
  if (str(fd, 'avatar_mode') === 'upload' && avatarData) {
    const saved = await saveAvatarDataUrl(avatarData);
    if ('error' in saved) return fail(saved.error);
    avatarFile = saved.file;
  }
  const preset = AVATAR_PRESETS.includes(fields.avatar_preset as (typeof AVATAR_PRESETS)[number]) ? fields.avatar_preset : 'rocket';

  const isAdmin = config.adminEmails.includes(email);
  const now = new Date();
  let userId: number;
  try {
    const res = await execute(
      `INSERT INTO users (email, password_hash, discord_nickname, public_nickname, avatar_preset, avatar_file, role, status,
                          consent_terms_at, consent_public_profile_at, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        email,
        await bcrypt.hash(password, 10),
        fields.discord,
        fields.nickname,
        preset,
        avatarFile,
        isAdmin ? 'admin' : 'participant',
        isAdmin ? 'active' : 'pending',
        now,
        now,
        now,
        now,
      ],
    );
    userId = res.insertId;
  } catch (err) {
    if ((err as { code?: string }).code === 'ER_DUP_ENTRY') return fail('Ten e-mail lub nick jest już zajęty.');
    throw err;
  }

  await createSession(userId);
  redirect(isAdmin ? '/admin' : '/konto');
}

export async function loginAction(_prev: FormState, fd: FormData): Promise<FormState> {
  const email = normalizeEmail(str(fd, 'email'));
  const fields = { email };
  if (!(await hit(`login:${await clientIp()}:${email}`, 10, 15 * 60_000))) {
    return { error: 'Zbyt wiele prób logowania. Odczekaj 15 minut.', fields };
  }
  const rows = await query<{ id: number; password_hash: string; role: string; status: string }>(
    'SELECT id, password_hash, role, status FROM users WHERE email = ?',
    [email],
  );
  const user = rows[0];
  const ok = await bcrypt.compare(str(fd, 'password'), user?.password_hash ?? (await getDummyHash()));
  if (!user || !ok || user.status === 'deleted') return { error: 'Nieprawidłowy e-mail lub hasło.', fields };

  await createSession(user.id);
  redirect(user.role === 'admin' ? '/admin' : '/konto');
}

export async function logoutAction(): Promise<void> {
  await destroySession();
  redirect('/');
}

export async function requestPasswordResetAction(_prev: FormState, fd: FormData): Promise<FormState> {
  const email = normalizeEmail(str(fd, 'email'));
  const done: FormState = {
    success: 'Jeśli konto z tym adresem istnieje, wysłaliśmy link do ustawienia nowego hasła. Sprawdź skrzynkę (także spam).',
  };
  if (validateEmail(email)) return { error: 'Podaj poprawny adres e-mail.', fields: { email } };
  if (!(await hit(`reset-ip:${await clientIp()}`, 10, 3_600_000)) || !(await hit(`reset:${email}`, 3, 3_600_000))) return done;

  const rows = await query<{ id: number }>("SELECT id FROM users WHERE email = ? AND status <> 'deleted'", [email]);
  if (rows[0]) {
    const token = randomToken();
    await execute('INSERT INTO password_resets (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)', [
      sha256(token),
      rows[0].id,
      new Date(Date.now() + 3_600_000),
      new Date(),
    ]);
    const event = await getEvent();
    const link = `${config.appUrl}/nowe-haslo?token=${token}`;
    try {
      await sendMail(
        email,
        `${event.name} — ustaw nowe hasło`,
        `Cześć!\n\nOtrzymaliśmy prośbę o zmianę hasła. Kliknij w link, aby ustawić nowe hasło (ważny 1 godzinę):\n\n${link}\n\nJeśli to nie Ty, zignoruj tę wiadomość.`,
      );
    } catch (err) {
      console.error('[mail] password reset failed', err);
    }
  }
  return done;
}

export async function resetPasswordAction(_prev: FormState, fd: FormData): Promise<FormState> {
  const token = str(fd, 'token');
  const password = str(fd, 'password');
  const error = validatePassword(password) ?? (password !== str(fd, 'password2') ? 'Hasła nie są takie same.' : null);
  if (error) return { error };

  const rows = await query<{ user_id: number }>(
    'SELECT user_id FROM password_resets WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?',
    [sha256(token), new Date()],
  );
  if (!rows[0]) return { error: 'Link wygasł lub został już użyty. Poproś o nowy.' };
  const userId = rows[0].user_id;

  await execute('UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?', [await bcrypt.hash(password, 10), new Date(), userId]);
  await execute('UPDATE password_resets SET used_at = ? WHERE user_id = ? AND used_at IS NULL', [new Date(), userId]);
  await destroyAllSessions(userId);
  redirect('/logowanie?haslo=zmienione');
}
