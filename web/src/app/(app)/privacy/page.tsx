import type { Metadata } from "next";
import Link from "next/link";

import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Privacy",
  description: "What PCRStudio stores, what it does not, and how to take your work out.",
};

/**
 * What is kept, what is not, and how to leave.
 *
 * Written as a description of what the software does rather than as a licence
 * to do things to somebody. Every claim here is one the code makes true and a
 * reader could check against the implementation, so anything this page cannot
 * point at is a sentence that does not belong on it.
 *
 * The deliberate omissions are the interesting part: there is no analytics
 * section because there is no analytics, and no third-party section because
 * there are no third parties. Saying so plainly is worth more than a longer
 * document that leaves the reader to infer it.
 */
export default function PrivacyPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Privacy"
        description="What is stored, what is not, and how to take your work out."
      />

      <Card className="workbench-card">
        <CardHeader>
          <CardTitle className="font-serif text-lg font-semibold">What is stored</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
          <p>
            <span className="text-foreground">Your account.</span> An email address, the name you
            chose to be called, and when the account was made. The address is used to sign you in
            and for nothing else — there is no newsletter, no verification email, and nothing is
            ever sent to it.
          </p>
          <p>
            <span className="text-foreground">Your password and recovery code.</span> Neither is
            stored. What is stored is an Argon2 hash of each, which is a one-way function: nobody
            can read either one back, including whoever runs the server. That is also why a
            forgotten password cannot be recovered without the code.
          </p>
          <p>
            <span className="text-foreground">Your projects.</span> The sequences you paste, the
            settings you choose, and every run you keep — including the request that produced each
            result, so a design can be reproduced rather than only read.
          </p>
          <p>
            <span className="text-foreground">Your sessions.</span> One row per signed-in browser,
            holding a hash of the session token and when it expires. Signing out everywhere deletes
            them, and it takes effect immediately rather than at the next expiry.
          </p>
        </CardContent>
      </Card>

      <Card className="workbench-card">
        <CardHeader>
          <CardTitle className="font-serif text-lg font-semibold">What is not stored</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
          <p>
            There is no analytics, no tracking, no advertising identifier and no third-party script.
            The Content-Security-Policy this site sends refuses to load one, which you can check in
            your browser rather than take on trust.
          </p>
          <p>
            Sequences pasted into the bench tools without a project are not written down at all.
            They are held in memory for as long as the calculation takes and are gone when the
            answer is returned.
          </p>
          <p>
            Server logs record the request, its outcome and a request id. They exist so a fault can
            be traced to a moment and do not carry the contents of a design.
          </p>
        </CardContent>
      </Card>

      <Card className="workbench-card">
        <CardHeader>
          <CardTitle className="font-serif text-lg font-semibold">
            Taking it with you, and deleting it
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
          <p>
            <Link href="/account" className="text-foreground underline underline-offset-4">
              Your account page
            </Link>{" "}
            has a download button that produces one JSON file holding every project and every saved
            run, with the request beside each result. It is enough to rebuild a design somewhere
            else, not just to read what this one said.
          </p>
          <p>
            The same page deletes the account. Deleting removes the account row, and every project,
            run and session hanging off it goes with it in the same transaction. There is no recycle
            bin and no thirty-day grace period: it is gone.
          </p>
        </CardContent>
      </Card>

      <Card className="workbench-card">
        <CardHeader>
          <CardTitle className="font-serif text-lg font-semibold">Where this runs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
          <p>
            PCRStudio is proprietary software. If this hosted instance is not one you want to trust
            with your sequences, contact the operator about an approved deployment or data-handling
            arrangement before uploading them.
          </p>
          <p>
            <Link
              href={site.repository}
              className="text-foreground underline underline-offset-4"
              rel="noreferrer noopener"
              target="_blank"
            >
              The project repository is here
            </Link>
            , including everything described on this page.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
