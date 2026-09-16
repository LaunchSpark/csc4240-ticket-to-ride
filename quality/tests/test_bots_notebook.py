from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


NOTEBOOK = (
    Path(__file__).resolve().parents[2]
    / "applications"
    / "notebook_harness"
    / "bots.py"
)


def load_notebook():
    spec = importlib.util.spec_from_file_location("bots_notebook", NOTEBOOK)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BotsNotebookTests(unittest.TestCase):
    def test_local_rows_describe_every_discovered_bot(self) -> None:
        module = load_notebook()
        rows = module.local_bot_rows()

        self.assertTrue(rows, "expected at least one local bot")
        ids = {row["bot_id"] for row in rows}
        self.assertIn("random_bot", ids)

        row = next(r for r in rows if r["bot_id"] == "random_bot")
        self.assertEqual(row["name"], "Random Bot")
        self.assertEqual(row["notebook"], "random_bot.py")

    def test_notebook_name_comes_from_the_module_path_not_the_bot_id(self) -> None:
        # BOT_META["id"] and the filename are independent; deriving one from the
        # other breaks as soon as they diverge.
        module = load_notebook()
        for row in module.local_bot_rows():
            self.assertTrue(row["notebook"].endswith(".py"))
            self.assertNotIn("/", row["notebook"])

    def test_remote_rows_ignore_local_entries(self) -> None:
        module = load_notebook()
        payload = {
            "bots": [
                {"botId": "a", "name": "A", "version": "1", "source": "local",
                 "connectionId": None, "baseUrl": None},
                {"botId": "b", "name": "B", "version": "2", "source": "remote",
                 "connectionId": "c1", "baseUrl": "http://host:9000"},
            ],
            "connections": [],
        }

        rows = module.remote_bot_rows(payload)

        self.assertEqual([row["bot_id"] for row in rows], ["b"])
        self.assertEqual(rows[0]["base_url"], "http://host:9000")

    def test_remote_rows_tolerate_an_empty_payload(self) -> None:
        module = load_notebook()

        self.assertEqual(module.remote_bot_rows({}), [])

    def test_notebook_link_is_a_relative_file_query(self) -> None:
        module = load_notebook()

        self.assertEqual(module.notebook_link("random_bot.py"), "?file=random_bot.py")


if __name__ == "__main__":
    unittest.main()
