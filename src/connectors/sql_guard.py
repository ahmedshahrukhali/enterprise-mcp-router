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
        allowed_tables: Optional[Set[str]] = None,
        require_qualified_tables: bool = False,
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

        # 6. Verify CTE aliases (block shadowing) and every exp.Table in the AST
        #    (covering FROM, JOIN, UNION/UNION ALL, subqueries, and CTE bodies).
        upper_allowed_schemas = {s.upper() for s in allowed_schemas} if allowed_schemas is not None else None
        upper_allowed_tables = {t.upper() for t in allowed_tables} if allowed_tables is not None else None
        allowlisted_short_names = {t.split(".")[-1] for t in (upper_allowed_tables or set())}

        valid_cte_aliases: Set[str] = set()
        for cte in stmt.find_all(exp.CTE):
            alias = (cte.alias_or_name or "").strip().upper()
            if not alias:
                continue
            if alias in allowlisted_short_names:
                return {
                    "valid": False,
                    "reason": "cte_table_shadowing_blocked",
                    "role": role,
                    "schema": schema,
                    "blocked_cte": cte.alias_or_name,
                }
            valid_cte_aliases.add(alias)

        for table_node in stmt.find_all(exp.Table):
            tbl_catalog = (table_node.catalog or "").strip()
            tbl_db = (table_node.db or "").strip()
            tbl_name = (table_node.name or "").strip()
            fq_name = ".".join(part for part in (tbl_catalog, tbl_db, tbl_name) if part)

            # A local CTE alias reference (unqualified, matching a non-shadowing CTE) is permitted
            # because every exp.Table inside the CTE definition itself is validated in this loop.
            if not tbl_catalog and not tbl_db and tbl_name.upper() in valid_cte_aliases:
                continue

            if tbl_catalog and (upper_allowed_tables is not None or upper_allowed_schemas is not None):
                return {
                    "valid": False,
                    "reason": "unauthorized_table_access",
                    "role": role,
                    "schema": schema,
                    "unauthorized_table": fq_name,
                }

            if upper_allowed_schemas is not None:
                if tbl_db:
                    if tbl_db.upper() not in upper_allowed_schemas:
                        return {
                            "valid": False,
                            "reason": (
                                "snowflake_schema_not_allowlisted"
                                if dialect == "snowflake"
                                else "schema_not_allowlisted"
                            ),
                            "role": role,
                            "schema": schema,
                            "unauthorized_schema": tbl_db,
                            "unauthorized_table": fq_name,
                        }
                    if schema is not None and tbl_db.upper() != schema.upper():
                        return {
                            "valid": False,
                            "reason": (
                                "snowflake_schema_not_allowlisted"
                                if dialect == "snowflake"
                                else "schema_not_allowlisted"
                            ),
                            "role": role,
                            "schema": schema,
                            "unauthorized_schema": tbl_db,
                            "unauthorized_table": fq_name,
                        }
                elif require_qualified_tables:
                    return {
                        "valid": False,
                        "reason": "unqualified_table_not_allowed",
                        "role": role,
                        "schema": schema,
                        "unauthorized_table": fq_name,
                    }
            elif schema is not None and tbl_db and tbl_db.upper() != schema.upper():
                return {
                    "valid": False,
                    "reason": "schema_not_allowlisted",
                    "role": role,
                    "schema": schema,
                    "unauthorized_schema": tbl_db,
                    "unauthorized_table": fq_name,
                }

            if upper_allowed_tables is not None:
                if not tbl_name:
                    return {
                        "valid": False,
                        "reason": "unauthorized_table_access",
                        "role": role,
                        "schema": schema,
                        "unauthorized_table": fq_name,
                    }
                if tbl_db:
                    allowed = f"{tbl_db}.{tbl_name}".upper() in upper_allowed_tables
                else:
                    if require_qualified_tables:
                        return {
                            "valid": False,
                            "reason": "unqualified_table_not_allowed",
                            "role": role,
                            "schema": schema,
                            "unauthorized_table": fq_name,
                        }
                    allowed = tbl_name.upper() in upper_allowed_tables
                if not allowed:
                    return {
                        "valid": False,
                        "reason": "unauthorized_table_access",
                        "role": role,
                        "schema": schema,
                        "unauthorized_table": fq_name,
                    }

        normalized = stmt.sql(dialect=dialect)
        return {
            "valid": True,
            "reason": "validated_readonly_query",
            "role": role,
            "schema": schema,
            "normalized_sql": normalized,
        }
