import { Links, Meta, Outlet, Scripts, ScrollRestoration } from 'react-router';
import './styles.css';
export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="color-scheme" content="light dark" />
        <title>PCRStudio · Private projects</title>
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}
export function HydrateFallback() {
  return (
    <div className="boot" role="status">
      Opening PCRStudio…
    </div>
  );
}
export default function Root() {
  return <Outlet />;
}
export function ErrorBoundary() {
  return (
    <main className="auth-page">
      <div className="card">
        <h1>We couldn’t open this page</h1>
        <p>Please reload to try again.</p>
        <a className="button" href="/">
          Reload PCRStudio
        </a>
      </div>
    </main>
  );
}
