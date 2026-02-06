# Contributing to FrontDesk AI

Thank you for your interest in contributing to FrontDesk AI! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inspiring community for all. Please be respectful and constructive in all interactions.

### Our Standards

**Positive behavior includes:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

**Unacceptable behavior includes:**
- Harassment, trolling, or discriminatory comments
- Publishing others' private information
- Any conduct that could be considered inappropriate in a professional setting

---

## Getting Started

### Prerequisites

- Python 3.11+
- Git
- GitHub account
- Familiarity with FastAPI, Vue.js, and PostgreSQL

### Development Setup

1. **Fork the repository**
   ```bash
   # Click "Fork" on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/frontdesk-ai.git
   cd frontdesk-ai
   ```

2. **Add upstream remote**
   ```bash
   git remote add upstream https://github.com/stephenschoettler/frontdesk-ai.git
   ```

3. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Development dependencies
   ```

5. **Set up environment**
   ```bash
   cp .env.example .env
   # Fill in your API keys (see docs/INSTALLATION.md)
   ```

6. **Run database migrations**
   ```bash
   cd supabase
   supabase db push
   ```

7. **Run the server**
   ```bash
   python main.py
   ```

---

## How to Contribute

### Reporting Bugs

**Before submitting a bug report:**
1. Check the [issue tracker](https://github.com/stephenschoettler/frontdesk-ai/issues) for existing reports
2. Verify you're using the latest version
3. Try to reproduce the issue with minimal configuration

**How to submit a good bug report:**
1. Use a clear, descriptive title
2. Provide step-by-step reproduction instructions
3. Include actual vs. expected behavior
4. Add relevant logs, screenshots, or error messages
5. Specify your environment (OS, Python version, etc.)

**Bug report template:**
```markdown
## Description
Brief description of the issue

## Steps to Reproduce
1. Step one
2. Step two
3. ...

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: [e.g., Ubuntu 22.04]
- Python: [e.g., 3.11.5]
- FrontDesk AI Version: [e.g., commit hash or tag]

## Additional Context
Any other relevant information
```

### Suggesting Features

**Before suggesting a feature:**
1. Check if it's already been suggested
2. Consider if it fits the project's scope
3. Think about how it benefits most users

**Feature request template:**
```markdown
## Feature Description
Clear description of the feature

## Use Case
Why is this feature needed?

## Proposed Solution
How could this be implemented?

## Alternatives Considered
What other approaches did you consider?

## Additional Context
Any mockups, examples, or references
```

### Contributing Code

**Types of contributions we're looking for:**
- Bug fixes
- Feature implementations
- Performance improvements
- Documentation improvements
- Test coverage improvements
- Code refactoring
- UI/UX enhancements

---

## Development Workflow

### 1. Create a Branch

```bash
# Update your fork
git checkout main
git pull upstream main
git push origin main

# Create feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/issue-description
```

**Branch naming conventions:**
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Test improvements
- `chore/` - Maintenance tasks

### 2. Make Changes

- Write clean, readable code
- Follow the coding standards (see below)
- Add tests for new functionality
- Update documentation as needed
- Test your changes thoroughly

### 3. Commit Changes

```bash
git add .
git commit -m "feat: add calendar OAuth support"
```

See [Commit Messages](#commit-messages) for formatting guidelines.

### 4. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

---

## Coding Standards

### Python Style

**Follow PEP 8 with these specifics:**
- Line length: 100 characters (not 79)
- Use type hints for function signatures
- Use docstrings for public functions/classes
- Use f-strings for string formatting

**Code formatting:**
```bash
# We use ruff for formatting and linting
pip install ruff

# Format code
ruff format .

# Lint code
ruff check .

# Auto-fix issues
ruff check --fix .
```

**Example:**
```python
async def get_client_config(client_id: str) -> dict | None:
    """
    Retrieve client configuration from database.

    Args:
        client_id: UUID of the client

    Returns:
        Client configuration dict or None if not found

    Raises:
        DatabaseError: If database connection fails
    """
    supabase = get_supabase_client()
    result = supabase.table("clients").select("*").eq("id", client_id).execute()

    if result.data:
        return result.data[0]
    return None
```

### JavaScript/Vue.js Style

**Standards:**
- Use ES6+ features
- Use `const` by default, `let` when reassignment needed
- Use arrow functions for callbacks
- Use template literals for string interpolation
- Use Vue 3 Composition API

**Example:**
```javascript
const clientForm = ref({
  name: '',
  phone_number: '',
  calendar_id: '',
  tts_provider: 'cartesia'
});

