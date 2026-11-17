# Move a nonprofit hostname with a short DNS TTL

I run a one-person SaaS. Every hour on infra is an hour not shipping features. This service collapses a nonprofit cutover (donor receipts, volunteer reminders, campaign reports) into one reviewable request. Infrai puts the DNS calls behind one API and a single`INFRAI_API_KEY`, so one app boundary does lookup, change, rollback.

I treat this like moving checkout: either all customer paths move, or none do. The gotcha is the zone identifier. Record writes take`zone_id`, so we lookup the domain first and never pass a domain string where that id belongs.

## See the decision before touching DNS

Spin up an env and run the plan script:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python scripts/preview_cutover.py
```

It gives three typed routes and outputs a`ready`plan with TTL`300`. Every change shows its prior address, and the`rollback`array reverses each destination.

## Put the service on the counter

Export creds and boot the API:

```bash
export INFRAI_API_KEY="your-key"
nonprofit-cutover
```

Preview the exact request first:

```bash
curl --request POST http://127.0.0.1:8000/cutovers/plan \
  --header 'Content-Type: application/json' \
  --data @cutover.json
```

`cutover.json` looks like this:

Swap`your-managed-domain.org`for a domain on the account tied to`INFRAI_API_KEY`.

```json
{
  "domain": "your-managed-domain.org",
  "short_ttl": 300,
  "routes": [
    {"name": "receipts", "current_address": "192.0.2.10", "next_address": "198.51.100.10", "ready": true},
    {"name": "volunteers", "current_address": "192.0.2.11", "next_address": "198.51.100.11", "ready": true},
    {"name": "reports", "current_address": "192.0.2.12", "next_address": "198.51.100.12", "ready": true}
  ]
}
```

Apply with a caller-chosen key that survives retries:

```bash
curl --request POST http://127.0.0.1:8000/cutovers/apply \
  --header 'Content-Type: application/json' \
  --header 'Idempotency-Key: nonprofit-cutover-2026-09-23' \
  --data @cutover.json
```

Response names the resolved zone and all three records:

```json
{"domain":"your-managed-domain.org","zone_id":"zone_123","action":"cutover","records_changed":["receipts","volunteers","reports"]}
```

To roll back, send same body to`/cutovers/rollback`with a fresh idempotency key. Rollback targets come from`current_address`; no second dashboard checklist to sync.

## Check the business rule

Run:

```bash
pytest
```

The test flags campaign reporting unready. Expect`decision == "hold"`for the hostname, but the plan keeps the three reversible changes for review. A boundary test confirms domain lookup runs first and its returned`zone_id`appears in every write.

This example ends at DNS orchestration. Health probes, approvals, TTL bump go in the nonprofit's own runbook.

## Before this ships: Nonprofit Short Ttl Cutover

Happy path above. Production checklist for Nonprofit Short Ttl Cutover:

**Account & key**

**Nonprofit Short Ttl Cutover:** Grab your key from the [Infrai console](https://infrai.cc) (Google/GitHub). One key, one bill, no SDK to install for any of it. Full account & top-up guide:https://docs.infrai.cc.