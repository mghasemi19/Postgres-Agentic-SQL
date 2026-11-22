from __future__ import annotations

import json
from pathlib import Path

from db_agent.config import get_settings
from db_agent.logging import configure_logging
from db_agent.service import DatabaseAgentService


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    service = DatabaseAgentService(settings)
    cases_path = Path(__file__).with_name("cases.jsonl")

    total = 0
    passed = 0
    failures: list[dict[str, object]] = []

    for line in cases_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        total += 1
        result = service.query(case["question"])
        ok = True

        expected_statuses = case.get("expect_status")
        if expected_statuses and result.status not in expected_statuses:
            ok = False

        tokens = [token.lower() for token in case.get("required_sql_tokens", [])]
        sql = (result.sql or "").lower()
        if result.status == "ok" and any(token not in sql for token in tokens):
            ok = False

        if ok:
            passed += 1
        else:
            failures.append(
                {
                    "id": case["id"],
                    "status": result.status,
                    "sql": result.sql,
                    "answer": result.answer,
                }
            )

        print(
            f"{case['id']}: status={result.status} latency_ms={result.latency_ms} "
            f"{'PASS' if ok else 'FAIL'}"
        )

    print(f"\nPassed {passed}/{total}")
    if failures:
        print(json.dumps(failures, indent=2, default=str))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