const saveClient = async () => {
  try {
    const response = await fetch(`/api/clients/${clientForm.value.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(clientForm.value)
    });

    if (!response.ok) throw new Error('Save failed');

    alert('Client saved successfully!');
  } catch (error) {
    console.error('Error saving client:', error);
    alert('Failed to save client');
  }
};
```

### SQL Style

**Standards:**
- Use uppercase for SQL keywords
- Indent subqueries
- Use meaningful table aliases
- Add comments for complex queries

**Example:**
```sql
-- Get clients with active calls
SELECT
    c.id,
    c.name,
    c.phone_number,
    COUNT(con.id) as total_calls,
    SUM(con.duration) as total_minutes
FROM clients c
LEFT JOIN conversations con
    ON c.id = con.client_id
WHERE c.is_active = true
    AND con.created_at >= NOW() - INTERVAL '30 days'
GROUP BY c.id, c.name, c.phone_number
ORDER BY total_minutes DESC;
```

---

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=services --cov-report=html

# Run specific test file
pytest tests/test_calendar.py

# Run specific test
pytest tests/test_calendar.py::test_book_appointment
```

### Writing Tests

**Test file structure:**
```
tests/
├── test_calendar.py
├── test_llm_tools.py
├── test_supabase_client.py
└── conftest.py  # Shared fixtures
```

**Test example:**
```python
import pytest
from services.google_calendar import get_available_slots

@pytest.mark.asyncio
async def test_get_available_slots():
    """Test availability checking returns valid time slots"""
    slots = await get_available_slots(
        calendar_id="primary",
        start_time="2026-02-10T09:00:00-08:00",
        end_time="2026-02-10T17:00:00-08:00",
        client_id="test-client-id"
    )

    assert isinstance(slots, list)
    assert len(slots) > 0
    assert all('human_time' in slot for slot in slots)
    assert all('iso_start' in slot for slot in slots)
```

### Test Coverage Requirements

- Minimum 70% coverage for new code
- 100% coverage for critical paths (payment, auth, calendar booking)
- All bug fixes must include a regression test

---

## Documentation

### Code Documentation

**Docstrings required for:**
- All public functions
- All classes
- Complex algorithms
- Non-obvious code

**Format:**
```python
def complex_function(param1: str, param2: int = 10) -> dict:
    """
    One-line summary of function.

    Longer description if needed. Explain the purpose,
    any important behavior, and edge cases.

    Args:
        param1: Description of param1
        param2: Description of param2, defaults to 10

    Returns:
        Dictionary containing results with keys:
        - 'status': Operation status
        - 'data': Result data

    Raises:
        ValueError: If param1 is empty
        NetworkError: If API call fails

    Example:
        >>> result = complex_function("test", 20)
        >>> print(result['status'])
        'success'
    """
```

### Documentation Files

**Update when changing:**
- **README.md** - Project overview, quick start
- **docs/FEATURES.md** - Feature list and descriptions
- **docs/ARCHITECTURE.md** - System design
- **docs/API_REFERENCE.md** - API endpoints
- **CHANGELOG.md** - Version history

---

## Commit Messages

### Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `chore`: Maintenance tasks, dependencies

### Examples

```bash
feat(calendar): add OAuth authentication support

Implement Google OAuth 2.0 flow for per-client calendar authorization.
Users can now authorize calendar access with one click instead of
uploading service account keys.

Closes #42
```

```bash
fix(billing): correct balance deduction calculation

Balance was being deducted in minutes instead of seconds,
causing 60x overcharge.

Fixes #56
```

```bash
docs(api): add calendar OAuth endpoint documentation

Add API reference documentation for the new calendar OAuth endpoints:
- POST /api/clients/{id}/calendar/oauth/initiate
- GET /api/calendar/oauth/callback
```

---

## Pull Request Process

### Before Submitting

**Checklist:**
- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] Commit messages follow convention
- [ ] Branch is up to date with main
- [ ] No merge conflicts

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Related Issues
Closes #123, Relates to #456

## Testing
Describe how you tested these changes

## Screenshots
If applicable, add screenshots

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Commits follow convention
```

### Review Process

1. **Automated checks** must pass:
   - Tests
   - Linting
   - Type checking
   - Build (if applicable)

2. **Code review** by maintainer:
   - Code quality
   - Test coverage
   - Documentation
   - Security considerations

3. **Approval** required before merge

4. **Merge** by maintainer (squash or rebase)

### After Merge

- Delete your branch
- Update your fork
- Celebrate! 🎉

---

## Community

### Getting Help

- **GitHub Discussions** - Ask questions, share ideas
- **GitHub Issues** - Report bugs, request features
- **Discord** - Real-time chat (coming soon)

### Recognition

Contributors are recognized in:
- GitHub contributors list
- CHANGELOG.md release notes
- README.md acknowledgments

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

## Questions?

If you have questions about contributing, please:
1. Check existing documentation
2. Search closed issues/PRs
3. Ask in GitHub Discussions
4. Reach out to maintainers

**Thank you for making FrontDesk AI better! 🚀**
