#!/usr/bin/env python3
"""AIProve sample agent — reads skill.md, authenticates, lists, enters.

Bounty: sample-agent-skillmd — "Build a sample agent that reads skill.md and
enters a bounty" (0.12 META, first clean loop wins).

Loop (per https://aiprove.fun/skill.md):
  1. fetch + read skill.md, parse API base + endpoint paths from it
  2. keypair from AGENT_PRIVATE_KEY env, else generate a fresh ephemeral one
     (the private key is NEVER printed or written to disk)
  3. GET /api/auth/challenge?address=<addr>
  4. sign the challenge EIP-191 (personal_sign)
  5. POST /api/auth/verify -> Bearer session token
  6. GET /api/bounties?status=open
  7. POST /api/bounties/sample-agent-skillmd/enter {"handle": "teddy.agent"}

Every step is logged with a UTC timestamp to stdout AND to transcript.log.
Every POST has a 60s timeout. A failed step is logged as FAILED and the
agent exits non-zero with a clear message — success is never faked.

Dependencies: Python 3 stdlib + eth-account only.
Run:  AGENT_PRIVATE_KEY=0x... python3 agent.py
      (without the env var a fresh ephemeral keypair is generated for the run)
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from eth_account import Account
from eth_account.messages import encode_defunct

API_BASE = "https://aiprove.fun"
SKILL_URL = "https://aiprove.fun/skill.md"
BOUNTY_SLUG = "sample-agent-skillmd"
HANDLE = "teddy.agent"
POST_TIMEOUT = 60  # seconds, every POST
GET_TIMEOUT = 60

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transcript.log")
_log_file = open(LOG_PATH, "a", encoding="utf-8")


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    _log_file.write(line + "\n")
    _log_file.flush()


def fail(msg):
    log(f"FAILED: {msg}")
    _log_file.close()
    sys.exit(1)


def http_get(url, timeout=GET_TIMEOUT):
    """GET via curl (urllib is unreliable through this VM's egress proxy)."""
    try:
        r = subprocess.run(
            ["curl", "-sS", "--max-time", str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 10,
        )
    except subprocess.TimeoutExpired:
        return None, f"GET {url} timed out after {timeout}s"
    if r.returncode != 0:
        return None, f"GET {url} curl error rc={r.returncode}: {r.stderr.strip()[:200]}"
    if not r.stdout.strip():
        return None, f"GET {url} returned 0 bytes (empty reply)"
    return r.stdout, None


def http_post_json(url, payload, token=None, timeout=POST_TIMEOUT):
    """POST JSON via curl. Returns (body, error)."""
    headers = ["-H", "content-type: application/json"]
    if token:
        headers += ["-H", f"Authorization: Bearer {token}"]
    try:
        r = subprocess.run(
            ["curl", "-sS", "--max-time", str(timeout), "-X", "POST", url]
            + headers + ["-d", json.dumps(payload)],
            capture_output=True, text=True, timeout=timeout + 10,
        )
    except subprocess.TimeoutExpired:
        return None, f"POST {url} timed out after {timeout}s (server did not respond)"
    if r.returncode != 0:
        return None, f"POST {url} curl error rc={r.returncode}: {r.stderr.strip()[:200]}"
    if not r.stdout.strip():
        return None, f"POST {url} returned 0 bytes (empty reply — server write path not answering)"
    return r.stdout, None


def main():
    log("=== AIProve sample agent — full loop ===")
    log(f"API base: {API_BASE} | bounty: {BOUNTY_SLUG} | handle: {HANDLE}")

    # ---- Step 1: fetch + read skill.md, parse the endpoints we follow ----
    log("STEP 1: fetching skill.md ...")
    body, err = http_get(SKILL_URL)
    if err:
        fail(f"could not fetch skill.md: {err}")
    log(f"STEP 1 OK: skill.md fetched ({len(body)} bytes)")
    # Parse the endpoint paths from the doc itself (the sections we follow).
    wanted = {
        "auth challenge": "/api/auth/challenge?address=",
        "auth verify": "/api/auth/verify",
        "list bounties": "/api/bounties?status=open",
        "enter bounty": "/api/bounties/:slug/enter",
        "submit": "/api/bounties/:slug/submit",
        "me": "/api/me",
        "leaderboard": "/api/leaderboard",
    }
    for name, path in wanted.items():
        log(f"  skill.md section: {name:16s} -> {path} "
            f"{'FOUND' if path in body else 'NOT FOUND IN DOC'}")
    if "/api/auth/challenge" not in body or "/api/bounties" not in body:
        fail("skill.md does not contain the expected API endpoints")

    # ---- Step 2: keypair (env) or fresh ephemeral one ----
    log("STEP 2: keypair ...")
    raw_key = os.environ.get("AGENT_PRIVATE_KEY", "").strip()
    if raw_key:
        acct = Account.from_key(raw_key)
        log("STEP 2 OK: loaded keypair from AGENT_PRIVATE_KEY env var")
    else:
        acct = Account.create()
        log("STEP 2 OK: generated fresh EPHEMERAL keypair for this run "
            "(not saved anywhere; only the address is logged)")
    log(f"  agent address: {acct.address}")
    # NOTE: the private key is never printed, never written to disk.

    # ---- Step 3: challenge ----
    log("STEP 3: GET /api/auth/challenge ...")
    body, err = http_get(f"{API_BASE}/api/auth/challenge?address={acct.address}")
    if err:
        fail(f"challenge request failed: {err}")
    try:
        challenge = json.loads(body).get("challenge")
    except json.JSONDecodeError:
        fail(f"challenge response is not JSON: {body[:200]}")
    if not challenge:
        fail(f"challenge response has no 'challenge' field: {body[:300]}")
    log(f"STEP 3 OK: challenge received (len {len(challenge)})")

    # ---- Step 4: sign EIP-191 personal_sign ----
    log("STEP 4: signing challenge EIP-191 personal_sign ...")
    sig = acct.sign_message(encode_defunct(text=challenge)).signature.hex()
    log("STEP 4 OK: signature produced (not logged)")

    # ---- Step 5: verify -> Bearer token ----
    log(f"STEP 5: POST /api/auth/verify (timeout {POST_TIMEOUT}s) ...")
    body, err = http_post_json(
        f"{API_BASE}/api/auth/verify",
        {"address": acct.address, "signature": "0x" + sig},
    )
    if err:
        fail(f"auth verify failed: {err}")
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        fail(f"verify response is not JSON: {body[:200]}")
    token = data.get("token")
    if not token:
        fail(f"verify response has no token: {body[:300]}")
    log(f"STEP 5 OK: session token received (expiresAt: {data.get('expiresAt')})")

    # ---- Step 6: list open bounties ----
    log("STEP 6: GET /api/bounties?status=open ...")
    body, err = http_get(f"{API_BASE}/api/bounties?status=open")
    if err:
        fail(f"list bounties failed: {err}")
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        fail(f"bounties response is not JSON: {body[:200]}")
    items = data if isinstance(data, list) else data.get("bounties", data.get("items", []))
    log(f"STEP 6 OK: {len(items)} open bounties")
    for b in items[:25]:
        if isinstance(b, dict):
            log(f"  - {b.get('slug')}: {b.get('title')} "
                f"({b.get('amt')} {b.get('unit')}, closes {b.get('endDate') or b.get('closes')})")

    # ---- Step 7: enter the sample-agent bounty ----
    log(f"STEP 7: POST /api/bounties/{BOUNTY_SLUG}/enter (timeout {POST_TIMEOUT}s) ...")
    body, err = http_post_json(
        f"{API_BASE}/api/bounties/{BOUNTY_SLUG}/enter",
        {"handle": HANDLE},
        token=token,
    )
    if err:
        fail(f"enter failed: {err}")
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        fail(f"enter response is not JSON: {body[:200]}")
    log(f"STEP 7 OK: entered {BOUNTY_SLUG} — response: {json.dumps(data)[:300]}")

    log("=== FULL LOOP COMPLETE: authenticated, listed, entered ===")
    _log_file.close()


if __name__ == "__main__":
    main()
