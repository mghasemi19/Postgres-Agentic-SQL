from db_agent.schema import TableSummary


def lexical_score(question: str, item: TableSummary) -> int:
    # Mirrors the intended ranking intuition without requiring a live DB inspector.
    q = set(question.lower().replace("?", "").split())
    table = set(item.table.lower().split("_"))
    columns = set(" ".join(item.columns).lower().replace("_", " ").split())
    return len(q & table) * 5 + len(q & columns)


def test_product_question_prefers_products() -> None:
    products = TableSummary("public", "products", ("product_id", "name", "category"))
    customers = TableSummary("public", "customers", ("customer_id", "full_name", "country"))
    q = "Which product category sold the most?"
    assert lexical_score(q, products) > lexical_score(q, customers)
