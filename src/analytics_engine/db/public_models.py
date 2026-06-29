"""Read-only SQLAlchemy models mirroring the backend's public schema tables.

These are used by the analytics engine to query raw Tally data.
We never write to these tables — they are owned by the backend service.
"""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class PublicBase(DeclarativeBase):
    pass


class Tenant(PublicBase):
    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    api_key_hash = Column(String(64), unique=True)
    created_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean)


class Client(PublicBase):
    __tablename__ = "clients"

    client_id = Column(String(36), primary_key=True)
    company_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True)
    phone = Column(String(20))
    gst_id = Column(String(50))
    email_verified = Column(Boolean)
    status = Column(String(50))
    plan = Column(String(50))
    created_at = Column(DateTime(timezone=True))
    last_sync_at = Column(DateTime(timezone=True))


class DeviceRegistration(PublicBase):
    __tablename__ = "device_registrations"

    device_id = Column(String(36), primary_key=True)
    client_id = Column(String(36), nullable=False)
    device_name = Column(String(255))
    api_key = Column(String(500), unique=True)
    status = Column(String(50))
    last_sync_at = Column(DateTime(timezone=True))


class CompanyMapping(PublicBase):
    __tablename__ = "company_mappings"

    id = Column(Integer, primary_key=True)
    client_id = Column(String(36), nullable=False)
    device_id = Column(String(36), nullable=False)
    company_name = Column(String(500), nullable=False)
    company_guid = Column(String(255))
    formal_name = Column(String(500))
    gst_number = Column(String(50))
    state = Column(String(100))
    is_active = Column(Boolean)
    last_synced_at = Column(DateTime(timezone=True))


class Voucher(PublicBase):
    __tablename__ = "vouchers"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(36), nullable=False)
    company_guid = Column(String(255), nullable=False)
    voucher_guid = Column(String(255), nullable=False)
    voucher_type = Column(String(50), nullable=False)
    voucher_number = Column(String(100))
    date = Column(String(10), nullable=False)
    party = Column(String(500))
    narration = Column(Text)
    amount = Column(String(30))
    raw_data = Column(Text)
    received_at = Column(DateTime(timezone=True))
    agent_version = Column(String(20))


class Ledger(PublicBase):
    __tablename__ = "ledgers"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(36), nullable=False)
    company_guid = Column(String(255), nullable=False)
    ledger_guid = Column(String(255), nullable=False)
    name = Column(String(500), nullable=False)
    parent = Column(String(500))
    ledger_type = Column(String(100))
    opening_balance = Column(String(30))
    closing_balance = Column(String(30))
    received_at = Column(DateTime(timezone=True))


class AccountGroup(PublicBase):
    __tablename__ = "account_groups"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(36), nullable=False)
    company_guid = Column(String(255), nullable=False)
    group_guid = Column(String(255), nullable=False)
    name = Column(String(500), nullable=False)
    parent = Column(String(500))
    is_revenue = Column(String(10))
    received_at = Column(DateTime(timezone=True))


class StockItem(PublicBase):
    __tablename__ = "stock_items"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(36), nullable=False)
    company_guid = Column(String(255), nullable=False)
    item_guid = Column(String(255), nullable=False)
    name = Column(String(500), nullable=False)
    parent = Column(String(500))
    base_units = Column(String(100))
    opening_balance = Column(String(30))
    closing_balance = Column(String(30))
    hsn_code = Column(String(50))
    gst_rate = Column(String(20))
    received_at = Column(DateTime(timezone=True))


class StockGroup(PublicBase):
    __tablename__ = "stock_groups"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(36), nullable=False)
    company_guid = Column(String(255), nullable=False)
    group_guid = Column(String(255), nullable=False)
    name = Column(String(500), nullable=False)
    parent = Column(String(500))
    received_at = Column(DateTime(timezone=True))


class SyncRecord(PublicBase):
    __tablename__ = "sync_records"

    sync_id = Column(String(36), primary_key=True)
    client_id = Column(String(36), nullable=False)
    device_id = Column(String(36))
    tenant_id = Column(String(36))
    records_count = Column(Integer)
    extracted_ledgers = Column(Integer)
    extracted_vouchers = Column(Integer)
    sync_status = Column(String(50))
    sync_timestamp = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True))
