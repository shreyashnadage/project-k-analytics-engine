"""Layer 1: Incremental sync — pull new records from public schema using watermarks."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from analytics_engine.db.models import SyncWatermark
from analytics_engine.db.public_models import AccountGroup, Ledger, StockItem, Voucher
from analytics_engine.pipeline.context import PipelineContext

logger = logging.getLogger(__name__)

BATCH_LIMIT = 10_000


class L1Sync:
    def __init__(self, session: Session):
        self._session = session

    def execute(self, ctx: PipelineContext) -> None:
        ctx.sync_stats.vouchers_pulled = self._pull_entity(
            ctx, "voucher", Voucher, Voucher.id, Voucher.tenant_id
        )
        ctx.sync_stats.ledgers_pulled = self._pull_entity(
            ctx, "ledger", Ledger, Ledger.id, Ledger.tenant_id
        )
        ctx.sync_stats.groups_pulled = self._pull_entity(
            ctx, "account_group", AccountGroup, AccountGroup.id, AccountGroup.tenant_id
        )
        ctx.sync_stats.stock_items_pulled = self._pull_entity(
            ctx, "stock_item", StockItem, StockItem.id, StockItem.tenant_id
        )

        logger.info(
            "L1 sync for %s: %d vouchers, %d ledgers, %d groups, %d stock_items",
            ctx.client_id,
            ctx.sync_stats.vouchers_pulled,
            ctx.sync_stats.ledgers_pulled,
            ctx.sync_stats.groups_pulled,
            ctx.sync_stats.stock_items_pulled,
        )

    def _pull_entity(self, ctx, entity_type, model, id_col, tenant_col) -> int:
        wm = self._get_or_create_watermark(ctx.client_id, entity_type)

        count = (
            self._session.query(id_col)
            .filter(id_col > wm.last_synced_id)
            .filter(tenant_col.in_(ctx.tenant_ids))
            .count()
        )

        if count > 0:
            max_id_row = (
                self._session.query(id_col)
                .filter(id_col > wm.last_synced_id)
                .filter(tenant_col.in_(ctx.tenant_ids))
                .order_by(id_col.desc())
                .first()
            )
            if max_id_row:
                wm.last_synced_id = max_id_row[0]
                wm.last_synced_at = datetime.now(timezone.utc)
                self._session.commit()

        return count

    def _get_or_create_watermark(self, client_id: str, entity_type: str) -> SyncWatermark:
        wm = (
            self._session.query(SyncWatermark)
            .filter_by(client_id=client_id, entity_type=entity_type)
            .first()
        )
        if wm is None:
            wm = SyncWatermark(
                client_id=client_id,
                entity_type=entity_type,
                last_synced_id=0,
            )
            self._session.add(wm)
            self._session.commit()
        return wm
