# Bump public GraphQL probe

Unauthenticated, read-only GraphQL meta-query only. No account/session/token or charging action used.

## Endpoint attempts

- `POST /graphql` → **200** — GraphQL Query typename: **true**

Resolved GraphQL endpoint: **/graphql**

## Public query schema

Introspection status: **200**, fields discovered: **30**

- `chargePoints` — args: `no args`
- `locationPlanning` — args: `no args`
- `tariffs` — args: `no args`

## TCC rule

This probe only establishes public schema metadata. Station prices remain non-rankable until an explicit tariff query can be matched to Bump's official station/PDC inventory.
