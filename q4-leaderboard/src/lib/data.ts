import 'server-only';
import { cache } from 'react';
import { config } from './config';
import { query } from './db';
import type { Period } from './periods';

export type EventInfo = {
  id: number;
  name: string;
  slug: string;
  motivationText: string;
  accessCodeHash: string | null;
  accessCodeRequired: boolean;
  registrationOpen: boolean;
  isPublicLeaderboard: boolean;
  startsAt: Date;
  endsAt: Date;
};

export type UserStatus = 'pending' | 'active' | 'rejected' | 'suspended' | 'deleted';

export type UserRow = {
  id: number;
  email: string;
  discordNickname: string;
  publicNickname: string;
  avatarPreset: string | null;
  avatarFile: string | null;
  role: 'participant' | 'admin';
  status: UserStatus;
  deletionRequestedAt: Date | null;
  createdAt: Date;
};

export function userColumns(alias = ''): string {
  const t = alias ? `${alias}.` : '';
  return `${t}id, ${t}email, ${t}discord_nickname AS discordNickname, ${t}public_nickname AS publicNickname,
    ${t}avatar_preset AS avatarPreset, ${t}avatar_file AS avatarFile, ${t}role, ${t}status,
    ${t}deletion_requested_at AS deletionRequestedAt, ${t}created_at AS createdAt`;
}

export const AVATAR_PRESETS = [
  'rocket', 'crown', 'fire', 'bolt', 'star', 'gem', 'chart', 'target',
  'trophy', 'coffee', 'fox', 'lion', 'owl', 'shark', 'cactus', 'planet',
] as const;

export function avatarUrl(u: { avatarPreset: string | null; avatarFile: string | null }): string {
  if (u.avatarFile) return `/api/avatar/${u.avatarFile}`;
  const preset = AVATAR_PRESETS.includes(u.avatarPreset as (typeof AVATAR_PRESETS)[number]) ? u.avatarPreset : 'rocket';
  return `/avatars/${preset}.svg`;
}

export const getEvent = cache(async (): Promise<EventInfo> => {
  const rows = await query<Record<string, unknown>>(
    `SELECT id, name, slug, motivation_text, access_code_hash, access_code_required, registration_open,
            is_public_leaderboard, starts_at, ends_at
     FROM events WHERE slug = ?`,
    [config.eventSlug],
  );
  const r = rows[0];
  if (!r) throw new Error('Event not found');
  return {
    id: Number(r.id),
    name: String(r.name),
    slug: String(r.slug),
    motivationText: String(r.motivation_text ?? ''),
    accessCodeHash: (r.access_code_hash as string | null) ?? null,
    accessCodeRequired: Boolean(r.access_code_required),
    registrationOpen: Boolean(r.registration_open),
    isPublicLeaderboard: Boolean(r.is_public_leaderboard),
    startsAt: r.starts_at as Date,
    endsAt: r.ends_at as Date,
  };
});

export const getPeriods = cache(async (eventId: number): Promise<Period[]> => {
  const rows = await query<Record<string, unknown>>(
    `SELECT id, week_number, starts_at, ends_at, entry_deadline, is_locked
     FROM reporting_periods WHERE event_id = ? ORDER BY week_number`,
    [eventId],
  );
  return rows.map((r) => ({
    id: Number(r.id),
    weekNumber: Number(r.week_number),
    startsAt: r.starts_at as Date,
    endsAt: r.ends_at as Date,
    entryDeadline: r.entry_deadline as Date,
    isLocked: Boolean(r.is_locked),
  }));
});
