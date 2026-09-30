import Link from 'next/link';
import { getCurrentUser } from '@/lib/auth';
import { avatarUrl } from '@/lib/data';
import { logoutAction } from '@/app/actions/auth';
import { Avatar } from './Avatar';

export async function Header({ wide = false }: { wide?: boolean }) {
  const user = await getCurrentUser();
  return (
    // Light bar with the black Next Level logo, as on nextlevel-marketing.pl.
    <header className="sticky top-0 z-30 border-b border-black/10 bg-header/95 text-header-fg backdrop-blur">
      <div className={`mx-auto flex h-16 ${wide ? 'max-w-5xl' : 'max-w-3xl'} items-center justify-between gap-3 px-4`}>
        <Link href="/" className="flex min-w-0 items-center gap-3" aria-label="Next Level — ranking Q4">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/brand/next-level-logo.png" alt="Next Level" width={65} height={40} className="h-10 w-auto shrink-0" />
          <span className="h-7 w-px shrink-0 bg-black/15" aria-hidden />
          <span className="truncate font-display text-[15px] font-extrabold leading-tight tracking-tight">
            Q4 <span className="text-accent">Leaderboard</span>
          </span>
        </Link>
        {user ? (
          <details className="relative">
            <summary className="flex cursor-pointer list-none items-center gap-2 rounded-full p-1 hover:bg-black/5">
              <Avatar src={avatarUrl(user)} size={34} />
              <span className="sr-only">Menu profilu</span>
            </summary>
            <nav className="card absolute right-0 mt-2 w-56 overflow-hidden p-1 text-white shadow-2xl">
              <div className="truncate px-3 py-2 text-sm text-muted">{user.publicNickname}</div>
              <Link href="/konto" className="block rounded-xl px-3 py-2.5 hover:bg-white/5">Mój wynik</Link>
              <Link href="/konto/profil" className="block rounded-xl px-3 py-2.5 hover:bg-white/5">Profil</Link>
              {user.role === 'admin' && (
                <Link href="/admin" className="block rounded-xl px-3 py-2.5 hover:bg-white/5">Panel administratora</Link>
              )}
              <form action={logoutAction}>
                <button type="submit" className="block w-full rounded-xl px-3 py-2.5 text-left text-accent-2 hover:bg-white/5">
                  Wyloguj
                </button>
              </form>
            </nav>
          </details>
        ) : (
          <Link href="/logowanie" className="btn-sm shrink-0 whitespace-nowrap bg-gradient-to-br from-accent to-accent-2 text-accent-fg">
            Zaloguj się
          </Link>
        )}
      </div>
    </header>
  );
}
