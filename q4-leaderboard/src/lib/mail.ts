import 'server-only';
import nodemailer, { type Transporter } from 'nodemailer';
import { config } from './config';

let transporter: Transporter | null = null;

function getTransporter(): Transporter | null {
  if (!config.smtp.host) return null;
  transporter ??= nodemailer.createTransport({
    host: config.smtp.host,
    port: config.smtp.port,
    secure: config.smtp.port === 465,
    auth: config.smtp.user ? { user: config.smtp.user, pass: config.smtp.pass } : undefined,
  });
  return transporter;
}

export async function sendMail(to: string, subject: string, text: string): Promise<void> {
  const t = getTransporter();
  if (!t) {
    // Without SMTP configured (local development) the message goes to the server log.
    console.log(`[mail] to=${to} subject=${subject}\n${text}`);
    return;
  }
  await t.sendMail({ from: config.smtp.from || config.smtp.user, to, subject, text });
}
