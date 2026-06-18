"""Маршрут: SQL-консоль (только admin)."""

import sqlalchemy as _sa

from fastapi import APIRouter, Request, Form, Depends
from app.database import templates, engine
from app.auth import require_role

router = APIRouter()


@router.get("/sql")
def sql_page(request: Request, _: dict = Depends(require_role("admin"))):
    """Форма SQL-запроса."""
    return templates.TemplateResponse(request=request, name="sql.html", context={
        "query": "",
        "error": None,
        "columns": None,
        "rows": None,
        "row_count": None,
        "affected": None,
    })


@router.post("/sql")
def sql_execute(
    request: Request,
    query: str = Form(""),
    _: dict = Depends(require_role("admin")),
):
    """Выполнить SQL-запрос и показать результат."""
    query_stripped = query.strip()

    if not query_stripped:
        return templates.TemplateResponse(
            request=request, name="sql.html",
            context={"query": "", "error": "Запрос не может быть пустым.",
                     "columns": None, "rows": None, "row_count": None, "affected": None},
        )

    is_select = query_stripped.upper().lstrip().startswith("SELECT")

    try:
        with engine.connect() as conn:
            if is_select:
                result = conn.execute(_sa.text(query_stripped))
                columns = list(result.keys())
                rows = [list(row) for row in result.fetchall()]
                row_count = len(rows)
                affected = None
            else:
                result = conn.execute(_sa.text(query_stripped))
                conn.commit()
                columns = None
                rows = None
                row_count = None
                affected = result.rowcount  # число затронутых строк
        return templates.TemplateResponse(
            request=request, name="sql.html",
            context={
                "query": query, "error": None,
                "columns": columns, "rows": rows, "row_count": row_count,
                "affected": affected,
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            request=request, name="sql.html",
            context={
                "query": query, "error": str(e),
                "columns": None, "rows": None, "row_count": None, "affected": None,
            },
        )
