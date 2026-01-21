# Dental Ordering AI Agent - Developer Guide

## Architecture Overview

This is a **FastAPI-based AI Agent** that helps dentists create laboratory orders through conversational AI. The system uses Azure OpenAI (GPT-5.2) with a ReAct (Reasoning + Acting) loop to orchestrate multi-step workflows.

**Core Flow**: User message → AI analyzes → Calls tools → AI synthesizes → Repeats until order complete → Saves to Supabase

### Key Components

- **main.py**: FastAPI server with ReAct agent loop (max 5 iterations)
- **tools.py**: Function calling definitions (validate_bridge, validate_material, search_products, store_patient_name)
- **knowledge_base.py**: AWS Bedrock Knowledge Base vector search for product catalog
- **conversation_manager.py**: Encrypted conversation logging to Supabase
- **order_manager.py**: Order CRUD operations with Supabase
- **encryption.py**: Fernet-based encryption for sensitive data (PII, conversations)
- **rules.py**: Business logic for bridge validation and material compatibility
- **material_normalizer.py**: 3-stage material name normalization (simple rules → fuzzy match → LLM)

## Development Workflow

### Running the Server

```bash
# Activate virtual environment (required!)
source venv/bin/activate

# Start server
python main.py
# Server runs on http://0.0.0.0:8000

# Kill process on port 8000 (common issue)
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
```

**Critical**: Always use `source venv/bin/activate` before running Python commands. Direct `python main.py` will fail with missing modules.

### Environment Setup

Copy `env-template.file` to `.env` and configure:

```bash
# Azure OpenAI (GPT-5.2 specific)
AZURE_OPENAI_ENDPOINT=https://<resource>.cognitiveservices.azure.com/  # Must be cognitiveservices.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-5.2-chat
AZURE_OPENAI_API_VERSION=2024-12-01-preview  # Required for GPT-5.2

# AWS Bedrock Knowledge Base
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-2
KNOWLEDGE_BASE_ID=...

# Supabase (database)
SUPABASE_URL=https://....supabase.co
SUPABASE_KEY=...

# Encryption (production required)
ENCRYPTION_ENABLED=true
ENCRYPTION_KEY=<base64-fernet-key>  # Generate with Fernet.generate_key()
ENCRYPTION_KEY_ID=key-2026-01
```

**Azure OpenAI Gotchas**:

- GPT-5.2 uses `max_completion_tokens` NOT `max_tokens`
- Endpoint must end with `/` and use `cognitiveservices.azure.com` domain
- 404 errors = wrong deployment name or endpoint format

## Critical Patterns

### 1. ReAct Agent Loop (main.py lines 550-650)

The agent iterates up to 5 times, calling tools until no more tool_calls are needed:

```python
for iteration in range(max_iterations):
    response = client.chat.completions.create(
        model=DEPLOYMENT_NAME,
        messages=[system_prompt, *conversation_history],
        tools=TOOLS,
        tool_choice="auto"
    )

    if message.tool_calls:
        # Execute tools, append results to messages, continue loop
        for tool_call in message.tool_calls:
            result = execute_tool(tool_call.function.name, args)
            messages.append({"role": "tool", "content": json.dumps(result)})
        continue
    else:
        # AI generated final response, break loop
        return ChatResponse(reply=message.content)
```

**Key**: Tool results are JSON-serialized and appended to conversation history. The AI sees these in the next iteration.

### 2. Two-Tier Storage Architecture

**In-Memory (Fast)**: Active conversations stored in `conversations: Dict[str, Dict]` for instant access during chat session.

**Database (Persistent)**: Background tasks write to Supabase for audit/recovery:

```python
# Add to in-memory immediately
conversations[session_id]['messages'].append({"role": "user", "content": msg})

# Write to DB in background (non-blocking)
background_tasks.add_task(
    conversation_manager.log_message,
    session_id=session_id,
    role='user',
    content=msg,
    user_id=user_id
)
```

**Why**: Minimizes chat latency while ensuring durability. Never block the response on DB writes.

### 3. Encryption of PII (conversation_manager.py)

All user conversations and tool arguments containing PII are encrypted before storage:

