import json

from nonprofit_cutover.cutover_service import build_plan
from nonprofit_cutover.models import CutoverRequest


def main() -> None:
    request = CutoverRequest.model_validate(
        {
            "domain": "giving.example.org",
            "short_ttl": 300,
            "routes": [
                {
                    "name": "receipts",
                    "current_address": "192.0.2.10",
                    "next_address": "198.51.100.10",
                    "ready": True,
                },
                {
                    "name": "volunteers",
                    "current_address": "192.0.2.11",
                    "next_address": "198.51.100.11",
                    "ready": True,
                },
                {
                    "name": "reports",
                    "current_address": "192.0.2.12",
                    "next_address": "198.51.100.12",
                    "ready": True,
                },
            ],
        }
    )
    print(json.dumps(build_plan(request).model_dump(), indent=2))


if __name__ == "__main__":
    main()
