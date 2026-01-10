import unittest

import polars as pl

from youtube_to_docs.storage import NullStorage


class TestNullStorage(unittest.TestCase):
    def setUp(self):
        self.storage = NullStorage()

    def test_exists(self):
        self.assertFalse(self.storage.exists("any_path"))

    def test_read_text_raises_error(self):
        with self.assertRaises(FileNotFoundError):
            self.storage.read_text("any_path")

    def test_read_bytes_raises_error(self):
        with self.assertRaises(FileNotFoundError):
            self.storage.read_bytes("any_path")

    def test_write_text_returns_empty(self):
        self.assertEqual(self.storage.write_text("any_path", "content"), "")

    def test_write_bytes_returns_empty(self):
        self.assertEqual(self.storage.write_bytes("any_path", b"content"), "")

    def test_load_dataframe_returns_none(self):
        self.assertIsNone(self.storage.load_dataframe("any_path"))

    def test_save_dataframe_returns_empty(self):
        df = pl.DataFrame({"a": [1]})
        self.assertEqual(self.storage.save_dataframe(df, "any_path"), "")

    def test_upload_file_returns_empty(self):
        self.assertEqual(self.storage.upload_file("local", "target"), "")

    def test_get_full_path_returns_same(self):
        self.assertEqual(self.storage.get_full_path("any_path"), "any_path")

    def test_get_local_file_returns_none(self):
        self.assertIsNone(self.storage.get_local_file("any_path"))


if __name__ == "__main__":
    unittest.main()
