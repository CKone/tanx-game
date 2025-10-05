# Continuous Integration Overview

## Local test workflow
- Install dev dependencies: `python -m pip install -r requirements-dev.txt`
- Run the deterministic gameplay tests: `python -m pytest --maxfail=1 --disable-warnings`

## GitHub Actions pipeline
The workflow in `.github/workflows/ci.yml` runs on pushes and pull requests targeting `main` and performs the following steps:
1. Checks out the repository on Ubuntu runners.
2. Sets up Python 3.11 and caches `pip` downloads based on `requirements*.txt` files.
3. Installs base and development dependencies (if the respective requirement files are present).
4. Executes the pytest suite and fails the build on the first failing test.

## Branch protection suggestions
To require the CI checks before merging to `main`:
1. Open *Settings → Branches* in your GitHub repository.
2. Add or edit a protection rule for `main`.
3. Enable **Require status checks to pass before merging** and select the `CI / tests` workflow.
4. Optionally require pull request reviews and up-to-date branches.

## Future improvements
- Add smoke/end-to-end tests once a headless front-end or simulation harness is available.
- Track coverage output (e.g., `pytest --cov`) and enforce thresholds via an additional status check.
- Extend the matrix to multiple Python versions or OS targets when portability becomes a concern.
- Integrate linting and static analysis (`ruff`, `mypy`) into the same workflow or dedicated jobs.
