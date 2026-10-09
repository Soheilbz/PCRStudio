# Experience contract

Projects is the landing page. The workspace selector stays visible on desktop/mobile. Bottom navigation separates Account from Workspace settings. Organization Members manages membership; Project Access manages grants. Scientific Tools, Runs, files and billing appear only when implemented.

## Core journeys

1. A researcher signs up, verifies their email and reaches their empty personal Projects page. New project is the single primary action.
2. They create and save a project. Save status is explicit. Refresh restores server data; conflicts keep their unsaved input and explain the next action.
3. They enroll MFA and create an organization. Organization projects remain private; membership alone does not grant access.
4. An organization owner invites a colleague. The colleague verifies the invited email and accepts membership. A project owner separately grants viewer/editor access.
5. A member is removed. Subsequent access fails immediately. If a project loses its owner, authorized members can read it and see why editing is unavailable. The organization owner performs a separate, audited recovery to an active member.

## State and interaction floor

Fields have labels, hints and inline validation. Preserve values on failure. Buttons expose pending/disabled reasons; prevent duplicate submissions. Lists have loading/empty/error/populated states without fabricated counts. Menus/dialogs use accessible Base UI primitives, Escape, focus containment and focus return. Navigation and forms work with keyboard, visible focus and reduced motion. Target WCAG2.2 AA; automated checks are not a conformance certification.

Clear identity-scoped query caches and cancel pending queries on sign-out/workspace changes. Never use prior workspace data as a loading placeholder. No offline persistence of scientific data in browser storage; theme preference may be stored locally. Explain operations with ordinary language, not implementation details. Do not present simulation as scientific output.
