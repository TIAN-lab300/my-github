"""Preserve goal revisions and diagnostic input versions."""
from alembic import op
import json
from uuid import uuid4
revision='0008'
down_revision='0007'
branch_labels=None
depends_on=None

def upgrade():
    op.execute("ALTER TABLE goals ADD COLUMN preference TEXT NOT NULL DEFAULT 'unspecified'")
    op.execute("""CREATE TABLE goal_revisions (
        id TEXT PRIMARY KEY, goal_id TEXT NOT NULL REFERENCES goals(id),
        version INTEGER NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(goal_id,version))""")
    connection=op.get_bind()
    for goal in connection.exec_driver_sql('SELECT * FROM goals').mappings().all():
        connection.exec_driver_sql('INSERT INTO goal_revisions VALUES (?,?,?,?,?)',
                                   (uuid4().hex,goal['id'],goal['version'],json.dumps(dict(goal),ensure_ascii=False),goal['created_at']))
    op.execute("ALTER TABLE diagnoses ADD COLUMN goal_version INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE diagnoses ADD COLUMN bank_version TEXT NOT NULL DEFAULT 'diagnostic-v1'")
    op.execute("ALTER TABLE diagnoses ADD COLUMN mastery_snapshot TEXT NOT NULL DEFAULT '{}'")

def downgrade():
    raise RuntimeError('Restore a verified backup to preserve goal history.')
