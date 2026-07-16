"""
HuggingFace → S3 sync tool with two transfer modes:

  stream  — Downloads byte ranges from HF CDN directly into memory and uploads
            to S3 via multipart. No local disk needed.

  xet     — Uses huggingface_hub's hf_hub_download (with hf_xet Rust backend)
            to download one file at a time to local disk, then uploads to S3 via
            boto3's optimized multipart upload. Deletes the local file after upload.
            Disk needed: max_file_size × file_workers.

Usage:
  python hf_s3_sync.py deepseek-ai/DeepSeek-V3 my-bucket --mode xet --file-workers 4
  python hf_s3_sync.py deepseek-ai/DeepSeek-V3 my-bucket --mode stream --file-workers 10
"""

import boto3
import boto3.s3.transfer
import requests
import concurrent.futures
import queue
import os
import threading
import time
import signal
import sys
import tempfile
from datetime import datetime, timezone
from huggingface_hub import HfApi, hf_hub_url, hf_hub_download


# ---------------------------------------------------------------------------
# Global state for graceful shutdown
# ---------------------------------------------------------------------------
_shutdown = threading.Event()
_active_uploads = []  # List of (s3_client, bucket, key, upload_id) tuples
_active_uploads_lock = threading.Lock()


def _signal_handler(signum, frame):
    """Handle SIGINT/SIGTERM: signal shutdown, cleanup happens after workers drain."""
    if _shutdown.is_set():
        print("\nForced exit.")
        sys.exit(1)
    sig_name = signal.Signals(signum).name
    print(f"\n⚠ Received {sig_name} — shutting down gracefully (press again to force)...")
    _shutdown.set()


def abort_tracked_uploads():
    """Abort all tracked multipart uploads."""
    with _active_uploads_lock:
        if not _active_uploads:
            return
        print(f"Aborting {len(_active_uploads)} incomplete multipart upload(s)...")
        for s3, bucket, key, upload_id in _active_uploads:
            try:
                s3.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
                print(f"  ✓ Aborted: {key}")
            except Exception as e:
                print(f"  ✗ Failed to abort {key}: {e}")
        _active_uploads.clear()
    print("Cleanup complete.")


def register_upload(s3, bucket, key, upload_id):
    with _active_uploads_lock:
        _active_uploads.append((s3, bucket, key, upload_id))


