# Pre-Commit Hooks Setup

## What Are Pre-Commit Hooks?

Pre-commit hooks are automated checks that run **before** you commit code to Git. They catch issues early, ensuring code quality and consistency before changes reach CI/CD.

## Installation

Pre-commit hooks are already configured for this project. To set them up:

```bash
# Install pre-commit (if not already installed)
pip install pre-commit

# Install the git hooks
pre-commit install
```

## What Gets Checked

The following checks run automatically on every commit:

### 1. **General File Checks**
- Trailing whitespace removal
- End-of-file fixing
- YAML/JSON validation
- Large file detection (max 1MB)
- Merge conflict detection
- Private key detection

### 2. **Python Code Quality**
- **Black**: Code formatting (88 char line length)
- **isort**: Import statement organization
- **flake8**: Linting and style checks
- **bandit**: Security vulnerability scanning

### 3. **Docker & YAML**
- **hadolint**: Dockerfile best practices
- **yamllint**: YAML file linting

## Usage

### Automatic (on commit)
Hooks run automatically when you commit:

```bash
git add .
git commit -m "Your commit message"
# Pre-commit hooks run here automatically
```

### Manual (check all files)
Run checks on all files without committing:

```bash
pre-commit run --all-files
```

### Manual (specific files)
Run checks on staged files only:

```bash
git add services/chat/app/app.py
pre-commit run
```

### Skip hooks (emergency only)
If you absolutely need to skip hooks (not recommended):

```bash
git commit -m "Emergency fix" --no-verify
```

## Common Issues & Fixes

### Issue: Trailing whitespace or end-of-file errors
**Fix**: Pre-commit auto-fixes these. Just re-stage and commit:
```bash
git add .
git commit -m "Your message"
```

### Issue: Black formatting changes
**Fix**: Black auto-formats your code. Review changes, then re-stage:
```bash
git add .
git commit -m "Your message"
```

### Issue: isort reorders imports
**Fix**: isort auto-fixes import order. Re-stage the changes:
```bash
git add .
git commit -m "Your message"
```

### Issue: flake8 errors (not auto-fixed)
**Fix**: Manually fix the reported issues in your code:
- Unused imports: Remove them
- Line too long: Break into multiple lines
- Undefined names: Fix typos or add imports

### Issue: bandit security warnings
**Fix**: Review the security concern:
- Add `# nosec` comment if it's a false positive
- Fix the actual security issue (e.g., add timeout to HTTP requests)

Example fix for httpx timeout:
```python
# Before
async with httpx.AsyncClient() as client:
    response = await client.post(url, json=data)

# After
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.post(url, json=data)
```

### Issue: YAML syntax errors
**Fix**: Check your YAML file for proper indentation and syntax:
```bash
# View specific line causing error
cat -n .github/workflows/ci.yml | grep -A 2 -B 2 <line_number>
```

## Updating Hooks

Update to the latest hook versions:

```bash
pre-commit autoupdate
```

## Disabling Specific Hooks

Edit `.pre-commit-config.yaml` and comment out unwanted hooks:

```yaml
# Disable Markdown linting (example)
# - repo: https://github.com/igorshubovych/markdownlint-cli
#   rev: v0.39.0
#   hooks:
#     - id: markdownlint
```

## Benefits

✅ **Catch issues early** - Before they reach CI/CD
✅ **Consistent formatting** - Automatic code formatting
✅ **Security scanning** - Detect vulnerabilities locally
✅ **Faster feedback** - No need to wait for CI pipeline
✅ **Prevent broken commits** - Tests run before commit

## Workflow Integration

Pre-commit hooks complement your existing CI/CD pipeline:

```
Local Development → Pre-commit hooks → Git commit → Push → CI/CD pipeline
                    (fast, instant)                          (slower, comprehensive)
```

- **Pre-commit**: Fast checks on changed files
- **CI/CD**: Full test suite, coverage, deployment

## Configuration

The configuration file is `.pre-commit-config.yaml` in the project root. Customize it to add or remove hooks based on your needs.

## Troubleshooting

### Hooks not running?
```bash
# Reinstall hooks
pre-commit uninstall
pre-commit install
```

### Slow first run?
The first run installs all hook environments (takes 2-3 minutes). Subsequent runs are fast (seconds).

### Docker not available for hadolint?
If Docker is not installed, you can disable the hadolint hook:
```yaml
# Comment out in .pre-commit-config.yaml
# - repo: https://github.com/hadolint/hadolint
```

## Additional Resources

- [Pre-commit Documentation](https://pre-commit.com/)
- [Black Documentation](https://black.readthedocs.io/)
- [flake8 Documentation](https://flake8.pycqa.org/)
- [Bandit Documentation](https://bandit.readthedocs.io/)

---

For questions or issues, refer to the main [Testing Guide](../tests/TEST_INFO.md) or open a GitHub issue.
