# LLM Provider Setup — Gemini API

## Default choice

The project uses the Gemini Developer API through the official `google-genai` Python SDK. Reviewers do not need Ollama or a local model.

## Create your own key

1. Open Google AI Studio: https://aistudio.google.com/
2. Sign in and create/view a Gemini API key.
3. Copy `.env.example` to `.env`.
4. Put the key in `GEMINI_API_KEY`.
5. Confirm the configured model is available for your account and free tier.

## Security rules

- Never commit `.env`, paste a key into source code, or include it in logs.
- Every reviewer should use their own key rather than sharing the developer's key.
- Restrict the key to the Gemini API where the platform offers that setting.
- Check the current free-tier quotas, model access, and terms before running a large workload.
- Google's current Gemini free-tier pricing page states that content may be used to improve its products. Do not send confidential company information unless the company has reviewed and approved the provider and applicable terms.
- The application must never silently enable paid billing or switch to a paid model/provider.
- If quota is exhausted, pause or degrade gracefully, record the reason, and explain how to resume.

## Budget semantics

The hard-coded €4.00 ceiling is an application safety limit for provider-billed LLM usage. It does not guarantee that free quota will be sufficient for 1,500 articles, nor does it replace provider quota enforcement. Track input/output tokens and estimated cost whenever the API exposes usage metadata. Benchmark real runs and report actual usage.

## Official documentation

- Gemini API setup and keys: https://ai.google.dev/gemini-api/docs/api-key
- Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
- Gemini API rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
