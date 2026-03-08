# GPU-First Strategy: Global Rules for Ollama Local (GPU0 + GPU1)

**Status**: ✅ **MANDATORY GLOBAL RULE** — All agents must follow

---

## 🎯 Core Principle

> **CPU TOKENS ARE MONEY. GPU IS FREE. USE GPU ALWAYS AND FIRST.**

Every LLM call must attempt GPU0/GPU1 before considering ANY cloud service (GitHub, OpenAI, Google, Anthropic, etc.).

---

## 📋 Hierarchy (Strict Order)

```
1. GPU0 (RTX 2060)      ← PRIMARY [11434]
   ├─ Try up to 3x with exponential backoff
   └─ Timeout: 30s per call
   
2. GPU1 (GTX 1050)      ← SECONDARY [11435]
   ├─ Try up to 3x with exponential backoff
   └─ Timeout: 30s per call
   
3. Cloud (FREE MODELS ONLY)    ← FALLBACK
   ├─ GPT-4o, GPT-4.1, GPT-5.1  ✓ Allowed
   ├─ Claude 3.5 Sonnet         ✗ Prohibited
   ├─ Claude Opus/Pro           ✗ Prohibited  
   ├─ Gemini Pro                ✗ Prohibited
   ├─ Gemini 2.0 Flash          ✓ Allowed (free tier only)
   └─ o3 family                 ✗ Prohibited
```

---

## 🔧 Implementation Rules

### Rule 1: Environment Variables (Non-Negotiable)
```bash
# ALWAYS set in .env
OLLAMA_HOST=http://192.168.15.2:11434              # GPU0
OLLAMA_HOST_GPU1=http://192.168.15.2:11435         # GPU1
OLLAMA_TIMEOUT=30                                   # Seconds
OLLAMA_MODEL=shared-coder                           # Default model
OLLAMA_RETRIES=3                                    # Retry attempts

# Cloud tokens ONLY set if GPU unavailable
OPENAI_API_KEY=<only if GPU down>
ANTHROPIC_API_KEY=<never use, prohibited>
```

### Rule 2: Code Pattern (Required)
Every LLM call must follow this pattern:
```python
async def call_llm(prompt: str, use_cloud_fallback: bool = False) -> str:
    """
    Call LLM with GPU-first strategy.
    
    Priority:
    1. GPU0 (192.168.15.2:11434)
    2. GPU1 (192.168.15.2:11435)
    3. Cloud only if both GPU down AND use_cloud_fallback=True
    """
    gpu_hosts = [
        os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434"),
        os.getenv("OLLAMA_HOST_GPU1", "http://192.168.15.2:11435"),
    ]
    model = os.getenv("OLLAMA_MODEL", "shared-coder")
    timeout = int(os.getenv("OLLAMA_TIMEOUT", 30))
    
    # Try each GPU with retries
    for gpu_url in gpu_hosts:
        for attempt in range(int(os.getenv("OLLAMA_RETRIES", 3))):
            try:
                async with aiohttp.ClientSession() as session:
                    response = await session.post(
                        f"{gpu_url}/api/generate",
                        json={"model": model, "prompt": prompt},
                        timeout=aiohttp.ClientTimeout(total=timeout)
                    )
                    if response.status == 200:
                        return await response.text()
            except Exception as e:
                logger.error(f"GPU attempt {attempt+1} failed: {e}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    # Fallback to cloud ONLY if explicitly allowed and all GPU failed
    if use_cloud_fallback and os.getenv("OPENAI_API_KEY"):
        logger.warning("GPU unavailable, falling back to OpenAI (FREE models only)")
        # Use GPT-4o (free tier)
        return await call_openai_free(prompt)
    
    raise RuntimeError("GPU unavailable and cloud fallback disabled")
```

### Rule 3: Configuration Files
Every config file must include:
```ini
# config.ini
[llm]
primary_host = http://192.168.15.2:11434
secondary_host = http://192.168.15.2:11435
model = shared-coder
timeout_seconds = 30
max_retries = 3
prefer_gpu = true  # NEVER set to false
cloud_fallback_enabled = false  # NEVER true by default
```

