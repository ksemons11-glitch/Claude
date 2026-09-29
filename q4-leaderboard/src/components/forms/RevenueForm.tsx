'use client';

import { useActionState } from 'react';
import { requestCorrectionAction, saveRevenueAction } from '@/app/actions/participant';
import { formatPln } from '@/lib/validation';
import { FormMessage } from '../FormMessage';
import { SubmitButton } from '../SubmitButton';

function CorrectionForm({ value }: { value: number }) {
  const [state, action] = useActionState(requestCorrectionAction, undefined);
  if (state?.success) return <FormMessage state={state} />;
  return (
    <form action={action} className="mt-4 space-y-3 rounded-xl border border-line p-4">
      <p className="text-sm font-semibold">Zgłoś korektę do organizatora</p>
      <FormMessage state={state} />
      <div>
        <label htmlFor="requested_value" className="label">Prawidłowy łączny przychód od początku Q4</label>
        <input id="requested_value" name="requested_value" inputMode="decimal" required className="input" defaultValue={String(value)} />
      </div>
      <div>
        <label htmlFor="message" className="label">Co się stało? (opcjonalnie)</label>
        <textarea id="message" name="message" maxLength={500} rows={3} className="input py-3" placeholder="Np. w zeszłym tygodniu wpisałem o jedno zero za dużo." />
      </div>
      <SubmitButton className="btn-ghost w-full" pendingText="Wysyłanie…">Wyślij zgłoszenie</SubmitButton>
    </form>
  );
}

export function RevenueForm({ current, previous }: { current: number | null; previous: number }) {
  const [state, action] = useActionState(saveRevenueAction, undefined);
  return (
    <>
      <form action={action} className="space-y-4">
        <div>
          <label htmlFor="revenue" className="label">Łączny przychód od początku Q4 (PLN)</label>
          <div className="relative">
            <input
              id="revenue"
              name="revenue"
              inputMode="decimal"
              autoComplete="off"
              required
              placeholder="np. 25 000"
              className="input pr-14 text-2xl font-bold tabular-nums"
              defaultValue={state?.fields?.revenue ?? (current !== null ? String(current) : '')}
            />
            <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 font-semibold text-muted">zł</span>
          </div>
          <p className="mt-1.5 text-xs text-muted">
            Wpisz całą sprzedaż od 1 października do dziś — nie tylko z tego tygodnia. System sam policzy Twój tygodniowy przyrost.
            {previous > 0 && <> Ostatnio zgłoszone (poprzednie tygodnie): <b className="text-white">{formatPln(previous)}</b>.</>}
          </p>
        </div>
        <FormMessage state={state} />
        <SubmitButton>Zapisz wynik</SubmitButton>
      </form>
      {state?.correctionFor !== undefined && <CorrectionForm value={state.correctionFor} />}
    </>
  );
}
