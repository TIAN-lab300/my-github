"""Versioned graphs, run traces, and independent remediation tasks."""
from alembic import op
revision='0009'
down_revision='0008'
branch_labels=None
depends_on=None

def upgrade():
    op.execute("ALTER TABLE graph_versions ADD COLUMN active INTEGER NOT NULL DEFAULT 0")
    op.execute("CREATE UNIQUE INDEX one_active_graph ON graph_versions(active) WHERE active=1")
    op.execute("ALTER TABLE agent_runs ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE agent_steps ADD COLUMN input_fingerprint TEXT NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE agent_steps ADD COLUMN output_summary TEXT NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE agent_steps ADD COLUMN attempt_no INTEGER NOT NULL DEFAULT 0")
    op.execute("""CREATE TABLE remediation_tasks (
        id TEXT PRIMARY KEY, path_id TEXT NOT NULL REFERENCES paths(id),
        skill TEXT NOT NULL, source_item_id TEXT, status TEXT NOT NULL,
        minutes INTEGER NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(path_id,skill))""")

def downgrade():
    raise RuntimeError('Restore a verified backup to preserve planning history.')
