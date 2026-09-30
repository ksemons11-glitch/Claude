import 'server-only';
import type { EventInfo, UserRow } from './data';

export const isAdminUser = (user: UserRow | null) => user?.role === 'admin' && user.status === 'active';

/** Message for a blocked write, or null when saving is allowed. Admins are never blocked. */
export function writeBlockedMessage(event: EventInfo, user: UserRow | null): string | null {
  if (event.maintenanceMode === 'off' || isAdminUser(user)) return null;
  return event.maintenanceMessage || 'Trwają prace techniczne — zapisywanie jest chwilowo wstrzymane. Spróbuj ponownie za chwilę.';
}

/** Whether the whole site is closed for this visitor. */
export function siteClosedFor(event: EventInfo, user: UserRow | null): boolean {
  return event.maintenanceMode === 'closed' && !isAdminUser(user);
}
