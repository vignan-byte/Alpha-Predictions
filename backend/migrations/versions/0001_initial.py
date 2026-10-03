"""Initial normalized prediction ledger and typed JSON document store."""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "records",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("key", sa.String(240), nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("updated", sa.Float),
        sa.UniqueConstraint("kind", "key"),
    )
    op.create_index("ix_records_kind", "records", ["kind"])
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(240), unique=True, nullable=False),
        sa.Column("symbol", sa.String(30)),
        sa.Column("source", sa.String(30)),
        sa.Column("created", sa.Integer),
        sa.Column("due", sa.Integer),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("result", sa.Text),
    )
    for name in ["symbol", "source", "created", "due"]:
        op.create_index("ix_predictions_" + name, "predictions", [name])


def downgrade():
    op.drop_table("predictions")
    op.drop_table("records")
