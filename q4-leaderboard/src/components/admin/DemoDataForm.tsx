'use client';

import { useActionState } from 'react';
import { removeDemoAction, seedDemoAction } from '@/app/actions/admin';
import { FormMessage } from '../FormMessage';
import { SubmitButton } from '../SubmitButton';

export function DemoDataForm({ count }: { count: number }) {
  const [seedState, seed] = useActionState(seedDemoAction, undefined);
  const [removeState, remove] = useActionState(removeDemoAction, undefined);
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">
        50 fikcyjnych uczestników z przychodami z pierwszych 3 tygodni (5 z nich „dołącza” w 2. tygodniu). Są widoczni w rankingu dla
        wszystkich — <b className="text-white">usuń je przed startem</b>. Nikt nie może się na nie zalogować.
      </p>
      <p className="text-sm">
        Obecnie kont testowych: <b>{count}</b>
      </p>
      <FormMessage state={seedState ?? removeState} />
      <div className="grid gap-2 sm:grid-cols-2">
        <form action={seed}>
          <SubmitButton className="btn-primary w-full" pendingText="Tworzenie…">Wygeneruj 50 kont testowych</SubmitButton>
        </form>
        <form action={remove}>
          <SubmitButton className="btn-ghost w-full" pendingText="Usuwanie…">Usuń konta testowe</SubmitButton>
        </form>
      </div>
    </div>
  );
}
