import io
import shutil
import tarfile
from unittest.mock import patch

import pytest

from services.repo_ingest import fetch_repo_snapshot


def _create_sample_tarball(single_top_dir: bool = True) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        if single_top_dir:
            base = "owner-repo-sha123"
            t_dir = tarfile.TarInfo(name=base)
            t_dir.type = tarfile.DIRTYPE
            tf.addfile(t_dir)

            f_info = tarfile.TarInfo(name=f"{base}/index.ts")
            data = b"console.log('hello');"
            f_info.size = len(data)
            tf.addfile(f_info, io.BytesIO(data))
        else:
            f_info = tarfile.TarInfo(name="file1.txt")
            data = b"content"
            f_info.size = len(data)
            tf.addfile(f_info, io.BytesIO(data))
    return buf.getvalue()


@pytest.mark.asyncio
async def test_fetch_repo_snapshot_success():
    tar_bytes = _create_sample_tarball(single_top_dir=True)

    class MockStreamResp:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def aiter_bytes(self):
            yield tar_bytes

    class MockAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        def stream(self, method, url, headers=None):
            return MockStreamResp()

    with patch("services.repo_ingest.get_installation_token", return_value="test_token"):
        with patch("services.repo_ingest.httpx.AsyncClient", return_value=MockAsyncClient()):
            snapshot_path = await fetch_repo_snapshot("owner/repo", 12345, "main")
            try:
                assert snapshot_path.is_dir()
                assert (snapshot_path / "index.ts").exists()
                assert (snapshot_path / "index.ts").read_text() == "console.log('hello');"
            finally:
                shutil.rmtree(
                    snapshot_path.parent
                    if snapshot_path.name == "owner-repo-sha123"
                    else snapshot_path
                )


@pytest.mark.asyncio
async def test_fetch_repo_snapshot_http_error():
    class MockStreamResp:
        status_code = 404

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def aiter_bytes(self):
            yield b""

    class MockAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        def stream(self, method, url, headers=None):
            return MockStreamResp()

    with patch("services.repo_ingest.get_installation_token", return_value="test_token"):
        with patch("services.repo_ingest.httpx.AsyncClient", return_value=MockAsyncClient()):
            with pytest.raises(RuntimeError, match="tarball fetch failed"):
                await fetch_repo_snapshot("owner/repo", 12345, "main")


@pytest.mark.asyncio
async def test_fetch_repo_snapshot_size_limit():
    class MockStreamResp:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def aiter_bytes(self):
            yield b"x" * 2000

    class MockAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        def stream(self, method, url, headers=None):
            return MockStreamResp()

    with patch("services.repo_ingest.MAX_TARBALL_BYTES", 1000):
        with patch("services.repo_ingest.get_installation_token", return_value="test_token"):
            with patch("services.repo_ingest.httpx.AsyncClient", return_value=MockAsyncClient()):
                with pytest.raises(RuntimeError, match="exceeds 1000 bytes"):
                    await fetch_repo_snapshot("owner/repo", 12345, "main")
