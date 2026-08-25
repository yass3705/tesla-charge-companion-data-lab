# Bump mobile static API discovery

Read-only static inspection of the current Google Play APK/splits. No Bump account, app execution, charging or payment action was used.

## Result

- APK/split files inspected: **4**
- Sanitized URL candidates: **47**
- Relative API/path candidates: **0**
- Likely station/tariff API candidates: **32**

## Candidate hosts

- `help.bump-charge.com` — 7 candidate(s)
- `www.bump-charge.com` — 3 candidate(s)
- `api.flutter.dev` — 2 candidate(s)
- `maps.googleapis.com` — 2 candidate(s)
- `stripe.com` — 2 candidate(s)
- `www.google.com` — 2 candidate(s)
- `www.googleapis.com` — 2 candidate(s)
- `api-staging.bump-charge.com` — 1 candidate(s)
- `api.bump-charge.com` — 1 candidate(s)
- `api.chargetrip.io` — 1 candidate(s)
- `api.staging.bump-charge.dev` — 1 candidate(s)
- `api.stripe.com` — 1 candidate(s)
- `api2.branch.io` — 1 candidate(s)
- `api3-eu.branch.io` — 1 candidate(s)
- `b.stripecdn.com` — 1 candidate(s)
- `buy-pass.bump-charge.com` — 1 candidate(s)
- `dl-app.bump-charge.com` — 1 candidate(s)
- `docs.stripe.com` — 1 candidate(s)
- `engine.api.dev.gist.build` — 1 candidate(s)
- `engine.api.gist.build` — 1 candidate(s)
- `engine.api.local.gist.build` — 1 candidate(s)
- `errors.stripe.com` — 1 candidate(s)
- `firebaseappcheck.googleapis.com` — 1 candidate(s)
- `firebaseremoteconfig.googleapis.com` — 1 candidate(s)
- `firebaseremoteconfigrealtime.googleapis.com` — 1 candidate(s)
- `identity.bump-charge.dev` — 1 candidate(s)
- `js.hcaptcha.com` — 1 candidate(s)
- `merchant-ui-api.stripe.com` — 1 candidate(s)
- `queue.api.local.gist.build` — 1 candidate(s)
- `realtime.cloud.dev.gist.build` — 1 candidate(s)

## Likely station/tariff candidates

- `https://api-staging.bump-charge.com/`
- `https://api.bump-charge.com/`
- `https://api.chargetrip.io/graphql`
- `https://api.flutter.dev/flutter/dart-ui/ChannelBuffers-class.html`
- `https://api.flutter.dev/flutter/material/Scaffold/of.html`
- `https://api.staging.bump-charge.dev/`
- `https://api.stripe.com/`
- `https://api2.branch.io/`
- `https://api3-eu.branch.io/`
- `https://b.stripecdn.com/connections-statics-srv/assets/PrepaneAsset--account_numbers-capitalone-2x.gif`
- `https://docs.stripe.com/api/customer_sessions/create`
- `https://engine.api.dev.gist.build/`
- `https://engine.api.gist.build/`
- `https://engine.api.local.gist.build/`
- `https://errors.stripe.com/api/`
- `https://firebaseappcheck.googleapis.com/v1/projects/%s/apps/%s:generatePlayIntegrityChallenge`
- `https://firebaseremoteconfig.googleapis.com/v1/projects/%s/namespaces/%s:fetch`
- `https://firebaseremoteconfigrealtime.googleapis.com/v1/projects/%s/namespaces/%s:streamFetchInvalidations`
- `https://js.hcaptcha.com/1/api.js`
- `https://maps.googleapis.com/`
- `https://maps.googleapis.com/maps/api/streetview`
- `https://merchant-ui-api.stripe.com/elements/`
- `https://queue.api.local.gist.build/`
- `https://realtime.cloud.dev.gist.build/api/v3/sse`
- `https://realtime.inapp.customer.io/api/v3/sse`
- `https://stripe.com/docs/api/payment_intents/object`
- `https://stripe.com/docs/api/setup_intents/object`
- `https://www.elephantbleu.com/ma-station-de-lavage/`
- `https://www.googleapis.com/auth/games`
- `https://www.googleapis.com/auth/games_lite`
- `https://www.recaptcha.net/recaptcha/api3`
- `https://www.reduxkotlin.org/api/store`

## Safety / TCC rule

Static clues are discovery evidence only. No endpoint is used to publish a Bump tariff until a public/read-only station lookup is verified against official Bump station/PDC identifiers and returns an explicit driver-facing price.
