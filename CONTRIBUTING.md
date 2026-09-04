# Contributing to HHGR (Hierarchical Hybrid Graph-RAG)

Thank you for your interest in contributing to HHGR.

## Development Setup

1. Clone the repository
2. Install backend dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and configure your API keys
4. Start the backend: `uvicorn src.main:app --reload`
5. Start the frontend: `cd ui && npm install && npm run dev`

## Code Quality

- **Linting**: Run `ruff check src/` before committing
- **Tests**: Run `python -m pytest tests/` — all 908 backend tests must pass
- **Frontend tests**: Run `cd ui && npm test` — all 49 tests must pass
- **Type checking**: Run `cd ui && npx tsc --noEmit` for frontend types

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with clear commit messages
3. Ensure all tests pass and linting is clean
4. Update documentation if your change affects user-facing behavior
5. Submit a pull request with a clear description of the change

## Reporting Issues

Open an issue on GitHub with:
- A clear title and description
- Steps to reproduce (if applicable)
- Expected vs actual behavior
- Environment details (Python version, Node version, OS)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
