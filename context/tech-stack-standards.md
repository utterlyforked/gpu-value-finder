# Technical Architecture & Stack Standards

**Version**: 1.0  
**Last Updated**: [Date when you customize this]

> ⚠️ **Customize this file for your organization before using the framework.**
> This template uses .NET/React as an example. Replace with your preferred stack.

## Philosophy

- Boring technology that works > shiny new frameworks that break
- Convention over configuration
- Optimize for reading code, not writing it
- Security by default
- Everything in a container so it can be ran locally in docker and then used in production with k8s or similar

## Core Stack

### Backend

**Framework**: ASP.NET Core 8.0 (LTS)  
**Language**: C# 12  
**Database**: PostgreSQL 16+  
**ORM**: Entity Framework Core 8  

### Frontend

**Framework**: React 18+ with TypeScript  
**Build Tool**: Vite  
**State Management**: TanStack Query + Context API  
**Styling**: Tailwind CSS  

### Testing

**Backend**: xUnit + FluentAssertions + NSubstitute  
**Frontend**: Vitest + React Testing Library  
**E2E**: Playwright  

### Infrastructure

**Caching**: Redis  
**Background Jobs**: Hangfire  
**File Storage**: Azure Blob Storage (or S3)  
**Monitoring**: Application Insights  

## Code Standards

### C#

- Nullable reference types enabled project-wide
- Use `record` for DTOs and value objects
- Async/await everywhere (no `.Result` or `.Wait()`)
- Code-first migrations only

### TypeScript

- Strict mode enabled
- No `any` types
- Functional components only
- Props interfaces for all components

### API Design

- RESTful with `/api/v1/` prefix
- RFC 7807 ProblemDetails for errors
- JWT authentication via HttpOnly cookies
- OpenAPI/Swagger documentation

## What We Don't Use

- ❌ Stored Procedures (business logic in code)
- ❌ Microservices (monolith until proven otherwise)
- ❌ Redux (React Query is sufficient)
- ❌ localStorage for tokens (security risk)

## More Details

For comprehensive standards, see:
- [API Guidelines](./api-guidelines.md) - if you create this
- [Database Patterns](./database-patterns.md) - if you create this
- [Testing Strategy](./testing-strategy.md) - if you create this

---

**Note**: This file is referenced by all agents. Keep it current as your stack evolves.
