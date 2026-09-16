from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from notebook_harness import pocketbase_source


class EngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.db = Path(self._tmp.name) / "data.db"
        con = sqlite3.connect(self.db)
        con.execute("create table matches (id text primary key, name text)")
        con.execute("insert into matches values ('m1', 'alpha')")
        con.commit()
        con.close()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_engine_reads_rows(self) -> None:
        import sqlalchemy

        engine = pocketbase_source.engine(self.db)
        with engine.connect() as conn:
            rows = conn.execute(sqlalchemy.text("select name from matches")).fetchall()

        self.assertEqual([row[0] for row in rows], ["alpha"])

    def test_engine_refuses_writes(self) -> None:
        import sqlalchemy

        engine = pocketbase_source.engine(self.db)
        with self.assertRaises(sqlalchemy.exc.OperationalError) as caught:
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text("insert into matches values ('m2', 'beta')"))

        self.assertIn("readonly", str(caught.exception).lower())

    def test_engine_reads_while_another_connection_writes(self) -> None:
        # WAL means a reader must not block on a live writer. This is the
        # concurrency risk named in the spec, pinned as a test.
        import sqlalchemy

        writer = sqlite3.connect(self.db)
        writer.execute("pragma journal_mode=wal")
        writer.execute("begin")
        writer.execute("insert into matches values ('m3', 'gamma')")

        engine = pocketbase_source.engine(self.db)
        with engine.connect() as conn:
            rows = conn.execute(sqlalchemy.text("select count(*) from matches")).fetchall()

        writer.rollback()
        writer.close()
        self.assertEqual(rows[0][0], 1)

    def test_db_path_points_at_the_repo_database(self) -> None:
        self.assertEqual(pocketbase_source.db_path().name, "data.db")
        self.assertIn("pocketbase", str(pocketbase_source.db_path()))


class ApiTests(unittest.TestCase):
    def test_api_returns_decoded_json(self) -> None:
        calls = []

        def fake_request(method, url, json=None, timeout=None):
            calls.append((method, url, json))

            class Response:
                status_code = 200

                @staticmethod
                def json():
                    return {"bots": []}

                @staticmethod
                def raise_for_status():
                    return None

            return Response()

        result = pocketbase_source.api("GET", "/bots", transport=fake_request)

        self.assertEqual(result, {"bots": []})
        self.assertEqual(calls[0][0], "GET")
        self.assertTrue(calls[0][1].endswith("/bots"))

    def test_api_wraps_transport_failures(self) -> None:
        def broken(method, url, json=None, timeout=None):
            raise OSError("connection refused")

        with self.assertRaises(pocketbase_source.PocketBaseSourceError) as caught:
            pocketbase_source.api("GET", "/bots", transport=broken)

        self.assertIn("connection refused", str(caught.exception))

    def test_api_wraps_http_errors(self) -> None:
        def failing(method, url, json=None, timeout=None):
            class Response:
                status_code = 500

                @staticmethod
                def raise_for_status():
                    raise RuntimeError("500 Server Error")

            return Response()

        with self.assertRaises(pocketbase_source.PocketBaseSourceError):
            pocketbase_source.api("GET", "/bots", transport=failing)


if __name__ == "__main__":
    unittest.main()
