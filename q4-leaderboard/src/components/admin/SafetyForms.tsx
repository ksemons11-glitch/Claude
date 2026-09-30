'use client';

import { useActionState, useState } from 'react';
import { createBackupAction, restoreBackupAction, setMaintenanceAction } from '@/app/actions/admin';
import type { MaintenanceMode } from '@/lib/data';
import { FormMessage } from '../FormMessage';
import { SubmitButton } from '../SubmitButton';

export function MaintenanceForm({ mode, message }: { mode: MaintenanceMode; message: string }) {
  const [state, action] = useActionState(setMaintenanceAction, undefined);
  const options: { value: MaintenanceMode; label: string; hint: string }[] = [
    { value: 'off', label: 'Normalna praca', hint: 'Wszystko działa.' },
    {
      value: 'readonly',
      label: 'Tylko odczyt (zamrożenie)',
      hint: 'Ranking widać, ale nikt poza adminami nie może się rejestrować, wpisywać wyników ani zmieniać profilu.',
    },
    { value: 'closed', label: 'Przerwa techniczna', hint: 'Uczestnicy i goście widzą tylko komunikat. Admini mogą się zalogować i pracować.' },
  ];
  return (
    <form action={action} className="space-y-3">
      {options.map((o) => (
        <label key={o.value} className="flex cursor-pointer gap-3 rounded-2xl border border-line p-3 has-[:checked]:border-accent">
          <input type="radio" name="mode" value={o.value} defaultChecked={mode === o.value} className="mt-1 h-5 w-5 accent-accent" />
          <span>
            <span className="block font-semibold">{o.label}</span>
            <span className="block text-sm text-muted">{o.hint}</span>
          </span>
        </label>
      ))}
      <div>
        <label htmlFor="message" className="label">Komunikat dla uczestników (opcjonalnie)</label>
        <input id="message" name="message" maxLength={255} defaultValue={message} placeholder="Np. Aktualizujemy ranking, wracamy o 21:00." className="input" />
      </div>
      <FormMessage state={state} />
      <SubmitButton>Zapisz tryb</SubmitButton>
    </form>
  );
}

export function CreateBackupForm() {
  const [state, action] = useActionState(createBackupAction, undefined);
  return (
    <form action={action} className="space-y-3">
      <FormMessage state={state} />
      <div className="grid gap-2 sm:grid-cols-2">
        <SubmitButton className="btn-primary w-full" pendingText="Tworzenie…">Utwórz kopię teraz</SubmitButton>
        <a href="/api/admin/backup?id=current" className="btn-ghost w-full">Pobierz aktualny stan na dysk</a>
      </div>
    </form>
  );
}

function ConfirmFields() {
  return (
    <>
      <input name="confirm" required placeholder="Wpisz PRZYWRÓĆ" className="input min-h-[40px]" autoComplete="off" />
      <label className="flex items-center gap-2 text-xs text-muted">
        <input type="checkbox" name="force" className="h-4 w-4 accent-accent" />
        Rozumiem, że obecne dane zostaną zastąpione (aktualny stan zapisze się automatycznie jako kopia).
      </label>
    </>
  );
}

export function RestoreBackupForm({ id }: { id: number }) {
  const [open, setOpen] = useState(false);
  const [state, action] = useActionState(restoreBackupAction, undefined);
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="btn-sm border border-line">
        Przywróć…
      </button>
    );
  }
  return (
    <form action={action} className="mt-2 w-full space-y-2">
      <input type="hidden" name="id" value={id} />
      <ConfirmFields />
      <FormMessage state={state} />
      <SubmitButton className="btn-sm min-h-[40px] w-full bg-accent text-accent-fg" pendingText="Przywracanie…">Przywróć tę kopię</SubmitButton>
    </form>
  );
}

export function RestoreUploadForm() {
  const [state, action] = useActionState(restoreBackupAction, undefined);
  return (
    <form action={action} className="space-y-3">
      <input name="file" type="file" accept="application/json,.json" required className="block w-full text-sm text-muted file:mr-3 file:rounded-full file:border-0 file:bg-white/10 file:px-4 file:py-2 file:text-white" />
      <ConfirmFields />
      <FormMessage state={state} />
      <SubmitButton className="btn-ghost w-full" pendingText="Przywracanie…">Przywróć z pliku</SubmitButton>
    </form>
  );
}
