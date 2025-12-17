# Contributing to Warframe Market Set Profit Analyzer

Thank you for your interest in contributing! This project is a modern full-stack application with a FastAPI backend and React frontend. This guide will help you contribute effectively.

## Project Architecture

This project follows a **clean architecture** pattern with clear separation of concerns:

```
Backend (Python/FastAPI)
├── app/
│   ├── api/routes/          # REST API endpoints
│   ├── core/                # Business logic (scoring, calculations)
│   ├── services/            # External API integrations
│   ├── models/              # Pydantic schemas
│   ├── db/                  # Database operations
│   └── config.py            # Configuration management

Frontend (React/TypeScript)
├── src/
│   ├── api/                 # API client & types
│   ├── components/          # Reusable UI components
│   ├── pages/               # Page-level components
│   ├── hooks/               # Custom React hooks
│   └── store/               # State management (Zustand)
```

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 22+
- Git

### Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/Warframe-Market-Set-Profit-Analyzer.git
   cd Warframe-Market-Set-Profit-Analyzer
   ```

2. **Start the Backend**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```
   Backend runs at http://localhost:8000

3. **Start the Frontend** (in a new terminal)
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Frontend runs at http://localhost:5173

4. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Guidelines

### Backend (Python/FastAPI)

#### Code Style
- Use type hints for all function parameters and return values
- Follow PEP 8 style guidelines
- Use async/await for I/O operations
- Keep functions focused on a single responsibility

#### Error Handling
```python
try:
    result = await some_operation()
    return result
except SpecificException as e:
    logger.error(f"Operation failed: {e}")
    raise HTTPException(status_code=500, detail="User-friendly message")
```

#### Adding New API Endpoints
1. Create route file in `backend/app/api/routes/`
2. Add router to `backend/app/api/router.py`
3. Define request/response schemas in `backend/app/models/schemas.py`

### Frontend (React/TypeScript)

#### Code Style
- Use TypeScript with strict mode
- Prefer functional components with hooks
- Use Tailwind CSS for styling
- Keep components small and focused

#### Component Structure
```typescript
interface Props {
  // Define props with TypeScript
}

export function ComponentName({ prop }: Props) {
  // Component logic
  return (
    // JSX
  );
}
```

#### State Management
- Use Zustand for global state (`src/store/`)
- Use TanStack Query for server state
- Keep local state in components when possible

## Contribution Areas

### High Priority
- **Test Coverage**: Add pytest tests for backend, Vitest for frontend
- **Performance**: Optimize API response times and bundle size
- **Documentation**: API documentation, inline code comments

### Feature Ideas
- Additional analysis metrics and visualizations
- Price history tracking and trend analysis
- User preferences persistence
- Export format options (CSV, Excel)

### Bug Fixes
- Check [GitHub Issues](https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/issues) for open bugs

## Pull Request Process

### Before Submitting

1. **Test your changes**
   ```bash
   # Backend tests
   cd backend && pytest

   # Frontend lint
   cd frontend && npm run lint

   # Frontend build
   npm run build
   ```

2. **Ensure code quality**
   - No linting errors
   - Type errors resolved
   - Existing functionality not broken

### PR Guidelines

1. Create focused PRs (one feature/fix per PR)
2. Include a clear description of changes
3. Reference related issues if applicable
4. Update documentation if needed

### PR Template

```markdown
## Description
Brief description of changes and motivation.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Performance improvement
- [ ] Documentation update
- [ ] Refactoring

## Testing
- [ ] Backend tests pass
- [ ] Frontend builds successfully
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project style
- [ ] No linting errors
- [ ] Existing functionality preserved
```

## Project-Specific Notes

### Rate Limiting
The backend implements rate limiting for Warframe Market API calls. When developing features that make API calls, respect the rate limiter in `backend/app/core/rate_limiter.py`.

### Scoring System
The scoring engine uses a multiplicative geometric model with strategy profiles. See `backend/app/core/scoring.py` and `backend/app/core/strategy_profiles.py` for implementation details.

### Cache System
Prime sets data is cached to reduce API calls. The cache manager is in `backend/app/core/cache_manager.py`.

## Getting Help

- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For questions and general discussion

## Code of Conduct

- Be respectful and constructive
- Help others learn and grow
- Focus on the code, not the person

---

**Thank you for contributing to the Warframe trading community!**
