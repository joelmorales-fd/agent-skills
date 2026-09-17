#!/usr/bin/env python3

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("extract-db-evidence.py")
SPEC = importlib.util.spec_from_file_location("extract_db_evidence", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExtractDbEvidenceTest(unittest.TestCase):
    def test_extracts_only_named_ddl_and_preloaded_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schema = root / "schema.sql"
            schema.write_text(
                "CREATE TABLE `wanted` (\n  `id` int NOT NULL\n) ENGINE=InnoDB;\n"
                "CREATE TABLE `other` (\n  `id` int NOT NULL\n) ENGINE=InnoDB;\n"
            )
            rows_file = root / "rows.xml"
            rows_file.write_text(
                "<note><case><input><row><id>1</id><name>keep</name></row>"
                "<row><id>2</id><name>drop</name></row><table>wanted</table>"
                "</input></case></note>"
            )

            ddl = MODULE.extract_ddl(schema, "wanted", 20)
            rows = MODULE.extract_rows(rows_file, "wanted", {"1"}, 5)

            self.assertIn("CREATE TABLE `wanted`", ddl["ddl"])
            self.assertNotIn("CREATE TABLE `other`", ddl["ddl"])
            self.assertEqual([{"id": "1", "name": "keep"}], rows["rows"])


if __name__ == "__main__":
    unittest.main()
