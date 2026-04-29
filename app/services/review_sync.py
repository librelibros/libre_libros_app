"""Sincroniza el estado de las propuestas de cambio con GitHub.

Se llama desde el dashboard cuando el usuario abre la home: cualquier
ReviewRequest abierta o en borrador cuya última sincronización tenga más
de SYNC_TTL se reconsulta contra GitHub. Los errores se silencian y se
loguean — el dashboard nunca debe romperse porque GitHub esté caído.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.models import ReviewKind, ReviewRequest, ReviewStatus
from app.services.repository.factory import repository_client_for

_logger = logging.getLogger("libre_libros.review_sync")

SYNC_TTL = timedelta(minutes=5)


def _map_pr_state(payload: dict) -> ReviewStatus:
    if payload.get("merged_at") or payload.get("merged"):
        return ReviewStatus.merged
    if payload.get("draft"):
        return ReviewStatus.draft
    if payload.get("state") == "closed":
        return ReviewStatus.closed
    return ReviewStatus.open


def _map_issue_state(payload: dict) -> ReviewStatus:
    return ReviewStatus.closed if payload.get("state") == "closed" else ReviewStatus.open


def _is_fresh(review: ReviewRequest, now: datetime) -> bool:
    return review.last_synced_at is not None and (now - review.last_synced_at) < SYNC_TTL


def sync_review(db: Session, review: ReviewRequest) -> bool:
    """Sincroniza un único ReviewRequest. Devuelve True si lo refrescó."""
    if review.external_number is None or review.repository_source is None:
        return False
    try:
        client = repository_client_for(review.repository_source)
    except Exception:
        _logger.exception("review_sync: no se pudo construir cliente de repo")
        return False

    try:
        if review.kind == ReviewKind.pull_request:
            payload = client.fetch_pull_request(review.external_number)
            review.status = _map_pr_state(payload)
            review.commits_count = int(payload.get("commits") or 0)
            review.comments_count = int(payload.get("comments") or 0) + int(payload.get("review_comments") or 0)
        else:
            payload = client.fetch_issue(review.external_number)
            review.status = _map_issue_state(payload)
            review.comments_count = int(payload.get("comments") or 0)
        review.last_synced_at = datetime.utcnow()
        return True
    except httpx.HTTPStatusError as exc:
        _logger.warning(
            "review_sync: GitHub %s en %s #%s",
            exc.response.status_code,
            review.kind.value,
            review.external_number,
        )
    except Exception:
        _logger.exception("review_sync: error inesperado en %s #%s", review.kind.value, review.external_number)
    return False


def refresh_open_reviews(db: Session, *, limit: int = 25) -> int:
    """Refresca propuestas abiertas/draft cuya última sincronización está caducada.

    Devuelve cuántas se actualizaron. No conmitea por sí mismo — el caller
    decide si hace commit (típico: el dashboard antes de devolver la home).
    """
    now = datetime.utcnow()
    candidates = (
        db.query(ReviewRequest)
        .filter(ReviewRequest.status.in_([ReviewStatus.open, ReviewStatus.draft]))
        .order_by(ReviewRequest.created_at.desc())
        .limit(limit)
        .all()
    )
    refreshed = 0
    for review in candidates:
        if _is_fresh(review, now):
            continue
        if sync_review(db, review):
            refreshed += 1
    return refreshed
