# Frontend Conventions

## Stack
- Next.js
- TypeScript
- Responsive web application
- Mobile-first approach

## Frontend Goals
The frontend must be:
- fast
- clear
- responsive
- clinically practical
- easy to extend
- easy to test

## UX Priorities
The product is for veterinary clinical workflows.
The UI must optimize:
- quick access to patients
- easy consultation registration
- low-friction navigation
- readable clinical history
- efficient data entry on mobile and desktop

## Suggested Folder Structure
```text
apps/web/
├─ src/
│  ├─ app/
│  ├─ components/
│  ├─ features/
│  ├─ services/
│  ├─ hooks/
│  ├─ lib/
│  ├─ types/
│  └─ styles/
├─ public/
├─ package.json
└─ .env.example
```

## Feature Organization
Prefer feature-oriented structure where reasonable.

Examples:
- `features/auth`
- `features/patients`
- `features/owners`
- `features/consultations`
- `features/exams`
- `features/search`

## Component Rules
- Keep components focused and small.
- Separate presentational components from feature orchestration when useful.
- Avoid large monolithic screens with too much inline logic.
- Prefer composition over deep prop drilling.

## State Management
Guidelines:
- local UI state stays local
- server data should be managed predictably
- avoid unnecessary global state
- introduce shared state only when clearly justified

Do not add heavy state libraries unless the project actually needs them.

## Forms
- Use consistent form components.
- Validate early and clearly.
- Show actionable error messages.
- Prefer controlled complexity over overly generic form builders.

## Routing
- Keep routes clear and resource-oriented.
- Avoid unnecessarily deep route nesting.
- Design screens so a veterinarian can reach core actions quickly.

## Design System Direction
- Minimal, modern, clinical interface
- Good spacing and clear hierarchy
- Accessible contrast
- Large enough touch targets on mobile
- Predictable layout patterns

## Accessibility
- Use semantic HTML where possible.
- Ensure keyboard accessibility.
- Provide labels and helper text.
- Avoid color-only meaning for states.

## API Integration
- Keep API calls centralized.
- Avoid spreading fetch logic across unrelated components.
- Use typed contracts consistently.

## Testing
At minimum, cover:
- critical rendering states
- key user flows
- error and empty states

## Simplicity Rule
Do not over-engineer the UI architecture.
Build for clarity, speed, and maintainability first.
