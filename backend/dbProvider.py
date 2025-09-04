from typing import Optional, Sequence, Mapping, Any, List, Dict, Tuple, Union
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor


class PostgresClient:
    """
    Lightweight Postgres client using psycopg2.

    Initialize either with a DSN string (dsn=...) or connection pieces (host, port, dbname, user, password).
    Methods:
      - select_from_table(...)  -> fetch rows
      - insert_into_table(...)  -> insert a dict -> returns inserted rowcount or optionally inserted id
      - delete_from_table(...)  -> delete rows by where clause -> returns deleted rowcount

    Safety notes:
      - Table/column identifiers are composed with psycopg2.sql to avoid SQL injection.
      - Values are passed as parameters (%s) to queries.
      - For WHERE you can provide a dict (safe) or a raw where_sql + params (use carefully).
    """

    def __init__(
        self,
        *,
        host: Optional[str] = None,
        port: Optional[int] = None,
        dbname: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        connect_timeout: int = 10,
    ) -> None:
            self._conn_info = {
                "host": host,
                "port": port,
                "dbname": dbname,
                "user": user,
                "password": password,
                "connect_timeout": connect_timeout,
            }
            # remove None values (psycopg2 accepts missing keys)
            self._conn_info = {k: v for k, v in self._conn_info.items() if v is not None}

    def connect(self):
        """
        Create a new psycopg2 connection. Use with context manager:
            with client._get_connection() as conn:
                ...
        The connection context manager commits on success, rolls back on exception.
        """
        return psycopg2.connect(**self._conn_info)

    # Generic execute helper
    def _execute(
        self,
        query: sql.SQL,
        params: Optional[Sequence[Any]] = None,
        fetch: Optional[str] = None,
    ) -> Union[List[Dict[str, Any]], int, None]:
        """
        Execute a composed sql.SQL query with params.
        fetch: None (no fetch, returns rowcount), 'one' (fetchone), 'all' (fetchall)
        Returns:
          - list[dict] when fetch == 'all'
          - dict when fetch == 'one'
          - int (rowcount) when fetch is None
        """
        with self.connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch == "one":
                    return cur.fetchone()
                if fetch == "all":
                    return cur.fetchall()
                return cur.rowcount

    # Placeholder method: SELECT FROM <table>
    def select_from_table(
        self,
        table: str,
        columns: Optional[Sequence[str]] = None,
        where: Optional[Mapping[str, Any]] = None,
        where_sql: Optional[str] = None,
        where_params: Optional[Sequence[Any]] = None,
        order_by: Optional[Sequence[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Select rows from a table.

        - table: table name (string)
        - columns: list of column names (default: ['*'])
        - where: mapping of column -> value (safe). Combined with AND.
        - where_sql: raw WHERE clause (e.g. "created_at > %s AND status = %s") plus where_params
            Use where_sql only if you need complex conditions; prefer where dict otherwise.
        - order_by: list of column names to order by
        - limit: optional integer

        Returns list of dictionaries (each row as dict).
        """
        if columns:
            cols_sql = sql.SQL(", ").join([sql.Identifier(c) for c in columns])
        else:
            cols_sql = sql.SQL("*")

        table_sql = sql.Identifier(table)

        query = sql.SQL("SELECT {cols} FROM {table}").format(cols=cols_sql, table=table_sql)

        params: List[Any] = []

        # Build WHERE
        if where:
            where_parts = []
            for k, v in where.items():
                where_parts.append(sql.SQL("{} = %s").format(sql.Identifier(k)))
                params.append(v)
            where_sql_obj = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_parts)
            query = query + where_sql_obj
        elif where_sql:
            query = query + sql.SQL(" WHERE ") + sql.SQL(where_sql)
            if where_params:
                params.extend(where_params)

        # ORDER BY
        if order_by:
            order_sql = sql.SQL(", ").join([sql.Identifier(c) for c in order_by])
            query = query + sql.SQL(" ORDER BY ") + order_sql

        # LIMIT
        if limit is not None:
            query = query + sql.SQL(" LIMIT %s")
            params.append(limit)

        # Execute and fetch all
        return self._execute(query, params=params or None, fetch="all")  # type: ignore

    # Placeholder method: INSERT INTO <table>
    def insert_into_table(
        self,
        table: str,
        data: Mapping[str, Any],
        return_columns: Optional[Sequence[str]] = None,
    ) -> Union[int, Dict[str, Any], None]:
        """
        Insert a row into `table` using `data` mapping column->value.

        - data: mapping of column names to values. Must be non-empty.
        - return_columns: optional list of columns to RETURNING (e.g. ['id']).

        Returns:
          - if return_columns provided: the first returned row as dict
          - otherwise: number of rows inserted (should be 1)
        """
        if not data:
            raise ValueError("`data` cannot be empty for insert.")

        table_sql = sql.Identifier(table)
        cols = list(data.keys())
        values = list(data.values())

        cols_sql = sql.SQL(", ").join([sql.Identifier(c) for c in cols])
        placeholders = sql.SQL(", ").join(sql.Placeholder() * len(cols))

        base = sql.SQL("INSERT INTO {table} ({cols}) VALUES ({vals})").format(
            table=table_sql, cols=cols_sql, vals=placeholders
        )

        if return_columns:
            ret_sql = sql.SQL(", ").join([sql.Identifier(c) for c in return_columns])
            query = base + sql.SQL(" RETURNING ") + ret_sql
            return self._execute(query, params=values, fetch="one")  # returns dict
        else:
            return self._execute(base, params=values, fetch=None)  # returns rowcount

    # Placeholder method: DELETE FROM <table>
    def delete_from_table(
        self,
        table: str,
        where: Optional[Mapping[str, Any]] = None,
        where_sql: Optional[str] = None,
        where_params: Optional[Sequence[Any]] = None,
        limit: Optional[int] = None,
    ) -> int:
        """
        Delete rows from `table`. Provide either `where` dict (safe) or `where_sql` + params (use carefully).
        Returns the number of rows deleted.
        """
        if not where and not where_sql:
            raise ValueError("DELETE requires a where clause (where dict or where_sql).")

        table_sql = sql.Identifier(table)
        query = sql.SQL("DELETE FROM {table}").format(table=table_sql)

        params: List[Any] = []

        if where:
            where_parts = []
            for k, v in where.items():
                where_parts.append(sql.SQL("{} = %s").format(sql.Identifier(k)))
                params.append(v)
            query = query + sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_parts)
        elif where_sql:
            query = query + sql.SQL(" WHERE ") + sql.SQL(where_sql)
            if where_params:
                params.extend(where_params)

        if limit is not None:
            # Some Postgres installations support LIMIT in DELETE (Postgres supports it with USING)
            # Simpler approach: wrap in a subquery to delete only limited rows
            # This uses ctid which is Postgres-specific but effective for limiting.
            query = sql.SQL("DELETE FROM {table} WHERE ctid IN (SELECT ctid FROM {table}").format(
                table=table_sql
            )
            # Need to re-attach the previous WHERE condition inside the subquery
            if where:
                # rebuild where_parts to reuse
                where_parts = []
                for k in where.keys():
                    where_parts.append(sql.SQL("{} = %s").format(sql.Identifier(k)))
                query = query + sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_parts)
            elif where_sql:
                query = query + sql.SQL(" WHERE ") + sql.SQL(where_sql)
            query = query + sql.SQL(" LIMIT %s)")  # closing subquery
            params.append(limit)

        return self._execute(query, params=params or None, fetch=None)  # returns rowcount


# Example usage (replace credentials before running):
if __name__ == "__main__":
    client = PostgresClient(host="localhost", port=5432, dbname="mydb", user="me", password="secret")

    # SELECT example (safe)
    rows = client.select_from_table("users", columns=["id", "email"], where={"active": True}, limit=10)
    print("select rows:", rows)

    # INSERT example (returning id)
    inserted = client.insert_into_table("users", {"email": "new@example.com", "active": True}, return_columns=["id"])
    print("inserted:", inserted)

    # DELETE example (safe)
    deleted_count = client.delete_from_table("users", where={"email": "new@example.com"})
    print("deleted rows:", deleted_count)
