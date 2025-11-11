
## Build, Lint, and Test

- **Linting**: This project uses `ruff` for linting and formatting.
- **Auto-formatting**: Run `ruff format .` to format the code.
- **Pre-commit Hooks**: `ruff` is configured to run as a pre-commit hook to automatically format and lint files.
- **Testing**: There are no automated tests in this project.

## Code Style Guidelines

- **Formatting**: Adhere to the `ruff` formatting standards, which are largely PEP 8 compliant.
- **Line Length**: Maximum line length is 100 characters.
- **Imports**: Imports are automatically sorted by `ruff`.
- **Naming Conventions**: Follow standard Python naming conventions (e.g., `snake_case` for functions and variables, `PascalCase` for classes).
- **Types**: Use type hints where possible.
- **Error Handling**: Use standard Python error handling with `try...except` blocks.
