# Ralion frontend design guide

This is the implementation-facing UI reference for Ralion. It condenses the canonical design system in `stitch_ralion/stitch_ralion_ai_onboarding_companion/ralion_design_system_design.md` so future UI work has a single practical baseline.

## Product intent

Ralion is an AI onboarding companion for software engineers: it helps a person move from joining a project to making their first contribution.

The intended personality is **65% friendly onboarding companion, 35% serious developer tool**. Interfaces should feel supportive, calm, intelligent, trustworthy, clear, curious, technical, warm, and non-judgmental.

Avoid making the product feel like enterprise HR software, a Jira clone, a generic AI chatbot, or a playful/gamified consumer app.

## Non-negotiable interaction principles

1. **Companion before dashboard.** Make the next useful step obvious; do not lead with raw metrics.
2. **One obvious next action.** Each state needs one visually clear primary action. Secondary/destructive actions must not compete with it.
3. **Progressive disclosure.** Put details, advanced controls, and dense metadata behind the first useful layer.
4. **Evidence before AI authority.** Any AI-generated answer or recommendation must visibly expose its supporting citations or clearly say that evidence is limited/conflicting.
5. **Calm density.** Use professional density, hierarchy, and whitespace instead of decorative cards, aggressive color, or excessive shadows.

## Foundations

Use these values for new Ralion-facing UI unless a role-specific legacy shell must be preserved during an incremental migration.

| Token purpose | Value | Use |
|---|---:|---|
| Ink | `#111513` | Main text, deep accents |
| Surface | `#F7F8F5` | Warm page background |
| White | `#FFFFFF` | Cards and high-contrast layers |
| Border | `#E2E4DE` | Quiet separators and inputs |
| Sky light / main / dark | `#AFCDE4` / `#7EADD0` / `#4B83AD` | Guidance, project context, project citations |
| Green light / main / dark | `#B9DDB5` / `#78B878` / `#397B4A` | Progress, readiness, company-policy citations |
| Panda accent | `#C96F4A` | Logo/mascot cue only; use sparingly |

- UI font: `Plus Jakarta Sans`; use a system fallback only when it is unavailable.
- Code, identifiers, file paths, PR references, and compact metadata: `Geist Mono`.
- Display: `48px / 1.1`, tracking `-0.02em`.
- H1: `32px / 1.2`.
- Body: `16px / 1.6`.
- Labels/small text: `14px / 1.4`.
- Base spacing unit: `4px`; prefer `4, 8, 12, 16, 24, 32, 48, 64, 96`.
- Standard cards: `12px` radius; hero/large surfaces: `24px`; pills/buttons: fully rounded when the component shape calls for it.

## Layout and navigation

- Desktop application shells use a fixed **240px sidebar** with a top bar for breadcrumbs, context, and search/actions.
- Navigation is role-specific and must show only actions valid for that role. Member navigation centers on onboarding and Ask Ralion; PM navigation centers on project/people/plan management.
- Preserve user context in the URL when it matters: active project, selected PM view, task/detail state, and Chat project handoff must remain recoverable on refresh and shared links.
- Every signed-in shell must provide a clear way to switch project when applicable and sign out.
- Do not make a disabled future feature look like an available route or primary action.

## Components and state

### Buttons

- Use one primary CTA per decision area. It should communicate the next action in a verb phrase.
- Primary actions use the blue/green brand family; secondary actions use a quiet border/surface treatment.
- Destructive actions remain visually distinct but should not dominate normal workflow states.
- Loading, disabled, error, empty, and permission-denied states must be explicit and actionable.

### Tasks and onboarding

- Present tasks horizontally on desktop with status, title, concise context, and blocked state/action.
- Show progress as readiness and completed work, not XP, streaks, levels, or other gamification.
- Keep the current task and unblock path visually more prominent than aggregate reporting.

### Chat and AI evidence

- Use grounded chat: conversation on the left and an evidence/source reader on the right at desktop widths.
- Cite every factual AI claim where evidence is available. Citation chips identify source domain: **blue = project**, **green = policy**.
- Confidence is qualitative only: `Strong evidence`, `Limited evidence`, or `Conflicting evidence`; never invent numerical confidence percentages.
- The mascot/avatar represents the AI and should appear where Ralion is explaining or responding. Do not use it as decorative chrome.
- Preserve selected project context when moving into or out of Chat. Policy scope remains available as an intentional alternative.

## Visual treatment

- The logo is a minimal geometric red-panda symbol plus wordmark; use no gradients in the logo.
- Supporting illustrations should be editorial and minimal: thin strokes, pictogram-like forms, and the metaphor of a supportive green companion with a tentative blue engineer.
- Background decoration, if needed, is extremely subtle: faint grids, micro-dots, or soft haze to suggest chaos becoming clarity.
- Prefer whitespace and borders as separators. Use shadows only to establish real elevation (dialogs, drawers, source panel), never as routine decoration.
- Do not use purple/neon “AI” gradients, high-saturation visual noise, or excessive card nesting.

## Responsive behavior

- Desktop reference width is 1440px: full sidebar and multi-column layouts are appropriate.
- On mobile, navigation becomes a drawer or compact top-level action set; critical account/project actions must remain reachable.
- The evidence/source reader becomes a focused bottom sheet or full-screen overlay rather than an unreadably narrow second column.
- Task rows stack vertically while retaining status, title, and primary action order.
- Test all new interaction paths at desktop and mobile widths; no essential control may exist only in a hidden desktop sidebar.

## Accessibility and implementation guardrails

- Use semantic landmarks, real buttons for actions, and real links for navigation.
- Give icon-only controls accessible names and make dialogs/drawers keyboard-operable with a clear close action.
- Preserve visible focus states and sufficient contrast; color may reinforce a status/domain but must not be its only signal.
- Respect `prefers-reduced-motion`; animations should be short, informative, and nonessential.
- Reuse existing feature-local components and CSS modules before creating parallel UI primitives. Avoid a new global design system unless the task explicitly includes a migration.
- Frontend authorization is UX/routing guidance only. Keep backend authorization as the source of truth and build UI from stable session/API contracts.

## UI review checklist

Before handing off a UI change, verify:

- Does the screen make the user’s next useful action obvious?
- Is project, role, task, and Chat scope context preserved across transitions?
- Does AI output expose evidence or clearly state limited/conflicting evidence?
- Are primary, secondary, disabled, loading, empty, error, and denied states deliberate?
- Does the layout work at desktop and mobile widths without hiding essential actions?
- Does the visual language avoid generic chatbot, enterprise-HR, Jira, neon-AI, and gamified patterns?
