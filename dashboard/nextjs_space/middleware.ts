import { withAuth } from 'next-auth/middleware';

export default withAuth({
  pages: {
    signIn: '/login',
  },
});

export const config = {
  matcher: [
    '/((?!login|api/signup|api/auth|api/proxy|_next/static|_next/image|favicon\\.svg|og-image\\.png).*)',
  ],
};
