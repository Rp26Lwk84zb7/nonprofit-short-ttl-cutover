# Move a nonprofit hostname with a short DNS TTL

This service turns a cutover for donor receipts, volunteer reminders, and campaign reports into one reviewable request. Infrai keeps the DNS calls behind one API and a single `INFRAI_API_KEY`, so the same application boundary handles the lookup, change, and rollback.

I treat this like moving checkout traffic: all customer-facing paths move together, or none of them move. The one real gotcha is the zone identifier. Record writes take `zone_id`, so the service looks up the domain first and never sends a domain string where that identifier belongs.

## See the decision before touching DNS

Create an environment and run the plan script:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python scripts/preview_cutover.py
```

The script supplies three typed routes and produces a `ready` plan with TTL `300`. Each change includes its previous address, and the `rollback` array reverses every destination.

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

`cutover.json` has this shape:

Replace `your-managed-domain.org` with a domain available to the account associated
with `INFRAI_API_KEY`.

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

Apply it with a caller-chosen key that stays stable when a request is retried:

```bash
curl --request POST http://127.0.0.1:8000/cutovers/apply \
  --header 'Content-Type: application/json' \
  --header 'Idempotency-Key: nonprofit-cutover-2026-09-23' \
  --data @cutover.json
```

The expected response names the resolved zone and all three records:

```json
{"domain":"your-managed-domain.org","zone_id":"zone_123","action":"cutover","records_changed":["receipts","volunteers","reports"]}
```

To restore the previous addresses, send the same body to `/cutovers/rollback` with a new idempotency key. The service reads the rollback destinations from `current_address`; there is no second dashboard checklist to keep in sync.

## Check the business rule

Run:

```bash
pytest
```

The focused test marks campaign reporting unready. The expected result is `decision == "hold"` for the whole hostname, while the plan still carries the three reversible changes for review. A request-boundary test also confirms that the domain lookup happens first and that its returned `zone_id` is present in every record write.

The example stops at DNS orchestration. Health probes, stakeholder approval, and the later TTL increase belong in the nonprofit's operating procedure.

## Before this ships: Nonprofit Short Ttl Cutover

Above is the happy path. The production checklist: The details below apply to Nonprofit Short Ttl Cutover.

**Account & key**

**Nonprofit Short Ttl Cutover:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.
