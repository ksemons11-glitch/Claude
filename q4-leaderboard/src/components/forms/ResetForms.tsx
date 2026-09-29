'use client';

import { useActionState } from 'react';
import { requestPasswordResetAction, resetPasswordAction } from '@/app/actions/auth';
import { FormMessage } from '../FormMessage';
import { SubmitButton } from '../SubmitButton';

export function ResetRequestForm() {
  const [state, action] = useActionState(requestPasswordResetAction, undefined);
  if (state?.success) return <FormMessage state={state} />;
  return (
    <form action={action} className="space-y-4">
      <FormMessage state={state} />
      <div>
        <label htmlFor="email" className="label">E-mail konta</label>
        <input id="email" name="email" type="email" autoComplete="email" required className="input" defaultValue={state?.fields?.email} />
      </div>
      <SubmitButton pendingText="Wysyłanie…">Wyślij link</SubmitButton>
    </form>
  );
}

export function NewPasswordForm({ token }: { token: string }) {
  const [state, action] = useActionState(resetPasswordAction, undefined);
  return (
    <form action={action} className="space-y-4">
      <FormMessage state={state} />
      <input type="hidden" name="token" value={token} />
      <div>
        <label htmlFor="password" className="label">Nowe hasło (min. 8 znaków)</label>
        <input id="password" name="password" type="password" autoComplete="new-password" minLength={8} required className="input" />
      </div>
      <div>
        <label htmlFor="password2" className="label">Powtórz hasło</label>
        <input id="password2" name="password2" type="password" autoComplete="new-password" minLength={8} required className="input" />
      </div>
      <SubmitButton>Ustaw nowe hasło</SubmitButton>
    </form>
  );
}
