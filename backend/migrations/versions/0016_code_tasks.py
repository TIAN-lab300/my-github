"""Frozen code test cases and exclusive grading leases."""
from alembic import op
revision='0016'
down_revision='0015'
branch_labels=None
depends_on=None


def upgrade():
    op.execute("ALTER TABLE tasks ADD COLUMN code_cases TEXT NOT NULL DEFAULT '[]'")
    op.execute("""CREATE TABLE code_runs (
        assignment_id TEXT PRIMARY KEY REFERENCES assignments(id),
        token TEXT NOT NULL, status TEXT NOT NULL, lease_until TEXT NOT NULL,
        error TEXT, updated_at TEXT NOT NULL)""")


def downgrade():
    raise RuntimeError('Restore a verified backup to preserve code grading history.')
