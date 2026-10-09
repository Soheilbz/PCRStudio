# PCRStudio design system

English web application. Warm, restrained visual language inspired by the user's Anthropic preference. System sans-serif body/controls, Georgia for selected page headings, system monospace for identifiers/data. No external font requests.

| Token | Light | Dark |
| --- | --- | --- |
| canvas | #F7F5F0 | #1F1D1A |
| sidebar | #EFEBE3 | #24211D |
| surface | #FFFDFA | #2B2824 |
| text | #2D2B26 | #F2EFE7 |
| secondary | #69645B | #B6AEA4 |
| action | #A24D32 | #D18A6D |
| action-label | #FFF8F2 | #211814 |
| input-border | #847C70 | #8B8174 |

Body 16px, secondary text at least 14px. Spacing uses 4px increments; 8px control and 12px card radii. Desktop sidebar 248px, header 56px, main content max 1200px. Below 1024px use a labelled drawer. At 320px preserve 16px page padding and essential actions; tables scroll within labelled regions. Prefer 44px touch targets. Theme follows OS until explicitly changed. Validate actual rendered contrast, focus, error and disabled states in both themes.

Use borders, readable typography and spacing rather than decorative gradients/glass. Selected labels use ordinary foreground. Status uses text plus icons, never color alone.
