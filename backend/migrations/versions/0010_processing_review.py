"""Local extraction metadata and explicit review gating."""
from alembic import op

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE resource_versions ADD COLUMN extraction_json TEXT NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE resource_versions ADD COLUMN review_status TEXT NOT NULL DEFAULT 'not_required'")
    op.execute("ALTER TABLE parse_jobs ADD COLUMN operation TEXT NOT NULL DEFAULT 'text'")


def downgrade():
    raise RuntimeError('Restore a verified backup to preserve extraction and review history.')
