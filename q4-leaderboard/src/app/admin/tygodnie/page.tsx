import { addPeriodAction, togglePeriodLockAction } from '@/app/actions/admin';
import { PeriodForm } from '@/components/admin/PeriodForm';
import { getEvent, getPeriods } from '@/lib/data';
import { currentPeriodState } from '@/lib/periods';
import { toLocalInput } from '@/lib/time';

export default async function PeriodsPage() {
  const event = await getEvent();
  const periods = await getPeriods(event.id);
  const now = new Date();
  const state = currentPeriodState(periods, now);

  return (
    <div>
      <h1 className="text-2xl font-extrabold">Tygodnie raportowe</h1>
      <p className="mt-1 text-sm text-muted">
        Czas polski. Wpisy trafiają do tygodnia trwającego w chwili zapisu. Po „zamknięciu edycji” uczestnicy nie mogą już zmienić wyniku
        tego tygodnia — tydzień możesz też zamknąć ręcznie wcześniej.
      </p>
      <ul className="mt-4 grid gap-3">
        {periods.map((p, i) => {
          const status = p.isLocked || now > p.endsAt ? 'zamknięty' : i === state.index && state.phase === 'running' ? 'trwa' : 'przyszły';
          return (
            <li key={p.id} className={`card p-4 ${status === 'trwa' ? 'border-accent/50' : ''}`}>
              <div className="mb-3 flex items-center justify-between gap-2">
                <div className="font-bold">
                  Tydzień {p.weekNumber}{' '}
                  <span className={`ml-1 text-xs font-semibold ${status === 'trwa' ? 'text-accent' : 'text-muted'}`}>{status}</span>
                </div>
                <form action={togglePeriodLockAction}>
                  <input type="hidden" name="id" value={p.id} />
                  <input type="hidden" name="locked" value={p.isLocked ? '0' : '1'} />
                  <button className="btn-sm border border-line">{p.isLocked ? 'Odblokuj ręcznie' : 'Zamknij teraz'}</button>
                </form>
              </div>
              <PeriodForm
                id={p.id}
                startsAt={toLocalInput(p.startsAt)}
                endsAt={toLocalInput(p.endsAt)}
              />
            </li>
          );
        })}
      </ul>
      <form action={addPeriodAction} className="mt-4">
        <button className="btn-ghost w-full">+ Dodaj kolejny tydzień</button>
      </form>
    </div>
  );
}
