"""Opening a current catalog must not create a redundant SQLite transaction."""
from pathlib import Path
from contextlib import closing
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from asset_director.core import Library, SCHEMA, DirectorError


class CatalogOpenCase(unittest.TestCase):
    def test_current_catalog_open_does_not_commit_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            with Library(directory) as observer:
                before = observer.db.execute('PRAGMA data_version').fetchone()[0]
                with Library(directory) as reader:
                    self.assertEqual(reader.all(), [])
                    self.assertEqual(reader.db.execute('PRAGMA user_version').fetchone()[0], SCHEMA)
                self.assertEqual(observer.db.execute('PRAGMA data_version').fetchone()[0], before)

    def test_current_catalog_open_can_read_while_writer_is_uncommitted(self):
        connect = sqlite3.connect
        with tempfile.TemporaryDirectory() as directory:
            with Library(directory) as writer:
                writer.db.execute('BEGIN IMMEDIATE')
                try:
                    # Fail quickly if opening a reader unnecessarily requests a write lock.
                    with patch('asset_director.core.sqlite3.connect', side_effect=lambda *a, **k: connect(*a, **(k | {'timeout': .05}))):
                        with Library(directory) as reader:
                            self.assertEqual(reader.all(), [])
                finally:
                    writer.db.rollback()

    def test_unversioned_catalog_is_initialized_and_remains_writable(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'catalog.sqlite'
            sqlite3.connect(database).close()
            with Library(directory) as library:
                self.assertEqual(library.db.execute('PRAGMA user_version').fetchone()[0], SCHEMA)
                library.db.execute("INSERT INTO events(at,kind,data) VALUES(0,'synthetic','{}')")
                library.db.commit()
            with Library(directory) as library:
                self.assertEqual(library.db.execute('SELECT count(*) FROM events').fetchone()[0], 1)

    def test_unknown_version_is_refused_without_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'catalog.sqlite'
            with closing(sqlite3.connect(database)) as connection:
                connection.execute('PRAGMA user_version=999')
            with self.assertRaises(DirectorError):
                Library(directory)
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 999)
