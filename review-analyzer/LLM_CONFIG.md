# LLM API Configuration

This document explains how the LLM API key is securely managed in the application.

## Security Model: Environment Variables + .gitignore

The application uses **pydantic-settings** to load configuration from a `.env` file, with secrets protected from version control.

### ✓ What's Secure

1. **LLM_API_KEY is NOT in git** - `.env` is in `.gitignore`
2. **Settings loaded at runtime** - From environment or `.env` file
3. **Type-safe validation** - Pydantic ensures config is valid
4. **Flexible sourcing** - Works with `.env` files OR environment variables

### How It Works

```
1. Application starts
   ↓
2. Settings module reads from:
   - Environment variables (priority)
   - .env file (fallback)
   - defaults (for optional fields)
   ↓
3. Pydantic validates all required fields present
   ↓
4. Settings available app-wide via: from app.settings import settings
```

## Configuration

### Required Variables

```bash
LLM_API_KEY=your_actual_api_key_here
```

### Optional Variables (Have Defaults)

```bash
LLM_PROVIDER=anthropic           # Default: "anthropic"
LLM_MODEL=claude-opus-4-8        # Default: "claude-opus-4-8"
```

## Setup Instructions

### For Development

1. Copy `.env.example` to `.env` (or create `.env` directly):
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your real API key:
   ```bash
   LLM_API_KEY=sk_YOUR_REAL_KEY_HERE
   ```

3. The `.env` file is in `.gitignore`, so it won't be committed

### For Production

Set environment variables directly on your deployment platform:

**Docker:**
```dockerfile
ENV LLM_API_KEY=your_production_key
```

**Kubernetes:**
```yaml
env:
  - name: LLM_API_KEY
    valueFrom:
      secretKeyRef:
        name: llm-secrets
        key: api-key
```

**AWS Lambda / Heroku / etc.:**
Use your platform's secrets management system to set environment variables.

## Accessing Settings in Code

```python
from app.settings import settings

# Get the API key
api_key = settings.llm_api_key

# Get other settings
provider = settings.llm_provider
model = settings.llm_model
```

## Verification

### Check that settings load correctly
```bash
python -m pytest tests/test_settings.py -v
```

Expected output:
```
[OK] LLM_API_KEY loaded: sk_test_placeholder_...
[OK] Settings loaded from .env file
[OK] .env is in .gitignore
```

### Verify .env is NOT in git
```bash
# Should return empty (no results)
git log -p --all | grep "sk_test\|LLM_API_KEY"

# Should show .env is gitignored
git check-ignore -v "review-analyzer/.env"
```

## Implementation Details

### Code Structure

- **[app/settings.py](app/settings.py)** - Settings definition and loader
  - Uses `BaseSettings` from pydantic-settings
  - Loads from `.env` file with fallback to environment
  - Type-safe validation with Field descriptors

- **[tests/test_settings.py](tests/test_settings.py)** - Security verification
  - Test: LLM_API_KEY loads from environment
  - Test: All required fields present
  - Test: .env file is gitignored
  - Test: No keys in git history

- **[.env](.env)** - Configuration (NOT in git)
  - Contains placeholder/development values
  - Should be replaced with real values in each environment

- **[.gitignore](.gitignore)** - Prevents .env from being committed
  - Blocks `.env`, `.env.local`, `.env.*.local`
  - Prevents accidental secret leaks

### Why This Approach?

| Aspect | Why |
|--------|-----|
| **pydantic-settings** | Type-safe, automatic env parsing, integrated with Pydantic validation |
| **.env files** | Simple development workflow, doesn't require complex setup |
| **.gitignore** | Prevents accidental commits of secrets |
| **Environment variables** | Works in production (Docker, Kubernetes, Heroku, etc.) without needing files |
| **Type validation** | Catch config errors early (missing required fields) |

## Troubleshooting

### Error: `Field required [type=missing, input_value=...]`

**Problem:** LLM_API_KEY not found in environment or `.env` file

**Solution:**
1. Check `.env` file exists: `ls -la review-analyzer/.env`
2. Check it has `LLM_API_KEY=...`: `grep LLM_API_KEY review-analyzer/.env`
3. Check you're in the right directory when running: `pwd`
4. Restart Python/IDE to reload .env changes

### Error: `ValueError: api key must start with sk_`

**Problem:** API key format invalid

**Solution:**
- Get real API key from your provider (Anthropic, OpenAI, etc.)
- Ensure it's properly formatted

### Settings not updating after .env change

**Problem:** Python cached the old settings

**Solution:**
- Restart your Python process (uvicorn server, pytest, etc.)
- Settings are loaded once at import time

## Security Checklist

Before deploying to production:

- [ ] Set `LLM_API_KEY` environment variable in production
- [ ] Never commit `.env` file (verify with `git status`)
- [ ] Verify `.env` is in `.gitignore`
- [ ] Run `git log -p | grep -i "api_key"` to confirm no keys in history
- [ ] Rotate any keys that were accidentally committed (unlikely but possible)
- [ ] Use platform-specific secrets management (not plain env vars if possible)

## See Also

- [pydantic-settings documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [OWASP: Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [Twelve-Factor App: Store Config in Environment](https://12factor.net/config)
