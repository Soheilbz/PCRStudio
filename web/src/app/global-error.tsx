"use client";

import { useEffect } from "react";

/** Last-resort fallback when even the root layout cannot render. */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en">
      <body>
        <main
          style={{
            boxSizing: "border-box",
            maxWidth: 720,
            margin: "0 auto",
            padding: "48px 20px",
            fontFamily: "system-ui, sans-serif",
          }}
        >
          <h1>PCRStudio could not render this page</h1>
          <p>An unexpected application error occurred. No internal error details are shown here.</p>
          {error.digest ? <p>Reference: {error.digest}</p> : null}
          <button
            type="button"
            onClick={reset}
            style={{
              marginTop: 12,
              minHeight: 40,
              padding: "8px 14px",
              border: "1px solid currentColor",
              borderRadius: 8,
              background: "transparent",
              color: "inherit",
              font: "inherit",
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
