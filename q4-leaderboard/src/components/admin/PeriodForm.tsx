'use client';

import { useActionState } from 'react';
import { updatePeriodAction } from '@/app/actions/admin';
import { FormMessage } from '../FormMessage';
import { SubmitButton } from '../SubmitButton';

export function PeriodForm({ id, startsAt, entryDeadline, endsAt }: { id: number; startsAt: string; entryDeadline: string; endsAt: string }) {
  const [state, action] = useActionState(updatePeriodAction, undefined);
  return (
    <form action={action} className="grid gap-2 sm:grid-cols-[1fr_1fr_1fr_auto] sm:items-end">
      <input type="hidden" name="id" value={id} />
      <label className="text-xs text-muted">
        Początek
        <input type="datetime-local" name="starts_at" defaultValue={startsAt} required className="input mt-1 min-h-[40px]" />
      </label>
      <label className="text-xs text-muted">
        Termin wpisów
        <input type="datetime-local" name="entry_deadline" defaultValue={entryDeadline} required className="input mt-1 min-h-[40px]" />
      </label>
      <label className="text-xs text-muted">
        Zamknięcie edycji
        <input type="datetime-local" name="ends_at" defaultValue={endsAt} required className="input mt-1 min-h-[40px]" />
      </label>
      <SubmitButton className="btn-sm min-h-[40px] border border-line">Zapisz</SubmitButton>
      {state && (
        <div className="sm:col-span-4">
          <FormMessage state={state} />
        </div>
      )}
    </form>
  );
}
