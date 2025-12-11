
# README for pyproject.toml

This file (`pyproject.toml`) is the central configuration for Python tooling in this project. It defines settings for build systems, dependencies, and code quality tools.

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

Tools used in this project:

| Tool     | Version | Purpose           | What it does                                      |
|----------|---------|-------------------|---------------------------------------------------|
| flake8   | 7.3.0   | Linting           | Style guide enforcement (PEP 8), logical errors   |
| black    | 25.11.0 | Formatting        | Opinionated code formatter (no config needed)     |
| isort    | 7.0.0   | Import sorting    | Organises imports alphabetically by type          |
| mypy     | 1.19.0  | Type checking     | Static type analysis using type hints             |
| bandit   | 1.9.2   | Security scanning | Scans code for common security issues             |
| safety   | 3.7.0   | Security scanning | Checks dependencies for known vulnerabilities     |
| pytest-cov | 5.0.0 | Local Test coverage| Local coverage reporting for pytest |
| Codecov | - | Cloud Test coverage  | Cloud service that collecs coverage reports |

### Type Stubs
| Package          | Version              | Purpose                              |
|------------------|----------------------|--------------------------------------|
| types-requests   | 2.31.0.20240406      | Type stubs for requests library      |
| types-aiofiles   | 23.2.0.20240403      | Type stubs for aiofiles library      |

## Key Sections

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

The CI pipeline runs multiple jobs in parallel using Python 3.11 (and 3.10, 3.12 for tests):

### Lint Job (Python 3.11)
1. **Checkout:** `actions/checkout@v4` (checks out the repository)
2. **Setup Python:** `actions/setup-python@v5` with Python 3.11
3. **Install tools:** `pip install flake8==7.3.0 black==25.11.0 isort==7.0.0`
4. **Check formatting:** `black --check .`
5. **Check imports:** `isort --check-only .`
6. **Lint:** `flake8 services/`

### Type-Check Job (Python 3.11)
1. **Checkout:** `actions/checkout@v4`
2. **Setup Python:** `actions/setup-python@v5` with Python 3.11
3. **Install mypy:** `pip install mypy==1.19.0`
4. **Install type stubs:** `pip install types-requests==2.31.0.20240406 types-aiofiles==23.2.0.20240403`
5. **Type check:** `mypy services/`

### Security-Scan Job (Python 3.11)
1. **Checkout:** `actions/checkout@v4`
2. **Setup Python:** `actions/setup-python@v5` with Python 3.11
3. **Install tools:** `pip install bandit==1.9.2 safety==3.7.0`
4. **Code security scan:** `bandit -r services/`
5. **Dependency security scan:** `safety check --policy-file .github/workflows/.safety-policy.yml -r [all service requirements files]`

### Unit-Tests Job (Matrix: Python 3.10, 3.11, 3.12)
Runs unit tests with coverage across multiple Python versions in parallel.
- **Coverage tools:** `pytest-cov==5.0.0 coverage==7.5.1`

### Integration-Tests Job
Starts Docker services (RabbitMQ, Qdrant, all microservices), waits for health checks, and runs integration tests.

### Build Job
Builds Docker images for all services and verifies service health endpoints.

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
