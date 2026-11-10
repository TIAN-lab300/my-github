"""Persistent resource parsing jobs."""
from alembic import op
revision='0005'
down_revision='0004'
branch_labels=None
depends_on=None

def upgrade():
    op.execute('''CREATE TABLE parse_jobs (
        id TEXT PRIMARY KEY, resource_version_id TEXT NOT NULL UNIQUE REFERENCES resource_versions(id),
        status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
        lease_token TEXT, lease_until TEXT, error TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')

def downgrade():
    op.drop_table('parse_jobs')
