"""Versioned engineering delivery plans, immutable submissions and human acceptance."""
from alembic import op
revision='0030'
down_revision='0029'

def upgrade():
    for sql in [
        '''CREATE TABLE project_workspaces(goal_id TEXT PRIMARY KEY REFERENCES goals(id),
        spec TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,progress_version INTEGER NOT NULL DEFAULT 0,auto_last_key TEXT,auto_error TEXT,created_at TEXT NOT NULL)''',
        '''CREATE TABLE project_delivery_plans(id TEXT PRIMARY KEY,goal_id TEXT NOT NULL REFERENCES goals(id),
        status TEXT NOT NULL,payload TEXT NOT NULL,fingerprint TEXT NOT NULL,mode TEXT NOT NULL,created_at TEXT NOT NULL)''',
        "CREATE UNIQUE INDEX one_project_delivery_plan ON project_delivery_plans(goal_id) WHERE status='active'",
        '''CREATE TABLE project_milestones(id TEXT PRIMARY KEY,goal_id TEXT NOT NULL REFERENCES goals(id),
        milestone_key TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'not_started',
        actual_minutes INTEGER NOT NULL DEFAULT 0,UNIQUE(goal_id,milestone_key))''',
        '''CREATE TABLE project_deliveries(id TEXT PRIMARY KEY,milestone_id TEXT NOT NULL REFERENCES project_milestones(id),
        plan_id TEXT NOT NULL REFERENCES project_delivery_plans(id),student_id TEXT NOT NULL REFERENCES users(id),
        revision INTEGER NOT NULL,snapshot TEXT NOT NULL,evidence TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,UNIQUE(milestone_id,revision))''',
        '''CREATE TABLE project_delivery_reviews(id TEXT PRIMARY KEY,delivery_id TEXT NOT NULL REFERENCES project_deliveries(id),
        reviewer_id TEXT NOT NULL REFERENCES users(id),accepted INTEGER NOT NULL,checks TEXT NOT NULL,comment TEXT NOT NULL,created_at TEXT NOT NULL)''',
        '''CREATE TABLE project_worklogs(id TEXT PRIMARY KEY,student_id TEXT NOT NULL REFERENCES users(id),
        goal_id TEXT,source_id TEXT,class_id TEXT,minutes INTEGER NOT NULL,created_at TEXT NOT NULL)''',
        'CREATE INDEX project_delivery_history ON project_deliveries(milestone_id,revision)',
    ]:op.execute(sql)

def downgrade():raise RuntimeError('Restore a verified backup to preserve engineering submissions.')
