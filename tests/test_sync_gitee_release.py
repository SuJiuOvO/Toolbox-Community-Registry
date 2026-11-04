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
    @mock.patch("tools.sync_gitee_release.delete_attachment")
    @mock.patch("tools.sync_gitee_release.list_existing_attachments")
    @mock.patch("tools.sync_gitee_release.get_or_create_release")
    def test_sync_uploads_and_overwrites_existing(
        self,
        mock_get_release,
        mock_list_att,
        mock_delete,
        mock_upload,
    ):
        mock_get_release.return_value = 999
        mock_list_att.return_value = {"existing.zip": 123}
        mock_upload.return_value = True
        mock_delete.return_value = True

        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir)
            (dir_path / "existing.zip").write_bytes(b"PK01")
            (dir_path / "new.zip").write_bytes(b"PK02")

            count = sync_gitee_release.sync_gitee_release(
                token="mock_token",
                packages_dir=dir_path,
                dry_run=False,
            )
            self.assertEqual(count, 2)
            mock_delete.assert_called_once()
            self.assertEqual(mock_upload.call_count, 2)


if __name__ == "__main__":
    unittest.main()
