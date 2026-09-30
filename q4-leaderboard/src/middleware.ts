import { NextResponse, type NextRequest } from 'next/server';

// Passes the requested path to server components (the maintenance gate in the root
// layout needs it to keep the login page reachable for admins).
export function middleware(req: NextRequest) {
  const headers = new Headers(req.headers);
  headers.set('x-pathname', req.nextUrl.pathname);
  return NextResponse.next({ request: { headers } });
}

export const config = {
  matcher: ['/((?!_next/|api/|avatars/|brand/|icon|favicon).*)'],
};
