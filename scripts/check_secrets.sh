#!/bin/bash
# Check for secrets before commit

echo "🔍 Checking for hardcoded secrets..."

# Check for common patterns
patterns=(
    "sk-[a-zA-Z0-9]{40,}"  # API keys
    "AKIA[0-9A-Z]{16}"      # AWS keys
    "(?i)api[_-]?key.*=.*['\"][a-zA-Z0-9]{32,}"
    "(?i)secret.*=.*['\"][a-zA-Z0-9]{16,}"
    "-----BEGIN.*PRIVATE KEY-----"
)

found_secrets=0

for pattern in "${patterns[@]}"; do
    if grep -r -E "$pattern" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.toml" --include="*.json" --exclude-dir=".venv" --exclude-dir="venv" --exclude-dir=".git" --exclude="*.example" . 2>/dev/null; then
        echo "❌ Found potential secret matching pattern: $pattern"
        found_secrets=1
    fi
done

# Check .env file doesn't have real values
if [ -f .env ]; then
    if grep -E "=['\"]?[a-zA-Z0-9]{20,}" .env | grep -v "^#" 2>/dev/null; then
        echo "❌ Found potential secrets in .env file"
        found_secrets=1
    fi
fi

if [ $found_secrets -eq 0 ]; then
    echo "✅ No secrets found!"
else
    echo "⚠️  Please remove secrets before committing!"
    exit 1
fi