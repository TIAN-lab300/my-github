"""Persist profile invalidation and retry state alongside learning facts."""
from alembic import op
revision='0003'
down_revision='0002'
branch_labels=None
depends_on=None
def upgrade():
    op.get_bind().exec_driver_sql("CREATE TABLE profile_refresh_events(id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES users(id), source_watermark INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', snapshot_id TEXT, error TEXT, created_at TEXT NOT NULL, processed_at TEXT, UNIQUE(student_id,source_watermark))")
def downgrade():
    raise RuntimeError('Restore a verified backup instead of deleting history.')
