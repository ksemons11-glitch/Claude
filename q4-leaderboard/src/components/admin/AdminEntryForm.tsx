'use client';

import { useActionState } from 'react';
import { adminSetEntryAction } from '@/app/actions/admin';
import { FormMessage } from '../FormMessage';
import { SubmitButton } from '../SubmitButton';

export function AdminEntryForm({
  userId,
  periodId,
  value,
  correctionId,
  defaultReason = '',
}: {
  userId: number;
  periodId: number;
  value: number | null;
  correctionId?: number;
  defaultReason?: string;
}) {
  const [state, action] = useActionState(adminSetEntryAction, undefined);
  return (
    <form action={action} className="grid gap-2 sm:grid-cols-[1fr_1.5fr_auto] sm:items-start">
      <input type="hidden" name="user_id" value={userId} />
      <input type="hidden" name="period_id" value={periodId} />
      {correctionId && <input type="hidden" name="correction_id" value={correctionId} />}
      <input name="value" inputMode="decimal" defaultValue={value ?? ''} placeholder="kwota (puste = usuń)" className="input min-h-[40px]" aria-label="Wynik narastający" />
      <input name="reason" required defaultValue={defaultReason} placeholder="Powód korekty (wymagany)" className="input min-h-[40px]" aria-label="Powód" />
      <SubmitButton className="btn-sm min-h-[40px] bg-accent text-bg">Zapisz</SubmitButton>
      {state && (
        <div className="sm:col-span-3">
          <FormMessage state={state} />
        </div>
      )}
    </form>
  );
}
