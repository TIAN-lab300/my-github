"""Freeze execution mode and model configuration per planning run."""
from alembic import op
revision='0013'
down_revision='0012'
branch_labels=None
depends_on=None


def upgrade():
    op.execute("ALTER TABLE model_configs ADD COLUMN timeout_seconds INTEGER NOT NULL DEFAULT 45")
    op.execute("ALTER TABLE model_configs ADD COLUMN max_tokens INTEGER NOT NULL DEFAULT 2048")
    op.execute("ALTER TABLE model_configs ADD COLUMN temperature REAL NOT NULL DEFAULT 0.2")
    op.execute("ALTER TABLE model_configs ADD COLUMN prompt_version TEXT NOT NULL DEFAULT 'zhixing-v1'")
    op.execute("ALTER TABLE agent_runs ADD COLUMN execution_mode TEXT NOT NULL DEFAULT 'local'")
    op.execute("ALTER TABLE agent_runs ADD COLUMN model_config_id TEXT REFERENCES model_configs(id)")


def downgrade():
    raise RuntimeError('Restore a verified backup to preserve model and execution provenance.')