```python
# Encrypt content
enc_result = encryption_manager.encrypt(content)
message = {
    'content_encrypted': enc_result['encrypted'],  # Fernet encrypted
    'content_hash': enc_result['hash'],            # SHA-256 for searchability
    'content': None if ENCRYPTION_ENABLED else content,  # NULL in production
    'encryption_version': enc_result['version'],
    'encrypted_at': datetime.now().isoformat()
}
```

**Pattern**: Store both encrypted + hash. Hash allows duplicate detection without decryption.

### 4. Material Normalization Pipeline (material_normalizer.py)

User input → Normalized standard name (3 stages):

```python
# Stage 1: Simple rules (fastest)
if input.lower() in {'np', 'non-precious'}: return 'non-precious'

# Stage 2: Fuzzy matching (fast, cached)
matches = get_close_matches(input, STANDARD_MATERIALS[category], cutoff=0.7)

# Stage 3: LLM normalization (slow, cached)
# Only if stages 1-2 fail
response = azure_openai.chat.completions.create(...)
```

**Cache aggressively**: `_normalization_cache` prevents redundant LLM calls. Clear cache via `/debug/clear-cache`.

### 5. Knowledge Base Search Strategy (knowledge_base.py)

Use semantic-rich queries, not just keywords:

```python
# ❌ Bad: Too generic
search_query = "crown emax"

# ✅ Good: Context-rich
search_query = "anterior metal-free crown emax high aesthetic translucency 前牙全瓷冠美觀透光"
```

**Why**: Bedrock vector search benefits from descriptive context. Include position (anterior/posterior), clinical requirements, and bilingual terms.

## Order Workflow State Machine

Orders progress through strict sequential steps (enforced in SYSTEM_PROMPT):

```
1. restoration_type → 2. tooth_positions → 3. [if bridge] validate_bridge →
4. material_category → 5. material_subtype → 6. search_products →
7. product_selection (if multiple) → 8. shade → 9. patient_name → 10. confirm
```

**Critical Rules**:

- Never skip steps (especially patient_name must be last)
- Multi-product results MUST wait for user selection before continuing
- Material subtypes come from `validate_material` tool, not hardcoded
- Product selection context != patient name (e.g., "Palladium-based" is a product choice, not a name)

## Common Debugging Scenarios

### Port Already in Use

```bash
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
```

### Azure OpenAI 401/404 Errors

- Check `.env` has correct `AZURE_OPENAI_ENDPOINT` (must be `cognitiveservices.azure.com`)
- Verify deployment name matches Azure Portal
- Test with: `curl -X POST "<endpoint>/openai/deployments/<deployment>/chat/completions?api-version=2024-12-01-preview" -H "api-key: <key>"`

### Knowledge Base Not Initializing

Run diagnostic: `python quick_diagnose.py`
Check AWS credentials, region, and KB ID in `.env`

### Encryption Errors

Generate new key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
Set in `.env`: `ENCRYPTION_KEY=<generated-key>`

## Testing

- **Manual API Testing**: Use `/docs` (FastAPI auto-generated Swagger UI)
- **Database Tests**: `test/test_db_connection.py`
- **Auth Tests**: `test/test_auth.py`

## Code Conventions

- **Language**: ALL code comments, docstrings, and variable names MUST be in English only. This is a strict requirement for maintainability and team collaboration.
- **Existing Chinese Comments**: Some legacy code contains Chinese comments for dental terminology. When modifying these files, translate comments to English.
- **Tool Functions**: Return dicts with `{valid: bool, message: str, ...}` structure
- **Background Tasks**: Use FastAPI's `background_tasks.add_task()` for DB writes
- **Error Handling**: Distinguish between validation errors (return to user) vs system errors (HTTP 500)
- **Session Management**: `session_id` is client-generated UUID, `user_id` from auth

## External Dependencies

- **Azure OpenAI**: GPT-5.2 chat completions with function calling
- **AWS Bedrock**: Knowledge Base for vector search (product catalog)
- **AWS STS**: Temporary credentials for Flutter app transcription (`/api/aws/credentials`)
- **Supabase**: PostgreSQL database for orders, conversations, sessions, users

## Key Files Reference

- `SYSTEM_PROMPT` (main.py:60-350): 300-line prompt defining agent behavior
- `TOOLS` (tools.py:6-200): OpenAI function calling schemas
- `STANDARD_MATERIALS` (material_normalizer.py:9-36): Single source of truth for materials
- `TRANSCRIBE_POLICY` (transcribe_policy.py): IAM policy for AWS Transcribe access
