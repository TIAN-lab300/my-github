"""Private engineering scope proposals and direct catalogue evidence identities."""
from alembic import op
revision='0028'
down_revision='0027'

def upgrade():
    op.execute('''CREATE TABLE project_goal_proposals(id TEXT PRIMARY KEY,student_id TEXT NOT NULL REFERENCES users(id),
        description TEXT NOT NULL,mode TEXT NOT NULL,model_config_id TEXT REFERENCES model_configs(id),
        analysis TEXT NOT NULL,confirmed_goal_id TEXT REFERENCES goals(id),created_at TEXT NOT NULL)''')
    op.execute('''CREATE TABLE project_goal_contexts(goal_id TEXT PRIMARY KEY REFERENCES goals(id),
        proposal_id TEXT NOT NULL REFERENCES project_goal_proposals(id),graph_version TEXT NOT NULL UNIQUE REFERENCES graph_versions(id),
        skill_ids TEXT NOT NULL,analysis TEXT NOT NULL,relation_version TEXT REFERENCES curriculum_relation_versions(id),
        auto_enabled INTEGER NOT NULL DEFAULT 0,auto_mode TEXT NOT NULL DEFAULT 'local',auto_last_key TEXT,auto_error TEXT,created_at TEXT NOT NULL)''')
    op.execute('''CREATE TABLE project_evidence_links(student_id TEXT NOT NULL REFERENCES users(id),question_id TEXT NOT NULL,
        skill_id TEXT NOT NULL REFERENCES curriculum_catalog_skills(id),observation_id TEXT NOT NULL UNIQUE REFERENCES observations(id),
        origin TEXT NOT NULL,PRIMARY KEY(student_id,question_id))''')

def downgrade():raise RuntimeError('Restore a backup to preserve engineering goal evidence.')
