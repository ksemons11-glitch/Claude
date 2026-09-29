import 'server-only';

function env(name: string, fallback = ''): string {
  return process.env[name]?.trim() || fallback;
}

export const config = {
  databaseUrl: env('DATABASE_URL'),
  databaseSsl: env('DATABASE_SSL', 'false') === 'true',
  appUrl: env('APP_URL', 'http://localhost:3000').replace(/\/$/, ''),
  eventSlug: env('EVENT_SLUG', 'q4-2026'),
  eventName: env('EVENT_NAME', 'Next Level Q4 Leaderboard'),
  eventAccessCode: env('EVENT_ACCESS_CODE'),
  q4Start: env('Q4_START', '2026-10-01'),
  q4End: env('Q4_END', '2026-12-31'),
  adminEmails: env('ADMIN_EMAILS')
    .split(',')
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean),
  termsUrl: env('TERMS_URL', '#'),
  privacyUrl: env('PRIVACY_URL', '#'),
  dataController: env('DATA_CONTROLLER', ''),
  contactEmail: env('CONTACT_EMAIL', ''),
  smtp: {
    host: env('SMTP_HOST'),
    port: Number(env('SMTP_PORT', '587')),
    user: env('SMTP_USER'),
    pass: env('SMTP_PASS'),
    from: env('MAIL_FROM'),
  },
  sendApprovalEmails: env('SEND_APPROVAL_EMAILS', 'true') === 'true',
  secureCookies: env('NODE_ENV') === 'production' && env('APP_URL').startsWith('https://'),
};
