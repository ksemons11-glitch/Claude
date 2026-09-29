import Link from 'next/link';

export function AuthShell({ title, subtitle, children }: { title: string; subtitle?: React.ReactNode; children: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-md px-4 pb-16 pt-8">
      <Link href="/" className="text-sm text-muted hover:text-white">← Ranking</Link>
      <h1 className="mt-4 text-2xl font-extrabold tracking-tight">{title}</h1>
      {subtitle && <div className="mt-1.5 text-muted">{subtitle}</div>}
      <div className="mt-6">{children}</div>
    </main>
  );
}
