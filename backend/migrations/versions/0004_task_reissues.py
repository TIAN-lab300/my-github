"""Retain task replacement relationships without rewriting published facts."""
from alembic import op
revision='0004'
down_revision='0003'
branch_labels=None
depends_on=None
def upgrade():
    op.get_bind().exec_driver_sql('CREATE TABLE task_reissues(task_id TEXT PRIMARY KEY REFERENCES tasks(id), previous_task_id TEXT NOT NULL REFERENCES tasks(id), created_at TEXT NOT NULL)')
def downgrade():
    raise RuntimeError('Use a verified backup to restore historical tasks.')
