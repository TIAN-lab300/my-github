"""Persist external search provenance and user-scoped results."""
from alembic import op
revision='0012'
down_revision='0011'
branch_labels=None
depends_on=None


def upgrade():
    op.execute("""CREATE TABLE search_runs (
        id TEXT PRIMARY KEY, actor_id TEXT NOT NULL REFERENCES users(id),
        query TEXT NOT NULL, status TEXT NOT NULL, rounds INTEGER NOT NULL,
        results TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL)""")


def downgrade():
    raise RuntimeError('Restore a verified backup to preserve search evidence.')
