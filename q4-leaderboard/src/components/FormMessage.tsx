import type { FormState } from '@/app/actions/types';

export function FormMessage({ state }: { state: FormState }) {
  if (state?.error) return <p role="alert" className="alert-error">{state.error}</p>;
  if (state?.success) return <p role="status" className="alert-success">{state.success}</p>;
  return null;
}