def unregister_upload(bucket, key, upload_id):
    with _active_uploads_lock:
        _active_uploads[:] = [
            entry for entry in _active_uploads
            if not (entry[1] == bucket and entry[2] == key and entry[3] == upload_id)
        ]


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_size(size_bytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def format_speed(bytes_per_sec):
    return f"{format_size(bytes_per_sec)}/s"


# ---------------------------------------------------------------------------
# Progress tracking (K8s-friendly periodic log lines)
# ---------------------------------------------------------------------------

class ProgressTracker:
    """Thread-safe progress tracker that prints periodic log lines."""

    def __init__(self, total: int, description: str, interval: float = 120):
        self.total = total
        self.description = description
        self.interval = interval
        self._transferred = 0
        self._lock = threading.Lock()
        self._start_time = time.time()
        self._last_print_time = 0

    def update(self, nbytes: int):
        now = time.time()
        with self._lock:
            self._transferred += nbytes
            if now - self._last_print_time >= self.interval:
                self._print_status(now)
                self._last_print_time = now

    def _print_status(self, now: float):
        elapsed = now - self._start_time
        speed = self._transferred / elapsed if elapsed > 0 else 0
        pct = (self._transferred / self.total * 100) if self.total > 0 else 0
        remaining = ""
        if speed > 0 and self.total > 0:
            eta_secs = (self.total - self._transferred) / speed
            remaining = f", ETA {eta_secs:.0f}s"
        print(
            f"  [{self.description}] {pct:.1f}% — "
            f"{format_size(self._transferred)}/{format_size(self.total)} "
            f"@ {format_speed(speed)}{remaining}"
        )

    def finish(self):
        now = time.time()
        with self._lock:
            self._print_status(now)


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------

def get_s3_file_info(s3, bucket: str, prefix: str) -> dict:
    """List all objects under a prefix and return {relative_key: {size, last_modified}}."""
    info = {}
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            rel_key = obj["Key"][len(prefix):].lstrip("/")
            info[rel_key] = {
                "size": obj["Size"],
                "last_modified": obj["LastModified"],
            }
    return info


def needs_transfer(filename: str, hf_size, hf_last_modified, existing: dict) -> str:
    """Determine if a file needs to be transferred. Returns reason string or None."""
    s3_info = existing.get(filename)

    if s3_info is None:
        return "new"

    if hf_size is not None and s3_info["size"] != hf_size:
        return f"size mismatch (HF: {format_size(hf_size)}, S3: {format_size(s3_info['size'])})"

    if hf_last_modified is not None:
        s3_modified = s3_info["last_modified"]
        if s3_modified.tzinfo is None:
            s3_modified = s3_modified.replace(tzinfo=timezone.utc)
        if hf_last_modified.tzinfo is None:
            hf_last_modified = hf_last_modified.replace(tzinfo=timezone.utc)
        if hf_last_modified > s3_modified:
            return f"newer on HF ({hf_last_modified:%Y-%m-%d %H:%M} > {s3_modified:%Y-%m-%d %H:%M})"

    return None


# ---------------------------------------------------------------------------
# Mode: XET (download file to disk, then upload to S3)
# ---------------------------------------------------------------------------

def _upload_file_to_s3(
    local_path: str,
    bucket: str,
    s3_key: str,
    max_upload_workers: int = 16,
    part_size: int = 100 * 1024 * 1024,
    progress_callback=None,
    transfer_client: str = "default",
):
    """Upload a local file to S3 using boto3's optimized multipart transfer.

    Args:
        transfer_client: "crt" to use the AWS CRT-based transfer client (faster,
                         requires awscrt package), or "default" for the classic
                         threading-based client.
    """
    s3 = boto3.client("s3")
    config_kwargs = {
        "multipart_threshold": part_size,
        "max_concurrency": max_upload_workers,
        "multipart_chunksize": part_size,
    }
    if transfer_client == "crt":
        config_kwargs["preferred_transfer_client"] = "crt"
    else:
        config_kwargs["use_threads"] = True
    config = boto3.s3.transfer.TransferConfig(**config_kwargs)
    callback = progress_callback if progress_callback else None
    s3.upload_file(local_path, bucket, s3_key, Config=config, Callback=callback)


def transfer_file_xet(
    repo_id: str,
    filename: str,
    bucket: str,
    s3_prefix: str,
    hf_token: str = None,
    temp_dir: str = None,
    max_upload_workers: int = 16,
    part_size: int = 100 * 1024 * 1024,
    overall_progress: ProgressTracker = None,
    transfer_client: str = "default",
):
    """Download a single file via hf_hub_download (Xet), upload to S3, delete local copy."""
    if _shutdown.is_set():
        return

    s3_key = f"{s3_prefix}/{filename}"
    file_start = time.time()

    # Download to local temp dir using huggingface_hub (uses hf_xet if installed)
    local_path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        token=hf_token,
        local_dir=temp_dir,
    )

    if _shutdown.is_set():
        return

    file_size = os.path.getsize(local_path)
    dl_elapsed = time.time() - file_start
    dl_speed = file_size / dl_elapsed if dl_elapsed > 0 else 0
    print(f"  ↓ {filename} — downloaded {format_size(file_size)} in {dl_elapsed:.1f}s ({format_speed(dl_speed)})")

    # Upload to S3
    upload_start = time.time()
    _upload_file_to_s3(
        local_path=local_path,
        bucket=bucket,
        s3_key=s3_key,
        max_upload_workers=max_upload_workers,
        part_size=part_size,
        progress_callback=overall_progress.update if overall_progress else None,
        transfer_client=transfer_client,
    )

    upload_elapsed = time.time() - upload_start
    upload_speed = file_size / upload_elapsed if upload_elapsed > 0 else 0

    # Delete local file to free disk space
    try:
        os.remove(local_path)
    except OSError:
        pass

    total_elapsed = time.time() - file_start
    print(
        f"  ✓ {filename} — {format_size(file_size)} "
        f"(↓{format_speed(dl_speed)} ↑{format_speed(upload_speed)}) "
        f"total {total_elapsed:.1f}s"
    )


