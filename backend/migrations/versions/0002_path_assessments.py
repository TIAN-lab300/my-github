"""Stable path-task assessments and frozen graph metadata."""
from alembic import op
revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None

def upgrade():
    db=op.get_bind()
    db.exec_driver_sql('CREATE TABLE path_assessments(path_id TEXT REFERENCES paths(id), item_id TEXT, attempt_id TEXT UNIQUE REFERENCES attempts(id), PRIMARY KEY(path_id,item_id))')
    db.exec_driver_sql('CREATE TABLE graph_versions(id TEXT PRIMARY KEY, nodes TEXT NOT NULL, edges TEXT NOT NULL, created_at TEXT NOT NULL, owner_id TEXT REFERENCES users(id))')

def downgrade():
    raise RuntimeError('Restore a verified backup instead of deleting history.')
