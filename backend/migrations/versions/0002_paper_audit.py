"""Add isolated virtual-account books and append-only audit events."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "paper_accounts",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created", sa.Float, nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
    )
    op.create_index("ix_audit_events_created", "audit_events", ["created"])


def downgrade():
    op.drop_index("ix_audit_events_created", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("paper_accounts")
