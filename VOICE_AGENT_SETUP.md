# Optional Sarvam Voice Agents setup

The browser MVP is ready without these steps. No phone number has been provisioned and no real call has been placed.

1. Open the Sarvam Voice Agents dashboard and create an agent. Connect or rent a phone number and create an inbound deployment. These operations require your Voice Agents workspace access; a Model API key alone is insufficient.
2. Host this backend behind HTTPS and an authenticated gateway before exposing it externally. Set a strong `VOICE_TOOL_TOKEN` in `.env` and restart. The default local service does not expose a public address.
3. Add an API tool named `process_retailer_turn`, POST to `https://YOUR_HOST/api/voice-agent/turn`. Store its bearer credential in Sarvam Secrets and configure `Authorization: Bearer <VOICE_TOOL_TOKEN>` through the tool's secure auth controls.
4. Map the User Identifier call-context variable to `phone_number` and Interaction ID to `interaction_id`. Pass each retailer utterance as `text`, a unique stable per-turn `request_id`, and `revision` initially 0. Store returned `order.revision` and supply it for the next turn. Reuse the same request ID on a retry. Use an allowlisted gateway if integrating telephony into a broader network.

Example request (fictional retailer):

```json
{
  "interaction_id": "unique-call-identifier",
  "phone_number": "+919000000001",
  "request_id": "unique-turn-identifier",
  "revision": 0,
  "text": "Kal 10 carton atta aur 5 carton Maggi bhej dena"
}
```

5. Configure the agent to read the returned `reply` faithfully, without inventing stock, prices or success. The backend supplies the current cart and computed shortages. Every retailer turn must go through the tool. Do not trigger an outbound order or auto-confirm at call end.
6. Require a separate “Haan confirm” (or the supported explicit equivalent) after the complete cart has been read back. Substitute acceptance is only a cart edit. A `COMPLETED` result is the only success condition. Unknown caller numbers require human handling; the adapter never assigns an unknown caller to Raja Stores.
7. Test in Sarvam's agent tester, then call the connected number. Use real customer mappings only after the application is secured and the fictional seed phone numbers are replaced.

Sarvam Voice Agents management APIs use `X-API-Key`, separate from the Model API `api-subscription-key`. Deployments use `https://apps.sarvam.ai/api/app-authoring` and organization/workspace-scoped routes. Tool auth is the private bearer token for this app, not the Sarvam API key.

Official setup references: [overview](https://docs.sarvam.ai/conversations/overview), [HTTP tools and caller variables](https://docs.sarvam.ai/conversations/build/tools/https-tool), [Voice Agents API authentication and URLs](https://docs.sarvam.ai/api-reference/conversations).
