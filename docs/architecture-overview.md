# Architecture Overview

## Architecture Style
Monorepo application with separated frontend and backend applications.

## Main Components
- `apps/web`: Next.js responsive frontend
- `apps/api`: FastAPI backend
- `PostgreSQL`: primary relational database
- `GitHub Actions`: CI/CD orchestration
- `Vercel`: frontend deployment
- `Google Cloud Run`: backend deployment
- `Heroku Postgres`: initial managed database

## Repository Approach
Single repository containing:
- product documentation
- frontend
- backend
- shared configuration
- CI/CD pipelines

## Deployment Strategy
### Frontend
- deployed independently on Vercel
- preview and production environments supported

### Backend
- containerized FastAPI app
- deployed on Google Cloud Run
- environment-based configuration

## Database Strategy
Initial:
- Heroku Postgres

Future:
- migrate to Cloud SQL or equivalent managed PostgreSQL if scale or latency becomes a concern

## Why This Stack
- fast MVP delivery
- modern DX
- good compatibility with CI/CD
- scalable path for future SaaS growth
- clear separation between frontend and backend responsibilities

## Backend Principles
- stateless services
- tenant-aware request processing
- explicit API contracts
- modular structure
- strong validation at API boundary

## Frontend Principles
- mobile-first responsive design
- feature-oriented structure
- clear separation between UI, state, and API integration
- predictable navigation
- accessibility-first components

## Key Architectural Constraint
The product must be designed as multi-tenant from day one, even if the first release serves only 3 pilot users.
