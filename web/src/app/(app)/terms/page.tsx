import type { Metadata } from "next";
import Link from "next/link";

import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Terms",
  description: "What PCRStudio promises, what it does not, and what it expects of you.",
};

/**
 * The terms, kept to what is actually true.
 *
 * The temptation on this page is to copy a template that disclaims everything
 * and asserts every right. Most of that would be a lie here — there is no
 * arbitration venue, no data processor, nothing sold — and a document that says
 * untrue things about a tool is worse than a short one that says true things.
 *
 * The section that matters is the scientific one. This designs primers; it does
 * not know whether they work, and no amount of careful thermodynamics changes
 * that a reaction is an experiment. Saying so is not a disclaimer dressed up as
 * modesty, it is the single most important thing on the page.
 */
export default function TermsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Terms"
        description="What this promises, what it does not, and what it asks of you."
      />

      <Card className="workbench-hero border-primary/40">
        <CardHeader>
          <CardTitle className="font-serif text-lg font-semibold">
            What a design here is, and is not
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
          <p className="text-foreground">
            PCRStudio predicts. It does not test. Every primer it produces is a prediction from a
            thermodynamic model, and the only thing that establishes whether a reaction works is
            running it.
          </p>
          <p>
            The models are good and their limits are real. A melting temperature is computed for the
            buffer you specified — get that wrong and the number is right about a reaction nobody is
            running. A specificity scan is only as complete as the background sequence you gave it.
            A design checked against nothing is reported as checked against nothing, which is the
            honest answer and not a passing grade.
          </p>
          <p>
            Nothing here is validated for clinical or diagnostic use. If a result matters to
            somebody&apos;s treatment, it needs the validation that context requires, and this tool
            is not it.
          </p>
        </CardContent>
      </Card>

      <Card className="workbench-card">
        <CardHeader>
          <CardTitle className="font-serif text-lg font-semibold">Your work is yours</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
          <p>
            The sequences you paste and the designs you keep belong to you. Nothing is claimed over
            them, nothing is sold, and nothing is shared with anybody. They are stored so you can
            come back to them and for no other purpose.
          </p>
          <p>
            You are responsible for having the right to use the sequences you put in — this cannot
            tell whose they are, and it does not ask.
          </p>
        </CardContent>
      </Card>

      <Card className="workbench-card">
        <CardHeader>
          <CardTitle className="font-serif text-lg font-semibold">What is asked of you</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
          <p>
            One account per person, and do not automate against the design endpoints. They fork a
            real search rather than reading something back, and there is a rate limit in front of
            them for that reason. If you need a larger workload or a separate deployment, contact
            the operator for an approved arrangement rather than copying or redistributing the
            source.
          </p>
          <p>
            Do not use this to design anything intended to cause harm. That is stated plainly rather
            than buried, and it is the only prohibition on this page.
          </p>
        </CardContent>
      </Card>

      <Card className="workbench-card">
        <CardHeader>
          <CardTitle className="font-serif text-lg font-semibold">What is not promised</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
          <p>
            This is proprietary software offered without warranty, under the repository license.
            There is no uptime commitment, no support contract and no guarantee that this instance
            will still be here next year.
          </p>
          <p>
            Which is exactly why{" "}
            <Link href="/account" className="text-foreground underline underline-offset-4">
              your account page
            </Link>{" "}
            has an export button, and why{" "}
            <Link
              href={site.repository}
              className="text-foreground underline underline-offset-4"
              rel="noreferrer noopener"
              target="_blank"
            >
              the project repository
            </Link>{" "}
            contains the project documentation and contact channels. Export your work regularly so
            you retain a copy of your data.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
