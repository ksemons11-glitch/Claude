import { AuthShell } from '@/components/AuthShell';
import { ResetRequestForm } from '@/components/forms/ResetForms';

export default function ResetPage() {
  return (
    <AuthShell title="Nie pamiętasz hasła?" subtitle="Podaj e-mail — wyślemy link do ustawienia nowego hasła.">
      <ResetRequestForm />
    </AuthShell>
  );
}
