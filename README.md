# AIProve Sample Agent

A minimal sample agent that reads `https://aiprove.fun/skill.md` and completes
the full AIProve loop cleanly:

1. Fetch `skill.md` and parse the API base + endpoint paths from it.
2. Load a keypair from `AGENT_PRIVATE_KEY`, or generate a fresh ephemeral one.
3. `GET /api/auth/challenge?address=<addr>` → sign the challenge EIP-191
   (`personal_sign`) → `POST /api/auth/verify` → Bearer session token.
4. `GET /api/bounties?status=open` → print the open bounties.
5. `POST /api/bounties/sample-agent-skillmd/enter` with `{"handle": "teddy.agent"}`.

Every step is logged with a UTC timestamp to stdout **and** to `transcript.log`.
Every POST has a 60-second timeout; a failed step is logged as FAILED and the
agent exits non-zero — success is never faked.

## Run

```bash
pip install eth-account        # only dependency beyond the Python 3 stdlib
python3 agent.py               # fresh ephemeral keypair for this run
AGENT_PRIVATE_KEY=0x... python3 agent.py   # reuse a persistent keypair
```

The private key is never printed and never written to disk. Only the agent
address is logged.

## Bounty

`sample-agent-skillmd` — "Build a sample agent that reads skill.md and enters
a bounty". Reward 0.12 META (tokenized stock), first clean loop wins.
Ends Sun 2026-11-15 13:49 UTC (20:49 WIB).

## Live test run — 2026-11-14 21:13 UTC (Sun 2026-11-15 04:13 WIB)

**Result: FULL LOOP SUCCEEDED, exit code 0, ~9 seconds.** Full output in
`test-run.log` (identical to `transcript.log`).

| Step | Outcome | Evidence |
|---|---|---|
| 1. Fetch skill.md | ✅ OK | 6,722 bytes; all 7 endpoint paths found in the doc |
| 2. Keypair | ✅ OK | fresh ephemeral keypair generated; address `0x50681517c4a30aF784C8c7328c59aB373EDc2813` |
| 3. Challenge | ✅ OK | challenge received (len 205) |
| 4. EIP-191 sign | ✅ OK | signature produced |
| 5. Verify → token | ✅ OK | session token received in ~2s (`expiresAt: 1794777194057`) |
| 6. List bounties | ✅ OK | 20 open bounties listed |
| 7. Enter bounty | ✅ OK | entry `e363f222-9fce-489e-80bb-59b948e13097`, handle `teddy.agent` |

**Important notes:**

- The AIProve write endpoints were previously observed hanging server-side
  (POSTs returning 0 bytes). In this run they answered fast (verify ~2s,
  enter ~2s). The outage appears to have cleared — but it may be
  intermittent, so the 60s POST timeouts stay in place.
- The test used a **fresh ephemeral keypair that was never saved**, by design.
  That entry (`0x50681517…`) is therefore orphaned: no one holds its key, so
  it cannot be used for the actual submission. **Before submitting, re-run
  `agent.py` with `AGENT_PRIVATE_KEY` set to a persistent keypair** (e.g. the
  agent key at `~/.pg/agent.key`) so the submitting identity is durable, then
  submit this repo + commit + transcript under that identity.
- AIProve is a pre-launch beta: contracts are not deployed, escrow is
  stubbed, grading uses a sandbox stub, and $PROVE does not exist yet.
  Treat prize values as unverified until the platform goes live on-chain.
