import { SettingsForm } from '@/components/admin/SettingsForm';
import { getEvent } from '@/lib/data';
import { countDemoAccounts } from '@/lib/demo';
import { DemoDataForm } from '@/components/admin/DemoDataForm';

export default async function SettingsPage() {
  const [e, demoCount] = await Promise.all([getEvent(), countDemoAccounts()]);
  return (
    <div className="max-w-xl">
      <h1 className="mb-4 text-2xl font-extrabold">Ustawienia eventu</h1>
      <div className="card p-5">
        <SettingsForm
          name={e.name}
          motivationText={e.motivationText}
          accessCodeRequired={e.accessCodeRequired}
          hasCode={Boolean(e.accessCodeHash)}
          registrationOpen={e.registrationOpen}
          isPublicLeaderboard={e.isPublicLeaderboard}
        />
      </div>
      <h2 className="mb-3 mt-8 text-lg font-bold">Dane testowe</h2>
      <div className="card p-5">
        <DemoDataForm count={demoCount} />
      </div>
    </div>
  );
}
