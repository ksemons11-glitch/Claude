'use client';

import Link from 'next/link';
import { useActionState } from 'react';
import { loginAction } from '@/app/actions/auth';
import { FormMessage } from '../FormMessage';
import { SubmitButton } from '../SubmitButton';

export function LoginForm() {
  const [state, action] = useActionState(loginAction, undefined);
  return (
    <form action={action} className="space-y-4">
      <FormMessage state={state} />
      <div>
        <label htmlFor="email" className="label">E-mail</label>
        <input id="email" name="email" type="email" autoComplete="email" required className="input" defaultValue={state?.fields?.email} />
      </div>
      <div>
        <label htmlFor="password" className="label">Hasło</label>
        <input id="password" name="password" type="password" autoComplete="current-password" required className="input" />
      </div>
      <SubmitButton pendingText="Logowanie…">Zaloguj się</SubmitButton>
      <div className="flex justify-between text-sm">
        <Link href="/reset-hasla" className="link">Nie pamiętam hasła</Link>
        <Link href="/rejestracja" className="link">Załóż konto</Link>
      </div>
    </form>
  );
}
