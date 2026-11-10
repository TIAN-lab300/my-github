"""Require a persisted, reviewed evaluation before model activation."""
from alembic import op
revision='0017'
down_revision='0016'
branch_labels=None
depends_on=None


def upgrade():
    op.execute("UPDATE model_configs SET status='approved' WHERE status='active'")
    op.execute("""CREATE TABLE model_quality_reports (
        id TEXT PRIMARY KEY, model_config_id TEXT NOT NULL REFERENCES model_configs(id),
        operator TEXT NOT NULL, case_count INTEGER NOT NULL, passed_count INTEGER NOT NULL,
        payload TEXT NOT NULL, report_hash TEXT NOT NULL,
        review_status TEXT NOT NULL DEFAULT 'pending', reviewer_id TEXT REFERENCES users(id),
        review_comment TEXT, created_at TEXT NOT NULL, reviewed_at TEXT)""")


def downgrade():
    raise RuntimeError('Restore a verified backup to preserve quality review evidence.')
