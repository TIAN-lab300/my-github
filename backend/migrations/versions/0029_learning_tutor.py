"""Read-only learning tutor invocations, separate from planning and scoring."""
from alembic import op
revision='0029'
down_revision='0028'
def upgrade():
    op.execute('''CREATE TABLE tutor_runs(id TEXT PRIMARY KEY,actor_id TEXT NOT NULL REFERENCES users(id),
        course_id TEXT NOT NULL REFERENCES curriculum_catalog_courses(id),skill_id TEXT NOT NULL REFERENCES curriculum_catalog_skills(id),
        request_key TEXT NOT NULL,mode TEXT NOT NULL,level INTEGER NOT NULL,question TEXT NOT NULL,
        assessment_item_id TEXT,model_config_id TEXT REFERENCES model_configs(id),status TEXT NOT NULL,
        sources TEXT NOT NULL DEFAULT '[]',result TEXT NOT NULL DEFAULT '{}',error_code TEXT,
        elapsed_ms INTEGER,created_at TEXT NOT NULL,finished_at TEXT,UNIQUE(actor_id,request_key))''')
    op.execute('CREATE INDEX tutor_history ON tutor_runs(actor_id,course_id,created_at)')
def downgrade():raise RuntimeError('Restore a backup to preserve tutoring history.')
