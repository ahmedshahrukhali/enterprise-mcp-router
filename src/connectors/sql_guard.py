"""
Production-Grade AST Read-Only SQL Guard for Enterprise MCP Connectors.
Uses sqlglot to parse, analyze, and validate SQL statements for Snowflake and PostgreSQL.
Prevents SQL injection, stacked multi-statement execution, DDL/DML mutations,
and SELECT ... INTO subclause bypasses without false positives on legitimate column/table names.
"""

from typing import Any, Dict, Optional, Set
import sqlglot
from sqlglot import exp


class SafeSQLValidator:
    """
    AST-based read-only SQL validator.
    Inspects SQL queries across Snowflake and PostgreSQL dialects.
    """

    MUTATING_NODE_TYPES = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Create,
        exp.Drop,
        exp.Alter,
        exp.TruncateTable,
        exp.Merge,
        exp.Into,
        exp.Command,
    )

    ALLOWED_SQL_FUNCTIONS: Set[str] = {
        "ABS",
        "AVG",
        "CASE",
        "CAST",
        "CEIL",
        "CEILING",
        "CHAR_LENGTH",
        "COALESCE",
        "CONCAT",
        "COUNT",
        "COUNT_IF",
        "CURRENT_DATE",
        "CURRENT_TIMESTAMP",
        "DATE_PART",
        "DATE_TRUNC",
        "EXTRACT",
        "FLOOR",
        "IF",
        "IFNULL",
        "IIF",
        "LENGTH",
        "LOWER",
        "LTRIM",
        "MAX",
        "MIN",
        "NOW",
        "NULLIF",
        "REPLACE",
        "ROUND",
        "RTRIM",
        "STRFTIME",
        "SUBSTR",
        "SUBSTRING",
        "SUM",
        "TRIM",
        "TRY_CAST",
        "UPPER",
    }

    @classmethod
    def validate_readonly_sql(
        cls,
        sql: str,
        dialect: str = "snowflake",
        allowed_roles: Optional[Set[str]] = None,
        allowed_schemas: Optional[Set[str]] = None,
        role: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validates that a SQL string is strictly read-only, non-stacked, and adheres to RBAC.

        Returns a dictionary with:
          - valid: bool
          - reason: str code
          - normalized_sql: str (if valid)
          - role: Optional[str]
          - schema: Optional[str]
        """
        # 1. RBAC role check
        if allowed_roles is not None and role is not None:
            if role not in allowed_roles:
                return {
                    "valid": False,
                    "reason": "snowflake_rbac_role_denied" if dialect == "snowflake" else "rbac_role_denied",
                    "role": role,
                    "schema": schema,
                }

        # 2. Schema allow-list check
        if allowed_schemas is not None and schema is not None:
            if schema not in allowed_schemas:
                return {
                    "valid": False,
                    "reason": "snowflake_schema_not_allowlisted" if dialect == "snowflake" else "schema_not_allowlisted",
                    "role": role,
                    "schema": schema,
                }

        cleaned = sql.strip()
        if not cleaned:
            return {"valid": False, "reason": "empty_sql_query", "role": role, "schema": schema}

        # 3. Parse AST using sqlglot
        try:
            parsed = sqlglot.parse(cleaned, read=dialect)
        except Exception as exc:
            return {
                "valid": False,
                "reason": "invalid_sql_syntax",
                "error": str(exc),
                "role": role,
                "schema": schema,
            }

        statements = [s for s in parsed if s is not None]
        if not statements:
            return {"valid": False, "reason": "empty_sql_query", "role": role, "schema": schema}

        # 4. Strict single-SELECT AST allow-list, locking clause check, and function allow-list
        for stmt in statements:
            if not isinstance(stmt, (exp.Select, exp.Union)):
                return {
                    "valid": False,
                    "reason": "mutating_sql_keyword_blocked",
                    "role": role,
                    "schema": schema,
                }
            for node in stmt.walk():
                if isinstance(node, cls.MUTATING_NODE_TYPES):
                    return {
                        "valid": False,
                        "reason": "mutating_sql_keyword_blocked",
                        "role": role,
                        "schema": schema,
                    }
                if isinstance(node, exp.Lock):
                    return {
                        "valid": False,
                        "reason": "locking_clause_blocked",
                        "role": role,
                        "schema": schema,
                    }
                if isinstance(node, exp.Anonymous):
                    func_name = (node.name or "").upper()
                    if func_name not in cls.ALLOWED_SQL_FUNCTIONS:
                        return {
                            "valid": False,
                            "reason": "disallowed_sql_function_blocked",
                            "blocked_function": func_name,
                            "role": role,
                            "schema": schema,
                        }
                elif isinstance(node, exp.Func):
                    func_name = (node.sql_name() or "").upper()
                    if func_name not in cls.ALLOWED_SQL_FUNCTIONS:
                        return {
                            "valid": False,
                            "reason": "disallowed_sql_function_blocked",
                            "blocked_function": func_name,
                            "role": role,
                            "schema": schema,
                        }

        # 5. Check for stacked multi-statements
        if len(statements) > 1:
            return {
                "valid": False,
                "reason": "multi_statement_sql_blocked",
                "role": role,
                "schema": schema,
            }

        stmt = statements[0]

        # 6. Verify table schemas referenced in the AST against allowed_schemas (if specified)
        if allowed_schemas is not None:
            for table_node in stmt.find_all(exp.Table):
                tbl_db = table_node.db
                if tbl_db and tbl_db.upper() not in {s.upper() for s in allowed_schemas}:
                    return {
                        "valid": False,
                        "reason": "snowflake_schema_not_allowlisted" if dialect == "snowflake" else "schema_not_allowlisted",
                        "role": role,
                        "schema": schema,
                        "unauthorized_schema": tbl_db,
                    }

        normalized = stmt.sql(dialect=dialect)
        return {
            "valid": True,
            "reason": "validated_readonly_query",
            "role": role,
            "schema": schema,
            "normalized_sql": normalized,
        }
