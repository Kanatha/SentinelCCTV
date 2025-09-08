import psycopg2
import psycopg2.extras
from typing import Optional, Any, List, Union


class dbProvider:
    """
    Lightweight DB helper using psycopg2 (C extension) for good performance.

    By default, SELECT/RETURNING queries return lists of lists (instead of tuples).
    Set dict_results=True to return list[dict] instead.
    """

    def __init__(
        self,
        *,
        dbname: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        host: Optional[str] = "db",
        port: int = 5432,
        connect_timeout: int = 10,
    ) -> None:
        conn_args = {}
        if dbname is not None:
            conn_args["dbname"] = dbname
        if user is not None:
            conn_args["user"] = user
        if password is not None:
            conn_args["password"] = password
        conn_args["host"] = host
        conn_args["port"] = port
        conn_args["connect_timeout"] = connect_timeout

        self._conn = psycopg2.connect(**conn_args)
        self._conn.autocommit = False

    def execute(
        self,
        query: str,
        params: Optional[Union[tuple, list]] = None,
        *,
        dict_results: Optional[bool] = None,
        fetch: str = "auto",
        raise_on_error: bool = True,
    ) -> Union[bool, List[List[Any]], List[dict]]:
        """
        Execute SQL and return results according to rules:
         - If the statement produces a result set (cursor.description), returns rows.
         - If no result set, commits and returns True on success.
         - On exception: rolls back. Raises or returns False per raise_on_error.
        """
        cursor_factory = (
            psycopg2.extras.RealDictCursor if dict_results else None
        )

        cur = self._conn.cursor(cursor_factory=cursor_factory)
        try:
            if params is None:
                cur.execute(query)
            else:
                cur.execute(query, params)

            if fetch == "one":
                if cur.description is None:
                    self._conn.commit()
                    return True
                row = cur.fetchone()
                if row is None:
                    return None
                if dict_results:
                    return row  # already dict
                return list(row)  # convert tuple -> list

            if fetch == "none":
                self._conn.commit()
                return True

            if cur.description is not None:
                rows = cur.fetchall()
                if dict_results:
                    return rows  # already list of dicts
                return [list(r) for r in rows]  # convert tuples -> lists
            else:
                self._conn.commit()
                return True

        except Exception:
            try:
                self._conn.rollback()
            except Exception:
                pass

            if raise_on_error:
                raise
            return False
        finally:
            try:
                cur.close()
            except Exception:
                pass

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self) -> "dbProvider":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
