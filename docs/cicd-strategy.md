# CI/CD Strategy

## Objective
Create a safe and incremental delivery pipeline for a monorepo containing:
- frontend web application
- backend API
- shared documentation and configuration

## Deployment Targets
- Frontend: Vercel
- Backend: Google Cloud Run
- Database: Heroku Postgres

## Branch Strategy
Recommended branches:
- `main`: production-ready branch
- `develop`: integration branch for ongoing work
- feature branches: one slice or feature per branch

## CI Principles
Every pull request should validate quality before merge.

Minimum validations:
- lint
- type checks
- tests
- build verification

## CD Principles
Deployments should happen only after code has been validated.

### Frontend
Recommended approach:
- Vercel GitHub integration for preview and production deployments
- GitHub Actions still runs lint, tests, and build checks

### Backend
Recommended approach:
- GitHub Actions for tests and deployment to Cloud Run
- Containerized deployment using Docker

## Path-Based Execution
Pipelines should run selectively depending on changed paths.

### Backend pipeline triggers
Run when files change in:
- `apps/api/**`
- shared backend-relevant config
- workflow files affecting backend

### Frontend pipeline triggers
Run when files change in:
- `apps/web/**`
- shared frontend-relevant config
- workflow files affecting frontend

### Shared packages
If shared packages affect both applications, both validations should run.

## Environments
At minimum:
- local
- development
- production

Optional future improvement:
- preview/staging backend environment

## Secrets Management
Do not store secrets in the repository.

Use:
- GitHub Secrets for CI/CD variables
- Vercel environment variables for frontend
- Google Cloud secrets or GitHub Secrets for backend deployment credentials
- Cloud Run environment variables for runtime backend configuration

## Backend CI Flow
On pull request:
1. install dependencies
2. lint
3. run tests
4. verify app can build/start

On merge to `develop`:
1. run tests
2. build Docker image
3. deploy to development backend environment

On merge to `main`:
1. run tests
2. build Docker image
3. deploy to production backend environment

## Frontend CI Flow
On pull request:
1. install dependencies
2. lint
3. type-check
4. test
5. build

On merge to `develop` or `main`:
- Vercel handles deployment through GitHub integration

## Required Safeguards
- never deploy backend if tests fail
- avoid automatic production deploys from unreviewed branches
- keep workflow scopes narrow and understandable

## MVP Recommendation
For the earliest phase:
- activate CI first
- activate backend CD once local setup is stable
- use Vercel native deployment integration for frontend
- avoid overcomplicated release workflows initially
