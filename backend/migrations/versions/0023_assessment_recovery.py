from alembic import op

revision = '0023'
down_revision = '0022'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE assessment_sessions ADD COLUMN minutes INTEGER NOT NULL DEFAULT 5")
    op.execute("ALTER TABLE assessment_sessions ADD COLUMN invalid_reason TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE assessment_sessions ADD COLUMN goal_version INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE question_exposures ADD COLUMN source TEXT NOT NULL DEFAULT 'session'")
    op.execute("CREATE UNIQUE INDEX assessment_attempt_unique ON assessment_sessions(attempt_id) WHERE attempt_id IS NOT NULL")
    op.execute("UPDATE assessment_sessions SET goal_version=(SELECT g.version FROM paths p JOIN goals g ON g.id=p.goal_id WHERE p.id=assessment_sessions.path_id)")


def downgrade():
    raise RuntimeError('Restore a verified backup.')
