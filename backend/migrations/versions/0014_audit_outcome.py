"""Searchable outcomes for new and historical audit events."""
from alembic import op
revision='0014'
down_revision='0013'
branch_labels=None
depends_on=None


def upgrade():
    op.execute("ALTER TABLE audit_logs ADD COLUMN result TEXT NOT NULL DEFAULT 'success'")
    op.execute("UPDATE audit_logs SET result='failed' WHERE action IN ('login_failed','model_evaluation_failed')")
    op.execute('CREATE INDEX audit_outcome_time ON audit_logs(result,created_at)')


def downgrade():
    raise RuntimeError('Restore a verified backup to preserve audit results.')