### Rule 4: Monitoring & Logging
```python
# Log every LLM call
logger.info(f"LLM call: model={model}, host={host}, attempt={attempt}/{max_retries}")
logger.error(f"GPU failed: {gpu_url} - {error}")
logger.warning("Cloud fallback triggered - GPU unavailable")

# Metrics to track
- gpu_calls_total
- gpu_calls_success
- gpu_calls_failed
- gpu_avg_response_time
- cloud_calls_total  # Should be near 0
```

---

## 🚀 Enforcement (CI/CD & Pre-commit)

### Pre-commit Hook
```bash
#!/bin/bash
# .git/hooks/pre-commit

# Reject commits with cloud API calls as PRIMARY
if grep -r "openai.ChatCompletion\|anthropic.Anthropic\|google.GenerativeAI" \
    --include="*.py" --exclude-dir=tests . 2>/dev/null | \
    grep -v "# GPU fallback\|use_cloud_fallback=True"; then
    echo "❌ ERROR: Cloud LLM as primary detected!"
    echo "Must use Ollama (GPU0/GPU1) as primary."
    exit 1
fi

# Warn if OPENAI_API_KEY in .env (should only be for fallback)
if grep -q "^OPENAI_API_KEY.*=" .env; then
    echo "⚠️  WARNING: OPENAI_API_KEY set in .env"
    echo "This should only be used as GPU fallback!"
fi
```

### CI/CD Check
```yaml
# .github/workflows/gpu-first-check.yml
name: GPU-First Rule Enforcement
on: [pull_request]

jobs:
  gpu_priority:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Check for cloud-first patterns
        run: |
          ! grep -r "ChatCompletion\|Anthropic\|GenerativeAI" \
            --include="*.py" . | grep -v "fallback\|GPU"
```

---

## 📊 Cost Analysis

### GPU Cost (Monthly)
- GPU0 + GPU1: **$0** (hardware amortized)
- Electricity (~200W avg): **~$15/month** (24/7 operation)

### Cloud Cost (Monthly) 
- GPT-4o: **$2-5/1M tokens** (~$50-100 if moderate use)
- Claude 3.5 Sonnet: **PROHIBITED** (would cost $100+)
- Gemini Pro: **PROHIBITED**

### Savings with GPU-First
- **Minimum**: $35-85/month per agent
- **With 5 agents**: **$175-425/month saved**
- **Annual**: **$2,100-5,100 saved**

---

## ⚠️ Exceptions (Rare & Documented)

Only use cloud if:
1. **Both GPU0 AND GPU1 confirmed down** (check health endpoint)
2. **AND emergency/urgent task** (not routine)
3. **AND approved by Edenilson** (add approval comment in code)

```python
# Example: Emergency cloud fallback
if os.getenv("URGENT_TASK_APPROVED"):
    logger.warning("URGENT: Using OpenAI due to GPU unavailability")
    # ... OpenAI call
else:
    raise RuntimeError("GPU unavailable, cloud fallback not approved")
```

---

## 🔄 Monitoring Dashboard

```bash
# Check GPU health
curl http://192.168.15.2:11434/api/tags  # GPU0
curl http://192.168.15.2:11435/api/tags  # GPU1

# Monitor in real-time
watch -n 2 'echo GPU0: $(curl -s http://192.168.15.2:11434/api/tags | jq .models | wc -l) models; echo GPU1: $(curl -s http://192.168.15.2:11435/api/tags | jq .models | wc -l) models'

# Check logs
journalctl -u specialized-agents-api -f | grep "GPU\|LLM\|ollama"
```

---

## 📝 Checklist for Code Review

- [ ] All LLM calls use GPU primary
- [ ] Retry logic with exponential backoff implemented
- [ ] GPU timeouts set to 30s
- [ ] Cloud fallback disabled by default
- [ ] Logging includes GPU attempt info
- [ ] No cloud tokens in .env (except fallback placeholder)
- [ ] CI/CD checks enforce GPU-first

---

## 🎯 Bottom Line

> **If you're about to use a cloud API token without trying GPU first, STOP and reconsider.**

**GPU0 + GPU1 = Free. Cloud = Expensive. No exceptions.**

---

**Last Updated**: 2026-03-07  
**AppliesTo**: `**.py`, `.github/**/*.yml`, `config/**/*.ini`  
**Enforced By**: Pre-commit hooks, CI/CD checks
