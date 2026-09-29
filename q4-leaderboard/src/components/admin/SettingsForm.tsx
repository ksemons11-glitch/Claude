'use client';

import { useActionState } from 'react';
import { updateSettingsAction } from '@/app/actions/admin';
import { FormMessage } from '../FormMessage';
import { SubmitButton } from '../SubmitButton';

export function SettingsForm(props: {
  name: string;
  motivationText: string;
  accessCodeRequired: boolean;
  hasCode: boolean;
  registrationOpen: boolean;
  isPublicLeaderboard: boolean;
}) {
  const [state, action] = useActionState(updateSettingsAction, undefined);
  const check = (name: string, label: string, def: boolean) => (
    <label className="flex items-center gap-3">
      <input type="checkbox" name={name} defaultChecked={def} className="h-5 w-5 accent-[#7cf29c]" />
      {label}
    </label>
  );
  return (
    <form action={action} className="space-y-4">
      <div>
        <label htmlFor="name" className="label">Nazwa eventu</label>
        <input id="name" name="name" defaultValue={props.name} required maxLength={120} className="input" />
      </div>
      <div>
        <label htmlFor="motivation_text" className="label">Komunikat motywacyjny (nagłówek)</label>
        <input id="motivation_text" name="motivation_text" defaultValue={props.motivationText} maxLength={255} className="input" />
      </div>
      <div>
        <label htmlFor="access_code" className="label">Nowy kod dostępu do eventu</label>
        <input id="access_code" name="access_code" autoComplete="off" placeholder={props.hasCode ? 'kod ustawiony — wpisz, aby zmienić' : 'brak kodu'} className="input" />
        <p className="mt-1 text-xs text-muted">Kod jest przechowywany w formie zaszyfrowanej, dlatego nie da się go tu podejrzeć — tylko ustawić nowy.</p>
      </div>
      <div className="space-y-3 rounded-xl border border-line p-4">
        {check('access_code_required', 'Wymagaj kodu dostępu przy rejestracji', props.accessCodeRequired)}
        {check('registration_open', 'Rejestracja otwarta', props.registrationOpen)}
        {check('is_public_leaderboard', 'Ranking widoczny bez logowania', props.isPublicLeaderboard)}
      </div>
      <FormMessage state={state} />
      <SubmitButton>Zapisz ustawienia</SubmitButton>
    </form>
  );
}
