# README for pyproject.toml

This file (`pyproject.toml`) is the central configuration for Python tooling in this project. It defines settings for build systems, dependencies, and code quality tools.

## What is Code Quality?

Code quality refers to how well code meets standards for readability, maintainability, consistency, correctness, and security.

### Code Quality Dimensions
- **Readability:** Can others understand the code?
- **Maintainability:** Can the code be easily modified?
- **Consistency:** Does the code follow team standards?
- **Correctness:** Does the code do what it should?
- **Security:** Are there vulnerabilities?

### Why Automate Code Quality?
- Consistency across team members
- Early feedback (before code review)
- Reduces bikeshedding in reviews
- Catches issues humans miss
- Documents team standards

## Code Quality Tool Categories

Four main categories:
1. **Linters:** Find potential bugs and style issues
   - Python: flake8, pylint, ruff
   - JavaScript: ESLint
   - Java: Checkstyle, SpotBugs
2. **Formatters:** Enforce consistent code style
   - Python: black, isort
   - JavaScript: Prettier
   - Java: Google Java Format
3. **Type Checkers:** Catch type errors before runtime
   - Python: mypy
   - JavaScript: TypeScript
4. **Security Scanners:** Find vulnerabilities
   - Python: bandit, safety
   - JavaScript: npm audit
   - Java: OWASP Dependency-Check

## Python Tools Overview

Recommended Python toolchain:

| Tool    | Purpose      | What it does                                      |
|---------|--------------|---------------------------------------------------|
| flake8  | Linting      | Style guide enforcement (PEP 8), logical errors   |
| black   | Formatting   | Opinionated code formatter (no config needed)     |
| isort   | Import sort  | Organises imports alphabetically by type          |
| mypy    | Type checking| Static type analysis using type hints             |
| bandit  | Security     | Scans code for common security issues             |
| safety  | Security     | Checks dependencies for known vulnerabilities     |
| ruff    | All-in-one   | Fast linter + formatter (alternative)             |

## Key Sections

- **[tool.poetry] / [project]**: Project metadata, dependencies, and build configuration.
- **[tool.flake8]**: Linting configuration for code style and error checks.
- **[tool.black]**: Formatting configuration for automatic code style enforcement.
- **[tool.mypy]**: Type checking configuration for static analysis.
- **[tool.pylint]**: Additional static analysis and bug detection settings.
- **[tool.coverage]**: Test coverage reporting configuration.

## Running Tools Locally

To ensure code quality and consistency, run the following commands locally before committing changes:

### Linting
```
flake8 src/ tests/
```

### Formatting (apply changes)
```
black src/ tests/
isort src/ tests/
```

### Formatting (check only, for CI)
```
black --check src/ tests/
isort --check-only src/ tests/
```

### Type Checking
```
mypy src/
```

### Security Scanning
```
bandit -r src/
safety scan -r requirements.txt
```

## CI Workflow Steps

The CI pipeline runs multiple jobs in parallel:

### Lint Job
1. **Checkout:** `actions/checkout` (checks out the repository)
2. **Setup Python:** `actions/setup-python` with Python 3.11
3. **Install tools:** `pip install flake8 black isort`
4. **Check formatting:** `black --check .`
5. **Check imports:** `isort --check-only .`
6. **Lint:** `flake8 services/`

### Type-Check Job
1. **Checkout:** `actions/checkout`
2. **Setup Python:** `actions/setup-python` with Python 3.11
3. **Install mypy:** `pip install mypy`
4. **Install type stubs:** `pip install types-requests types-aiofiles`
5. **Type check:** `mypy services/`

### Security-Scan Job
1. **Checkout:** `actions/checkout`
2. **Setup Python:** `actions/setup-python` with Python 3.11
3. **Install tools:** `pip install bandit safety`
4. **Code security scan:** `bandit -r services/`
5. **Dependency security scan:** `safety scan -r [all requirements files]`

### Unit-Tests Job
Runs unit tests with coverage across Python 3.10, 3.11, and 3.12.

### Integration-Tests Job
Starts Docker services, waits for health checks, and runs integration tests.

### Build Job
Builds Docker images and verifies service health endpoints.

**Tip:** Jobs run in parallel where possible. If any job fails, dependent jobs are skipped.

## Why these tools were chosen

- **flake8 (Linting):** Chosen for its maturity, extensive plugin ecosystem, and clear, actionable feedback. Integrates well with CI/CD and is highly configurable. While `ruff` is faster and gaining popularity, `flake8` offers more granular control and compatibility with established plugins, making it preferable for larger or more complex projects.

- **black (Formatting):** Selected for its simplicity and ability to enforce a consistent code style automatically. Requires minimal configuration and is widely accepted in the Python community, making it a reliable choice over alternatives like `yapf` or `autopep8`.

- **mypy (Type Checking):** Preferred for its robust static type checking and seamless integration with modern Python codebases. Helps catch type errors before runtime, whereas alternatives like `pyright` are less commonly used in Python projects.

- **bandit (Security Scanning):** Chosen for its ability to detect common security issues in Python code such as SQL injection, hardcoded passwords, and weak cryptographic practices. Lightweight and easy to integrate into CI/CD pipelines.

- **safety (Dependency Security):** Selected for checking installed dependencies against known security vulnerabilities in the Safety DB and CVE databases. Helps maintain secure dependencies by identifying packages with known exploits.

- **pylint (Bug Detection):** Used for its deeper static analysis, detection of code smells, unused variables, and potential bugs. Complements `flake8` by covering additional checks and providing more detailed reports than tools like `pyflakes`.

- **coverage.py (Test Coverage):** Chosen for its industry-standard status, ease of use, and integration with most test runners and CI systems. Provides reliable coverage reports, making it preferable over less feature-rich alternatives.

## Why use pyproject.toml?

- Centralizes configuration for multiple tools.
- Simplifies dependency management and tool setup.
- Ensures reproducible builds and consistent code quality standards.

## How to use

- Install dependencies and tools using your preferred package manager (e.g., Poetry, pip).
- Run linting, formatting, type checking, and tests using the commands specified in your workflow or documentation.

For more details, refer to the documentation of each tool or the main project README.
