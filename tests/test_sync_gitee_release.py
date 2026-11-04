import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import sync_gitee_release


class SyncGiteeReleaseTests(unittest.TestCase):
    def test_missing_token_skips_gracefully(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            count = sync_gitee_release.sync_gitee_release(token=None)
            self.assertEqual(count, 0)

    def test_dry_run_with_token_counts_zip_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir)
            (dir_path / "a.zip").write_bytes(b"PK01")
            (dir_path / "b.zip").write_bytes(b"PK02")
            (dir_path / "ignored.txt").write_bytes(b"text")

            count = sync_gitee_release.sync_gitee_release(
                token="mock_token",
                packages_dir=dir_path,
                dry_run=True,
            )
            self.assertEqual(count, 2)

    @mock.patch("tools.sync_gitee_release.upload_attachment")
    @mock.patch("tools.sync_gitee_release.create_release")
    @mock.patch("tools.sync_gitee_release.delete_release")
    @mock.patch("tools.sync_gitee_release.find_release_id_by_tag")
    def test_sync_recreates_and_uploads_cleanly(
        self,
        mock_find_release,
        mock_delete_release,
        mock_create_release,
        mock_upload_attachment,
    ):
        mock_find_release.return_value = 101
        mock_delete_release.return_value = True
        mock_create_release.return_value = 102
        mock_upload_attachment.return_value = True

        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir)
            (dir_path / "package1.zip").write_bytes(b"PK01")
            (dir_path / "package2.zip").write_bytes(b"PK02")

            count = sync_gitee_release.sync_gitee_release(
                token="mock_token",
                packages_dir=dir_path,
                dry_run=False,
            )
            self.assertEqual(count, 2)
            mock_delete_release.assert_called_once()
            mock_create_release.assert_called_once()
            self.assertEqual(mock_upload_attachment.call_count, 2)


if __name__ == "__main__":
    unittest.main()
