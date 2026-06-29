"""Layer 2: Normalization — amount parsing, ledger classification, party normalization."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from analytics_engine.core.amount import parse_amount_to_paise
from analytics_engine.core.config import ConfigLoader
from analytics_engine.db.models import ClassifiedLedger, Party
from analytics_engine.db.public_models import Ledger, Voucher
from analytics_engine.pipeline.context import PipelineContext

logger = logging.getLogger(__name__)

# Standard categories in priority order for matching
STANDARD_CATEGORIES = [
    "cash", "bank", "sundry_debtors", "sundry_creditors",
    "sales", "purchase", "direct_expense", "indirect_expense",
    "fixed_asset", "current_asset", "current_liability",
    "capital", "duties_taxes", "loans_advances",
]


class L2Normalize:
    def __init__(self, session: Session, config_loader: ConfigLoader):
        self._session = session
        self._config = config_loader

    def execute(self, ctx: PipelineContext) -> None:
        self._classify_ledgers(ctx)
        self._normalize_parties(ctx)

    def _classify_ledgers(self, ctx: PipelineContext) -> None:
        classification_map = ctx.profile.ledger_classification
        # Build reverse lookup: tally_parent_name -> standard_category
        parent_to_category: dict[str, str] = {}
        for category, parent_names in classification_map.items():
            if category not in STANDARD_CATEGORIES:
                continue
            for name in parent_names:
                if name == "$inherit":
                    continue
                parent_to_category[name.lower()] = category

        # Pull all ledgers for this client's tenants
        ledgers = (
            self._session.query(Ledger)
            .filter(Ledger.tenant_id.in_(ctx.tenant_ids))
            .all()
        )

        count = 0
        for ledger in ledgers:
            existing = (
                self._session.query(ClassifiedLedger)
                .filter_by(ledger_id=ledger.id)
                .first()
            )

            category = self._resolve_category(ledger, parent_to_category)
            opening_paise = parse_amount_to_paise(ledger.opening_balance)
            closing_paise = parse_amount_to_paise(ledger.closing_balance)
            is_bank = category == "bank"
            is_cash = category == "cash"

            if existing:
                existing.standard_category = category
                existing.opening_balance_paise = opening_paise
                existing.closing_balance_paise = closing_paise
                existing.is_bank_account = is_bank
                existing.is_cash_account = is_cash
                existing.updated_at = datetime.now(timezone.utc)
            else:
                cl = ClassifiedLedger(
                    ledger_id=ledger.id,
                    client_id=ctx.client_id,
                    ledger_guid=ledger.ledger_guid,
                    name=ledger.name,
                    tally_parent=ledger.parent,
                    tally_type=ledger.ledger_type,
                    standard_category=category,
                    is_bank_account=is_bank,
                    is_cash_account=is_cash,
                    opening_balance_paise=opening_paise,
                    closing_balance_paise=closing_paise,
                )
                self._session.add(cl)
                count += 1

        self._session.commit()
        logger.info("L2 classified %d new ledgers for client %s", count, ctx.client_id)

    def _resolve_category(self, ledger: Ledger, parent_to_category: dict[str, str]) -> str:
        # Try ledger_type first (Tally's own classification)
        if ledger.ledger_type:
            lt = ledger.ledger_type.lower()
            if lt in parent_to_category:
                return parent_to_category[lt]

        # Try parent group name
        if ledger.parent:
            parent_lower = ledger.parent.lower()
            if parent_lower in parent_to_category:
                return parent_to_category[parent_lower]

        # Try ledger name itself for common patterns
        name_lower = (ledger.name or "").lower()
        if "cash" in name_lower and "discount" not in name_lower:
            return "cash"
        if "bank" in name_lower:
            return "bank"

        return "other"

    def _normalize_parties(self, ctx: PipelineContext) -> None:
        # Get all distinct party names from vouchers for this client
        party_rows = (
            self._session.query(Voucher.party, Voucher.voucher_type, Voucher.date)
            .filter(Voucher.tenant_id.in_(ctx.tenant_ids))
            .filter(Voucher.party.isnot(None))
            .filter(Voucher.party != "")
            .all()
        )

        # Group by normalized name (exact match for MVP — fuzzy dedup later)
        party_data: dict[str, dict] = {}
        for party_name, v_type, v_date in party_rows:
            canonical = party_name.strip()
            if not canonical:
                continue

            if canonical not in party_data:
                party_data[canonical] = {
                    "types": set(),
                    "first_date": v_date,
                    "last_date": v_date,
                }
            party_data[canonical]["types"].add(v_type)
            if v_date and (not party_data[canonical]["first_date"] or v_date < party_data[canonical]["first_date"]):
                party_data[canonical]["first_date"] = v_date
            if v_date and (not party_data[canonical]["last_date"] or v_date > party_data[canonical]["last_date"]):
                party_data[canonical]["last_date"] = v_date

        count = 0
        for canonical, data in party_data.items():
            existing = (
                self._session.query(Party)
                .filter_by(client_id=ctx.client_id, canonical_name=canonical)
                .first()
            )
            if existing:
                # Update date range
                if data["last_date"]:
                    from datetime import date as date_type
                    try:
                        last = date_type.fromisoformat(data["last_date"])
                        if not existing.last_seen_date or last > existing.last_seen_date:
                            existing.last_seen_date = last
                    except (ValueError, TypeError):
                        pass
                continue

            party_type = self._infer_party_type(data["types"])

            from datetime import date as date_type
            first_seen = None
            last_seen = None
            try:
                if data["first_date"]:
                    first_seen = date_type.fromisoformat(data["first_date"])
                if data["last_date"]:
                    last_seen = date_type.fromisoformat(data["last_date"])
            except (ValueError, TypeError):
                pass

            party = Party(
                party_id=str(uuid.uuid4()),
                client_id=ctx.client_id,
                canonical_name=canonical,
                party_type=party_type,
                aliases=json.dumps([canonical]),
                first_seen_date=first_seen,
                last_seen_date=last_seen,
            )
            self._session.add(party)
            count += 1

        self._session.commit()
        logger.info("L2 normalized %d new parties for client %s", count, ctx.client_id)

    @staticmethod
    def _infer_party_type(voucher_types: set[str]) -> str:
        has_sales = any(t in ("Sales", "Receipt", "Debit Note") for t in voucher_types)
        has_purchase = any(t in ("Purchase", "Payment", "Credit Note") for t in voucher_types)
        if has_sales and has_purchase:
            return "both"
        if has_sales:
            return "customer"
        if has_purchase:
            return "supplier"
        return "unknown"
