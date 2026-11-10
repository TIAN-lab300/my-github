"""Persist assignment drafts, submission timing, and published resource versions."""
from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("ALTER TABLE assignments ADD COLUMN draft TEXT NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE attempts ADD COLUMN late INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE attempts ADD COLUMN scoring_version TEXT NOT NULL DEFAULT 'assessment-v1'")
    op.execute("ALTER TABLE tasks ADD COLUMN resource_version_id TEXT")
    op.execute("""UPDATE attempts SET late=1 WHERE assignment_id IN (
        SELECT a.id FROM assignments a JOIN tasks t ON t.id=a.task_id
        WHERE attempts.created_at>t.due_at)""")
    op.execute("""UPDATE tasks SET resource_version_id=(SELECT current_version FROM resources
        WHERE resources.id=tasks.resource_id) WHERE status!='draft'""")

def downgrade():
    raise RuntimeError('Restore a verified backup to retain execution history.')
