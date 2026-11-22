import pytest

from db_agent.safety import SQLSafetyValidator


@pytest.fixture()
def validator() -> SQLSafetyValidator:
    return SQLSafetyValidator(["public", "analytics"], max_rows=100)


def test_allows_select_and_adds_limit(validator: SQLSafetyValidator) -> None:
    result = validator.validate("SELECT customer_id, full_name FROM public.customers")
    assert result.allowed is True
    assert result.sql is not None
    assert "LIMIT 100" in result.sql.upper()


def test_rejects_multiple_statements(validator: SQLSafetyValidator) -> None:
    result = validator.validate("SELECT 1; DROP TABLE customers")
    assert result.allowed is False


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM customers",
        "UPDATE customers SET status = 'inactive'",
        "INSERT INTO customers(full_name) VALUES ('x')",
        "DROP TABLE customers",
        "CREATE TABLE hacked(id int)",
        "TRUNCATE TABLE customers",
    ],
)
def test_rejects_mutations(validator: SQLSafetyValidator, sql: str) -> None:
    assert validator.validate(sql).allowed is False


def test_rejects_system_schema(validator: SQLSafetyValidator) -> None:
    result = validator.validate("SELECT * FROM pg_catalog.pg_user")
    assert result.allowed is False


def test_rejects_unapproved_schema(validator: SQLSafetyValidator) -> None:
    result = validator.validate("SELECT * FROM secret.payroll")
    assert result.allowed is False


def test_blocks_pg_sleep(validator: SQLSafetyValidator) -> None:
    result = validator.validate("SELECT pg_sleep(10)")
    assert result.allowed is False


def test_cte_select_is_allowed(validator: SQLSafetyValidator) -> None:
    result = validator.validate(
        "WITH x AS (SELECT customer_id FROM public.customers) SELECT customer_id FROM x"
    )
    assert result.allowed is True
