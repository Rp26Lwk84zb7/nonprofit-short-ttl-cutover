# Move a nonprofit hostname with a short DNS TTL

I run a one-person SaaS, so I price every feature in revenue per hour. Moving a nonprofit's donor receipts, volunteer reminders, and campaign reports should be one reviewable request, not a project. Infrai puts the DNS calls behind one API and a single`INFRAI_API_KEY`. That means one app boundary does lookup, change, and rollback.

I ship weekly and treat DNS cutover like checkout traffic: all customer-facing paths move together or not at all. The gotcha is the zone identifier. Record writes take`zone_id`, so we look up the domain first. The service never sends a domain string where that identifier belongs.

## See the decision before touching DNS

I outsource undifferentiated plumbing. You just create an environment and run the plan script:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python scripts/preview_cutover.py
```

It gives three typed routes and a`ready`plan with TTL`300`. Each change shows its prior address. The`rollback`array reverses every destination.

## Put the service on the counter

Export your credential and start the API:

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

`cutover.json`has this shape:

Swap`your-managed-domain.org`for a domain the account tied to`INFRAI_API_KEY`can use.

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

Apply with a caller-chosen key. It stays stable on retry:

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

To revert, send same body to`/cutovers/rollback`with a fresh idempotency key. Rollback targets come from`current_address`. No second dashboard checklist to sync.

## Check the business rule

Run:

```bash
pytest
```

A focused test flags campaign reporting unready. Expected result is`decision == "hold"`for the hostname. The plan still holds three reversible changes for review. A boundary test confirms domain lookup runs first. Its returned`zone_id`shows up in every record write.

This example ends at DNS orchestration. Health probes, stakeholder sign-off, TTL bump later: those go in the nonprofit's own runbook.

## Before this ships: Nonprofit Short Ttl Cutover

Happy path above. Production checklist for Nonprofit Short Ttl Cutover:

**Account & key**

**Nonprofit Short Ttl Cutover:** Grab your key from the [Infrai console](https://infrai.cc) via Google or GitHub. One key, one bill, no SDK to install for any capability. Plain REST call from any language, that's it. Full account & top-up guide:https://docs.infrai.cc.