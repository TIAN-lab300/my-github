"""Persistent local vector indexing."""
from alembic import op

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE embedding_jobs (
        version_id TEXT PRIMARY KEY REFERENCES resource_versions(id),
        status TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0,
        lease_until TEXT, lease_token TEXT, error TEXT, updated_at TEXT NOT NULL)""")
    op.execute("""CREATE TABLE vector_chunks (
        id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES resource_versions(id),
        ordinal INTEGER NOT NULL, body TEXT NOT NULL, location TEXT NOT NULL,
        embedding TEXT NOT NULL, model TEXT NOT NULL,
        UNIQUE(version_id,ordinal))""")


def downgrade():
    raise RuntimeError('Restore a verified backup to preserve index history.')
