"""Initial schema with booking slot keys, soft-delete, webhook idempotency.

Revision ID: 001_initial
Revises:
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("picture", sa.String(500), nullable=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_token", sa.String(500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_session_token", "user_sessions", ["session_token"], unique=True)

    op.create_table(
        "properties",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.String(64), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("property_type", sa.String(50), nullable=False),
        sa.Column("area_sqft", sa.Float(), nullable=False),
        sa.Column("bedrooms", sa.Integer(), nullable=False),
        sa.Column("bathrooms", sa.Integer(), nullable=False),
        sa.Column("amenities", sa.JSON(), nullable=True),
        sa.Column("images", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_properties_owner_id", "properties", ["owner_id"])
    op.create_index("ix_properties_property_type", "properties", ["property_type"])
    op.create_index("ix_properties_status", "properties", ["status"])
    op.create_index("ix_properties_price", "properties", ["price"])
    op.create_index("ix_properties_status_type", "properties", ["status", "property_type"])
    op.create_index("ix_properties_owner_status", "properties", ["owner_id", "status"])

    op.create_table(
        "bookings",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("property_id", sa.String(64), sa.ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("owner_id", sa.String(64), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("booking_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("time_slot", sa.String(50), nullable=False),
        sa.Column("slot_key", sa.String(200), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("payment_status", sa.String(20), nullable=False),
        sa.Column("deposit_amount", sa.Float(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slot_key", name="uq_bookings_slot_key"),
    )
    op.create_index("ix_bookings_property_id", "bookings", ["property_id"])
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"])
    op.create_index("ix_bookings_owner_id", "bookings", ["owner_id"])
    op.create_index("ix_bookings_status", "bookings", ["status"])
    op.create_index("ix_bookings_property_date_status", "bookings", ["property_id", "booking_date", "status"])
    op.create_index("ix_bookings_user_status", "bookings", ["user_id", "status"])
    op.create_index("ix_bookings_owner_status", "bookings", ["owner_id", "status"])
    op.create_index("ix_bookings_expires_at", "bookings", ["expires_at"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("participants", sa.JSON(), nullable=False),
        sa.Column("participant_key", sa.String(200), nullable=False),
        sa.Column("property_id", sa.String(64), sa.ForeignKey("properties.id", ondelete="SET NULL"), nullable=True),
        sa.Column("last_message", sa.Text(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversations_participant_key", "conversations", ["participant_key"])
    op.create_index("ix_conversations_property_id", "conversations", ["property_id"])
    op.create_index("ix_conversations_last_message_at", "conversations", ["last_message_at"])

    op.create_table(
        "messages",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", sa.String(64), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("receiver_id", sa.String(64), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("attachment_url", sa.String(500), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])
    op.create_index("ix_messages_conversation_created", "messages", ["conversation_id", "created_at"])

    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.String(255), nullable=False),
        sa.Column("booking_id", sa.String(64), sa.ForeignKey("bookings.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payment_status", sa.String(20), nullable=False),
        sa.Column("extra_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_payment_transactions_session_id", "payment_transactions", ["session_id"], unique=True)
    op.create_index("ix_payment_transactions_booking_id", "payment_transactions", ["booking_id"])

    op.create_table(
        "processed_webhook_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", name="uq_processed_webhook_event_id"),
    )
    op.create_index("ix_processed_webhook_events_event_id", "processed_webhook_events", ["event_id"], unique=True)


def downgrade() -> None:
    op.drop_table("processed_webhook_events")
    op.drop_table("payment_transactions")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("bookings")
    op.drop_table("properties")
    op.drop_table("user_sessions")
    op.drop_table("users")
