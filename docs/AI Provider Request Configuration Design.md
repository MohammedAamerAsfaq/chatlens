# AI Provider Request Configuration Design

## Purpose

ChatLens uses configurable AI providers for structured tasks such as inquiry extraction, product matching, embeddings, and future automation. Provider configuration must remain portable and must not lock the application into one vendor-specific request format.

This document records the intended design for adding model request controls such as JSON response mode and provider-specific options without breaking existing providers.

## Problem

Some OpenAI-compatible models can return non-JSON text even when the prompt says `Respond ONLY with valid JSON`. For example, a model may return reasoning-style content before the JSON body. This breaks strict structured parsing because the parser expects the response to begin with valid JSON.

`temperature=0` is still correct for deterministic extraction, but it does not guarantee JSON-only output. JSON reliability must be enforced through model/provider request configuration where supported.

## Design Principle

Provider request configuration must be:

- Provider-neutral by default.
- Provider-specific only when explicitly scoped to that provider.
- Non-breaking for providers that do not need or support a given option.
- Stored in provider configuration, not hardcoded into V2 inquiry logic.
- Applied consistently across agent/chat calls through the provider layer.

## Proposed Configuration Shape

Each AI provider may define optional request parameters in `extra_config`.

```json
{
  "default_chat_params": {
    "response_format": { "type": "json_object" }
  },
  "provider_chat_params": {
    "google": {
      "extra_body": {
        "google": {
          "thinking_config": {
            "include_thoughts": false
          }
        }
      }
    }
  }
}
```

`default_chat_params` contains generic OpenAI-compatible options that may be useful across multiple providers.

`provider_chat_params` contains vendor-specific options keyed by provider name. A Google-specific option must only be merged when the active provider is `google`; it must not be sent to DeepSeek, OpenAI, Qwen, Mistral, or other providers.

## Merge Order

When building the final chat request body, merge request parameters in this order:

1. Base request fields such as `model` and `messages`.
2. `extra_config.default_chat_params`.
3. `extra_config.provider_chat_params[provider]`.
4. Explicit caller kwargs, such as `temperature=0`.

Explicit caller kwargs must remain authoritative because task code may need to enforce deterministic behavior for structured workflows.

## Example For Gemini/Gemma

For Google OpenAI-compatible models, JSON mode and thought suppression can be configured without hardcoding Google behavior into the classification service:

```json
{
  "default_chat_params": {
    "response_format": { "type": "json_object" }
  },
  "provider_chat_params": {
    "google": {
      "extra_body": {
        "google": {
          "thinking_config": {
            "include_thoughts": false
          }
        }
      }
    }
  }
}
```

If the provider/model still returns non-JSON content after JSON mode is enabled, that model should not be used for strict structured extraction until proven reliable.

## Non-Goals

- Do not add Google-specific parameters directly inside V2 inquiry extraction code.
- Do not make V2 dependent on a single provider.
- Do not silently clean or discard reasoning text as a fallback without logging the raw failure.
- Do not change existing provider behavior when `extra_config` is empty.

## Future Implementation Notes

The provider layer should merge these parameters in `OpenAIChatProvider.chat()` or an equivalent common OpenAI-compatible provider path. Existing providers with empty `extra_config` must produce the same request body they produce today.

Before enabling this globally, test at least:

- Current active agent provider.
- DeepSeek agent provider.
- Google/Gemini or Gemma agent provider.
- Any OpenAI-compatible provider used for production parsing.

