'use client';

import { useActionState } from 'react';
import { registerAction } from '@/app/actions/auth';
import { AvatarPicker } from '../AvatarPicker';
import { FormMessage } from '../FormMessage';
import { SubmitButton } from '../SubmitButton';

export function RegisterForm({
  presets,
  codeRequired,
  termsUrl,
  privacyUrl,
}: {
  presets: readonly string[];
  codeRequired: boolean;
  termsUrl: string;
  privacyUrl: string;
}) {
  const [state, action] = useActionState(registerAction, undefined);
  const f = state?.fields ?? {};
  return (
    <form action={action} className="space-y-5">
      <FormMessage state={state} />
      {codeRequired && (
        <div>
          <label htmlFor="access_code" className="label">Kod dostępu do eventu</label>
          <input id="access_code" name="access_code" required autoComplete="off" className="input" />
          <p className="mt-1 text-xs text-muted">Kod znajdziesz w zamkniętej grupie programu.</p>
        </div>
      )}
      <div>
        <label htmlFor="email" className="label">E-mail (prywatny, do logowania)</label>
        <input id="email" name="email" type="email" autoComplete="email" required className="input" defaultValue={f.email} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="password" className="label">Hasło (min. 8 znaków)</label>
          <input id="password" name="password" type="password" autoComplete="new-password" minLength={8} required className="input" />
        </div>
        <div>
          <label htmlFor="password2" className="label">Powtórz hasło</label>
          <input id="password2" name="password2" type="password" autoComplete="new-password" minLength={8} required className="input" />
        </div>
      </div>
      <div>
        <label htmlFor="discord" className="label">Nick z Discorda (prywatny)</label>
        <input id="discord" name="discord" required maxLength={40} className="input" defaultValue={f.discord} />
        <p className="mt-1 text-xs text-muted">Widzi go tylko organizator — służy do weryfikacji, że jesteś w programie.</p>
      </div>
      <div>
        <label htmlFor="nickname" className="label">Publiczny nick rankingowy</label>
        <input id="nickname" name="nickname" required minLength={3} maxLength={24} className="input" defaultValue={f.nickname} />
        <p className="mt-1 text-xs text-muted">Ten nick zobaczą wszyscy w rankingu. Nie musi być Twoim imieniem.</p>
      </div>

      <AvatarPicker presets={presets} initialPreset={f.avatar_preset} />

      <div className="space-y-3 rounded-xl border border-line p-4">
        <label className="flex gap-3 text-sm">
          <input type="checkbox" name="terms" required className="mt-0.5 h-5 w-5 shrink-0 accent-accent" />
          <span>
            Akceptuję{' '}
            <a href={termsUrl} target="_blank" rel="noopener noreferrer" className="link">regulamin eventu</a> oraz{' '}
            <a href={privacyUrl} target="_blank" rel="noopener noreferrer" className="link">politykę prywatności</a>.
          </span>
        </label>
        <label className="flex gap-3 text-sm">
          <input type="checkbox" name="public_consent" required className="mt-0.5 h-5 w-5 shrink-0 accent-accent" />
          <span>Zgadzam się na publiczne wyświetlanie mojego pseudonimu, awatara i deklarowanego wyniku w rankingu.</span>
        </label>
      </div>

      <SubmitButton pendingText="Zakładanie konta…">Załóż konto</SubmitButton>
    </form>
  );
}
