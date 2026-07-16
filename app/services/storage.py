"""
app/services/storage.py

Cloud file upload service.
Supports: Dropbox (default) and local-only (no cloud).
Google Drive support can be added later via CLOUD_PROVIDER="gdrive".

Remote path structure:
  /Corporate Monitor/
    YYYY-MM-DD/
      HI/  CO/ ...
        CorpName.pdf
    daily_report_YYYY-MM-DD_run<id>.xlsx
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
# import dropbox
# from dropbox.files import WriteMode
# from dropbox.exceptions import ApiError

logger = logging.getLogger(__name__)


# ─── Public API ───────────────────────────────────────────────────────────────

def upload_run(run, app) -> None:
    """
    Upload all PDFs and the Excel report for *run* to the configured cloud.
    Updates ScanResult.cloud_link for each uploaded PDF.
    """
    with app.app_context():
        provider = app.config.get("CLOUD_PROVIDER", "none").lower()

        if provider == "none":
            logger.info("CLOUD_PROVIDER=none — skipping cloud upload.")
            return

        uploader = _get_uploader(provider, app)
        if uploader is None:
            logger.warning("No uploader for provider '%s'.", provider)
            return

        from app.models import ScanResult, DailyRun
        from app import db

        run_date = (run.started_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
        base = app.config.get("CLOUD_BASE_PATH", "/Corporate Monitor")

        # Upload Excel report
        if run.report_excel_path and os.path.exists(run.report_excel_path):
            remote = f"{base}/{os.path.basename(run.report_excel_path)}"
            link = uploader(run.report_excel_path, remote)
            if link:
                run.report_cloud_link = link
                db.session.commit()

        # Upload PDFs
        results = ScanResult.query.filter_by(daily_run_id=run.id).all()
        for r in results:
            if r.pdf_path and os.path.exists(r.pdf_path):
                state = r.corporation.state if r.corporation else "XX"
                remote = f"{base}/{run_date}/{state}/{os.path.basename(r.pdf_path)}"
                link = uploader(r.pdf_path, remote)
                if link:
                    r.cloud_link = link

        db.session.commit()


def upload_file(local_path: str, remote_path: str, app) -> str | None:
    """Upload a single file. Returns shared link or None."""
    provider = app.config.get("CLOUD_PROVIDER", "none").lower()
    uploader = _get_uploader(provider, app)
    if uploader:
        return uploader(local_path, remote_path)
    return None


# ─── Provider implementations ─────────────────────────────────────────────────

def _get_uploader(provider: str, app):
    """Return a callable(local_path, remote_path) -> link | None."""
    if provider == "dropbox":
        return _make_dropbox_uploader(app)
    logger.warning("Unknown CLOUD_PROVIDER: '%s'", provider)
    return None


def _make_dropbox_uploader(app):
    """Return a Dropbox upload function using the configured access token."""
    token = app.config.get("DROPBOX_ACCESS_TOKEN", "")
    if not token:
        logger.error("DROPBOX_ACCESS_TOKEN not configured.")
        return None

    # def _upload(local_path: str, remote_path: str) -> str | None:
    #     try:

    #         dbx = dropbox.Dropbox(token)
    #         with open(local_path, "rb") as f:
    #             dbx.files_upload(f.read(), remote_path, mode=WriteMode.overwrite)

    #         # Create shared link
    #         try:
    #             link_meta = dbx.sharing_create_shared_link_with_settings(remote_path)
    #             return link_meta.url
    #         except ApiError:
    #             # Link may already exist
    #             links = dbx.sharing_list_shared_links(path=remote_path, direct_only=True)
    #             if links.links:
    #                 return links.links[0].url
    #         return None

    #     except ImportError:
    #         logger.error("dropbox package not installed. Run: pip install dropbox")
    #         return None
    #     except Exception as exc:
    #         logger.error("Dropbox upload failed for '%s': %s", remote_path, exc)
    #         return None

    # return _upload
