# Hermes Cloud Voice Channel

**Status:** design scaffold; not a working telephony adapter.

## Purpose

Plan a secure voice gateway that lets an authorized caller speak to Hermes Cloud. The intended path is inbound phone call → speech-to-text → authenticated Hermes Cloud API → text-to-speech → caller audio.

## Prerequisites

- A deployed Hermes Cloud HTTPS API with authentication.
- A telephony provider that supports inbound calls and webhooks, such as Twilio Programmable Voice, and a phone number available for the account and region.
- Speech-to-text and text-to-speech services, or supported speech features from the telephony provider.
- Server-side secret storage. Never put credentials in this skill, a repository, a browser, or a mobile client.
- For WhatsApp or Telegram, a separately supported bot/business integration. Messaging bot access does not automatically provide native voice-call access.

## Safe implementation sequence

1. Confirm that the phone number and provider account are owned or authorized by the user.
2. Deploy Hermes Cloud behind HTTPS and require authentication.
3. Configure the provider to send inbound-call webhooks only to the verified endpoint.
4. Verify provider webhook signatures before processing calls.
5. Convert caller audio to text, send the transcript and session ID to Hermes Cloud, then synthesize the response to audio.
6. Explain whether audio or transcripts are recorded and retained; obtain consent where required and define retention/deletion rules.
7. Require explicit confirmation before consequential actions such as sending messages, changing accounts, spending money, or modifying code.
8. Add rate limits, timeouts, abuse controls, monitoring, and secret rotation before public deployment.

## Configuration names

- `HERMES_CLOUD_API_URL`
- `HERMES_CLOUD_API_KEY`
- `VOICE_PROVIDER`
- `VOICE_PROVIDER_ACCOUNT_SID`
- `VOICE_PROVIDER_AUTH_TOKEN`
- `VOICE_PROVIDER_PHONE_NUMBER`
- `SPEECH_TO_TEXT_PROVIDER`
- `TEXT_TO_SPEECH_PROVIDER`

Only check whether these variables are present; never print their values in logs.

## Validation checklist

- A test call reaches the authenticated webhook.
- Invalid signatures and unauthenticated API requests are rejected.
- Speech recognition and synthesis work end to end.
- Call sessions do not leak transcripts or context across callers.
- The service asks for authorization before consequential actions.
- Retention, deletion, rate limiting, and provider-cost limits are verified.

## Limitations

This skill does not deploy the server, provision a number, make calls, or claim the service is online. Those capabilities require a real provider adapter, credentials, infrastructure, and end-to-end tests.
