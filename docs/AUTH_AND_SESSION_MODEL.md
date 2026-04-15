# Auth and Session Model

## Why this deserves its own document

Both marketdata and trading/account services require authentication.

If the product treats those as unrelated logins, the runtime quickly becomes harder to reason about:

- duplicated credential handling
- inconsistent capability checks
- harder reconnect logic
- weaker operator visibility
- more room for agents to operate in ambiguous permission states

So v0.1 defines a shared **AuthSessionManager** concept.

## Design goal

Authenticate once and share session context across:

- marketdata surfaces
- trading surfaces
- account / position surfaces

Where the vendor truly supports one shared session, use it.

Where the vendor requires multiple underlying logins/tokens, still present **one logical runtime session** with explicit capabilities and health.

## Supported login modes

The docs should treat these as first-class supported shapes:

### Mode A
`account + password + cert + cert password`

### Mode B
`account + API key + cert + cert password`

The runtime should model the login mode explicitly, not infer it from half-populated fields.

## Safety boundary for agent-assisted setup

Mode B is especially useful for controlled workflows.

In some broker environments, the API key can be provisioned with narrower permissions. That enables a safer pattern:

- let a user or agent validate config, check session shape, and prepare runtime setup
- keep trade permission disabled on the API key when the goal is setup/replay/dry-run only
- expand authority only with explicit operator action

This is the right product stance for a seed runtime: helpful automation, not hidden live authority.

## SessionContext contract

A logical session context should include at least:

- `session_id`
- `account_no`
- `auth_mode`
- `marketdata_enabled`
- `trade_enabled`
- `account_query_enabled`
- `session_started_at`
- `expires_at` or renewal hint
- `capabilities`
- `health_status`
- `vendor_metadata`

Example capability questions the runtime should answer cleanly:

- Can this session subscribe market data?
- Can this session query positions?
- Can this session submit orders?
- Does this session require renewal or re-login?

## AuthSessionManager responsibilities

- validate profile shape before attempting login
- establish the logical runtime session
- attach usable session state to marketdata + broker/account surfaces
- refresh or re-login when the session becomes stale
- expose health and capability state to CLI / operator tooling
- make permission boundaries explicit before live workflows are armed

## CLI implications

The CLI should be able to:

- validate an auth profile file without logging in
- inspect the chosen login mode and expected capability shape
- inspect the current logical session and health state
- show whether trade permission is available

That prevents the common failure mode where everyone thinks they are in a safe dry-run posture while the credentials actually permit live trading.

## Secret handling stance

This repo should document profile shape and capability semantics.

It should **not** commit real credentials, certificates, or secret material.

Credential storage, secret distribution, and local environment hardening belong to operator workflows outside this seed repo.

## Failure and renewal model

The session layer should classify at least:

- invalid credentials / cert problems
- permission mismatch
- transient transport failure
- expired or stale session
- reconnect required but not yet healthy

These should surface as structured states, not only log text.

## Broker-preflight contract skeleton (new seed alignment)

Before a future trading-day smoke cron is allowed to move past preflight, the session surface should expose a stable shape for:

- `session_status.session_state`
- `session_status.renewal_state`
- `session_status.connections.marketdata.state`
- `session_status.connections.broker.state`
- `session_status.connections.account.state`

Seed-runtime truth may still report `not-connected`, but the shape itself should already be stable.
That way, later broker-connected work can replace the source of truth without rewriting the CLI/operator contract.

## Operator posture

Before live trading is even considered, an operator should be able to answer:

- which account is active?
- which login mode is in use?
- is trade permission enabled?
- which surfaces are healthy right now?
- what will reconnect / renewal do if the session drops?

If the runtime cannot answer those cleanly, it is not ready to claim operator control.