# ---------------------------------------------------------------------------
# Mode: STREAM (range-request download → memory → S3 upload, no disk)
# ---------------------------------------------------------------------------

def _download_range(session: requests.Session, url: str, headers: dict, start: int, end: int) -> bytes:
    """Download a byte range from a URL using a session for connection reuse."""
    range_headers = {**headers, "Range": f"bytes={start}-{end}"}
    resp = session.get(url, headers=range_headers)
    resp.raise_for_status()
    return resp.content


def transfer_file_stream(
    repo_id: str,
    filename: str,
    bucket: str,
    s3_prefix: str,
    hf_token: str = None,
    part_size: int = 100 * 1024 * 1024,
    download_chunk_size: int = 16 * 1024 * 1024,
    max_upload_workers: int = 8,
    max_download_workers: int = 8,
    overall_progress: ProgressTracker = None,
    progress_interval: float = 120,
):
    """Transfer a file from HF to S3 via parallel range-request downloads piped to S3 uploads."""
    if _shutdown.is_set():
        return

    s3 = boto3.client("s3")
    s3_key = f"{s3_prefix}/{filename}"

    url = hf_hub_url(repo_id, filename)
    headers = {"Authorization": f"Bearer {hf_token}"} if hf_token else {}

    # Session with connection pooling
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=max_download_workers,
        pool_maxsize=max_download_workers,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Resolve CDN URL and get file size
    head_resp = session.head(url, headers=headers, allow_redirects=True)
    head_resp.raise_for_status()
    file_size = int(head_resp.headers.get("content-length", 0))
    download_url = head_resp.url

    if file_size == 0:
        session.close()
        print(f"  ⚠ {filename} — skipping (size unknown or 0)")
        return

    # Initiate multipart upload
    mpu = s3.create_multipart_upload(Bucket=bucket, Key=s3_key)
    upload_id = mpu["UploadId"]
    register_upload(s3, bucket, s3_key, upload_id)

    parts = []
    parts_lock = threading.Lock()
    file_start = time.time()

    file_progress = ProgressTracker(total=file_size, description=filename, interval=progress_interval)

    # Build download ranges (small chunks)
    download_ranges = []
    chunk_idx = 0
    offset = 0
    while offset < file_size:
        end = min(offset + download_chunk_size - 1, file_size - 1)
        download_ranges.append((chunk_idx, offset, end))
        chunk_idx += 1
        offset = end + 1

    # Upload queue + assembler state
    upload_queue = queue.Queue(maxsize=max_upload_workers * 2)
    upload_error = []
    upload_done = threading.Event()

    downloaded_chunks = {}
    downloaded_chunks_lock = threading.Lock()
    next_chunk_to_assemble = [0]
    assembly_buffer = bytearray()
    s3_part_number = [1]

    def _try_assemble():
        while next_chunk_to_assemble[0] in downloaded_chunks:
            chunk_data = downloaded_chunks.pop(next_chunk_to_assemble[0])
            assembly_buffer.extend(chunk_data)
            next_chunk_to_assemble[0] += 1
            while len(assembly_buffer) >= part_size:
                part_data = bytes(assembly_buffer[:part_size])
                del assembly_buffer[:part_size]
                pn = s3_part_number[0]
                s3_part_number[0] += 1
                upload_queue.put((pn, part_data))

    def _upload_consumer():
        while True:
            try:
                item = upload_queue.get(timeout=1)
            except queue.Empty:
                if upload_done.is_set():
                    return
                continue
            if item is None:
                return
            if _shutdown.is_set():
                return
            part_num, data = item
            try:
                part = s3.upload_part(
                    Bucket=bucket, Key=s3_key, UploadId=upload_id,
                    PartNumber=part_num, Body=data,
                )
                with parts_lock:
                    parts.append({"PartNumber": part_num, "ETag": part["ETag"]})
            except Exception as e:
                upload_error.append(e)

    def _download_chunk(chunk_idx: int, start: int, end: int):
        if _shutdown.is_set():
            return
        data = _download_range(session, download_url, headers, start, end)
        chunk_size = end - start + 1
        file_progress.update(chunk_size)
        if overall_progress:
            overall_progress.update(chunk_size)
        if _shutdown.is_set():
            return
        with downloaded_chunks_lock:
            downloaded_chunks[chunk_idx] = data
            _try_assemble()

    try:
        # Start upload consumers
        upload_threads = []
        for _ in range(max_upload_workers):
            t = threading.Thread(target=_upload_consumer, daemon=True)
            t.start()
            upload_threads.append(t)

        # Download chunks in parallel
        max_dl_workers = min(max_download_workers, len(download_ranges))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_dl_workers) as dl_executor:
            dl_futures = {
                dl_executor.submit(_download_chunk, idx, s, e): idx
                for idx, s, e in download_ranges
            }
            for future in concurrent.futures.as_completed(dl_futures):
                if _shutdown.is_set():
                    for f in dl_futures:
                        f.cancel()
                    break
                future.result()
                if upload_error:
                    raise upload_error[0]

        # Flush remaining assembly buffer
        with downloaded_chunks_lock:
            if assembly_buffer:
                pn = s3_part_number[0]
                s3_part_number[0] += 1
                upload_queue.put((pn, bytes(assembly_buffer)))
                assembly_buffer.clear()

        # Signal upload consumers to finish
        upload_done.set()
        for _ in upload_threads:
            upload_queue.put(None)
        for t in upload_threads:
            t.join()

        if _shutdown.is_set():
            raise InterruptedError("Shutdown requested")
        if upload_error:
            raise upload_error[0]

        # Complete multipart upload
        parts.sort(key=lambda p: p["PartNumber"])
        s3.complete_multipart_upload(
            Bucket=bucket, Key=s3_key, UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )
        unregister_upload(bucket, s3_key, upload_id)

        elapsed = time.time() - file_start
        speed = file_size / elapsed if elapsed > 0 else 0
        print(f"  ✓ {filename} — {format_size(file_size)} in {elapsed:.1f}s ({format_speed(speed)})")

    except InterruptedError:
        upload_done.set()
        for _ in upload_threads:
            upload_queue.put(None)
        raise
    except Exception as e:
        upload_done.set()
        for _ in upload_threads:
            try:
                upload_queue.put_nowait(None)
            except queue.Full:
                pass
        s3.abort_multipart_upload(Bucket=bucket, Key=s3_key, UploadId=upload_id)
        unregister_upload(bucket, s3_key, upload_id)
        print(f"  ✗ {filename} — FAILED: {e}")
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def sync_hf_repo_to_s3(
    repo_id: str,
    bucket: str,
    s3_prefix: str,
    mode: str = "xet",
    hf_token: str = None,
    part_size: int = 100 * 1024 * 1024,
    download_chunk_size: int = 16 * 1024 * 1024,
    max_upload_workers: int = 16,
    max_file_workers: int = 4,
    max_download_workers: int = 16,
    force: bool = False,
    progress_interval: float = 120,
    temp_dir: str = None,
    transfer_client: str = "default",
):
    """Sync a HuggingFace repo to S3.

    Args:
        mode: "xet" (download to disk via hf_xet, then upload) or "stream" (range-requests in memory)
        temp_dir: Local directory for temporary downloads (xet mode only)
        transfer_client: "crt" for AWS CRT-based uploads, "default" for classic threading
    """
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    s3 = boto3.client("s3")
    api = HfApi()
    repo_start = time.time()

    # --- List HF repo files ---
    print(f"Listing files in {repo_id}...")
    repo_info = api.repo_info(repo_id, token=hf_token, files_metadata=True)
    files_info = {}
    for sibling in repo_info.siblings:
        files_info[sibling.rfilename] = {
            "size": sibling.size,
            "last_modified": getattr(sibling, "last_modified", None) or getattr(sibling, "lastModified", None),
        }

    total_size = sum(f["size"] for f in files_info.values() if f["size"])
    file_list = list(files_info.keys())

    print(f"Found {len(file_list)} files, total size: {format_size(total_size)}")
    print(f"Destination: s3://{bucket}/{s3_prefix}/")
    print(f"Mode: {mode}")

    # --- Sync check ---
    if not force:
        print("Checking existing files in S3...")
        existing = get_s3_file_info(s3, bucket, s3_prefix)
        print(f"Found {len(existing)} existing files in S3")

        files_to_transfer = []
        skipped = 0
        skipped_size = 0

        for filename in file_list:
            hf_size = files_info[filename]["size"]
            hf_modified = files_info[filename]["last_modified"]
            reason = needs_transfer(filename, hf_size, hf_modified, existing)
            if reason is None:
                skipped += 1
                skipped_size += hf_size or 0
            else:
                files_to_transfer.append(filename)
                print(f"  → {filename}: {reason}")

        if skipped:
            print(f"Skipping {skipped} files already in sync ({format_size(skipped_size)})")
    else:
        files_to_transfer = file_list
        print("Force mode: re-uploading all files")

    if not files_to_transfer:
        print("Everything is in sync. Nothing to transfer.")
        return

    transfer_size = sum(files_info[f]["size"] or 0 for f in files_to_transfer)
    print(f"Transferring {len(files_to_transfer)} files ({format_size(transfer_size)})")

    if mode == "xet":
        print(f"Config: {max_file_workers} concurrent files, {max_upload_workers} upload workers/file, {format_size(part_size)} upload parts")
        print(f"Temp dir: {temp_dir}")
    else:
        print(f"Config: {max_file_workers} concurrent files, {max_download_workers} download workers/file, {max_upload_workers} upload workers/file")
        print(f"        Download chunk: {format_size(download_chunk_size)}, S3 upload part: {format_size(part_size)}")

    print("-" * 70)

    # --- Transfer ---
    overall_progress = ProgressTracker(total=transfer_size, description="TOTAL", interval=progress_interval)

    completed = 0
    failed = 0
    completed_lock = threading.Lock()

    def _transfer_file(filename):
        nonlocal completed, failed
        if mode == "xet":
            transfer_file_xet(
                repo_id=repo_id,
                filename=filename,
                bucket=bucket,
                s3_prefix=s3_prefix,
                hf_token=hf_token,
                temp_dir=temp_dir,
                max_upload_workers=max_upload_workers,
                part_size=part_size,
                overall_progress=overall_progress,
                transfer_client=transfer_client,
            )
        else:
            transfer_file_stream(
                repo_id=repo_id,
                filename=filename,
                bucket=bucket,
                s3_prefix=s3_prefix,
                hf_token=hf_token,
                part_size=part_size,
                download_chunk_size=download_chunk_size,
                max_upload_workers=max_upload_workers,
                max_download_workers=max_download_workers,
                overall_progress=overall_progress,
                progress_interval=progress_interval,
            )
        with completed_lock:
            completed += 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_file_workers) as executor:
        futures = {executor.submit(_transfer_file, f): f for f in files_to_transfer}
        for future in concurrent.futures.as_completed(futures):
            if _shutdown.is_set():
                for f in futures:
                    f.cancel()
                break
            filename = futures[future]
            try:
                future.result()
            except (InterruptedError, concurrent.futures.CancelledError):
                pass
            except Exception as e:
                print(f"  ✗ {filename} — FAILED: {e}")
                with completed_lock:
                    failed += 1

    if _shutdown.is_set():
        abort_tracked_uploads()

    overall_progress.finish()

    # --- Summary ---
    elapsed = time.time() - repo_start
    avg_speed = transfer_size / elapsed if elapsed > 0 else 0
    print("-" * 70)
    if _shutdown.is_set():
        print(f"Interrupted after {elapsed:.1f}s")
        print(f"Completed: {completed}/{len(files_to_transfer)} files before interruption")
    else:
        print(f"Completed: {completed}/{len(files_to_transfer)} files transferred")
    if failed:
        print(f"Failed: {failed} files")
    print(f"Transferred: {format_size(transfer_size)}")
    print(f"Total time: {elapsed:.1f}s")
    print(f"Average speed: {format_speed(avg_speed)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Sync a HuggingFace model repo to S3 (stream or xet mode).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s deepseek-ai/DeepSeek-V3 my-bucket --mode xet --file-workers 4
  %(prog)s deepseek-ai/DeepSeek-V3 my-bucket --mode stream --file-workers 10
  %(prog)s google/gemma-4-31B my-bucket --prefix models/gemma --mode xet
        """,
    )

    parser.add_argument("repo_id", help="HuggingFace repo ID (e.g. deepseek-ai/DeepSeek-V3)")
    parser.add_argument("bucket", help="S3 bucket name")
    parser.add_argument("--prefix", default=None, help="S3 key prefix (default: repo_id)")
    parser.add_argument("--token", default=None, help="HuggingFace API token (default: $HF_TOKEN)")
    parser.add_argument(
        "--mode", choices=["xet", "stream"], default="xet",
        help="Transfer mode: 'xet' downloads to disk via hf_xet then uploads, "
             "'stream' uses range-request downloads directly to S3 (default: xet)",
    )
    parser.add_argument(
        "--part-size", type=int, default=16,
        help="S3 multipart upload part size in MB (default: 16)",
    )
    parser.add_argument(
        "--download-chunk-size", type=int, default=16,
        help="[stream mode] Download range-request chunk size in MB (default: 16)",
    )
    parser.add_argument(
        "--upload-workers", type=int, default=16,
        help="Number of parallel S3 upload threads per file (default: 16)",
    )
    parser.add_argument(
        "--file-workers", type=int, default=4,
        help="Number of files to transfer concurrently (default: 4)",
    )
    parser.add_argument(
        "--download-workers", type=int, default=16,
        help="[stream mode] Parallel range-request downloads per file (default: 16)",
    )
    parser.add_argument(
        "--temp-dir", default=None,
        help="[xet mode] Local directory for temporary downloads (default: system temp)",
    )
    parser.add_argument("--force", action="store_true", help="Re-upload all files, ignoring sync check")
    parser.add_argument(
        "--progress-interval", type=int, default=120,
        help="Seconds between progress log lines (default: 120). Set to 0 for every chunk.",
    )
    parser.add_argument(
        "--transfer-client", choices=["default", "crt"], default="default",
        help="S3 upload client: 'crt' for AWS CRT-based (faster, requires awscrt), "
             "'default' for classic threading-based (default: default)",
    )

    args = parser.parse_args()

    s3_prefix = args.prefix if args.prefix else args.repo_id
    hf_token = args.token or os.environ.get("HF_TOKEN")

    # Resolve temp dir for xet mode
    temp_dir = args.temp_dir
    if args.mode == "xet" and temp_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="hf_sync_")
        print(f"Using temp directory: {temp_dir}")

    sync_hf_repo_to_s3(
        repo_id=args.repo_id,
        bucket=args.bucket,
        s3_prefix=s3_prefix,
        mode=args.mode,
        hf_token=hf_token,
        part_size=args.part_size * 1024 * 1024,
        download_chunk_size=args.download_chunk_size * 1024 * 1024,
        max_upload_workers=args.upload_workers,
        max_file_workers=args.file_workers,
        max_download_workers=args.download_workers,
        force=args.force,
        progress_interval=args.progress_interval,
        temp_dir=temp_dir,
        transfer_client=args.transfer_client,
    )


if __name__ == "__main__":
    main()
