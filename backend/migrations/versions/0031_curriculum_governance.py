"""Canonical aliases, immutable revisions and explicit automated validation evidence."""
from alembic import op
revision='0031'
down_revision='0030'

def upgrade():
    for sql in [
        '''CREATE TABLE knowledge_id_aliases(namespace TEXT NOT NULL,alias TEXT NOT NULL,
        skill_id TEXT NOT NULL REFERENCES curriculum_catalog_skills(id),
        PRIMARY KEY(namespace,alias))''',
        '''CREATE TABLE curriculum_object_revisions(id TEXT PRIMARY KEY,object_type TEXT NOT NULL,
        object_id TEXT NOT NULL,content_hash TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,
        UNIQUE(object_type,object_id,content_hash))''',
        '''CREATE TABLE curriculum_validation_events(id TEXT PRIMARY KEY,revision_id TEXT NOT NULL
        REFERENCES curriculum_object_revisions(id),method TEXT NOT NULL,status TEXT NOT NULL,
        checks TEXT NOT NULL,reviewer_id TEXT REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE goal_curriculum_dependencies(goal_id TEXT NOT NULL REFERENCES goals(id),
        object_type TEXT NOT NULL,object_id TEXT NOT NULL,revision_id TEXT NOT NULL
        REFERENCES curriculum_object_revisions(id),PRIMARY KEY(goal_id,object_type,object_id))''',
        "INSERT INTO knowledge_id_aliases SELECT 'canonical',id,id FROM curriculum_catalog_skills",
        "INSERT INTO knowledge_id_aliases SELECT 'legacy_catalog','catalog:'||id,id FROM curriculum_catalog_skills",
        "INSERT OR IGNORE INTO knowledge_id_aliases SELECT 'graph:'||graph_version,graph_skill_id,skill_id FROM curriculum_graph_mappings",
        "CREATE TRIGGER curriculum_revision_no_update BEFORE UPDATE ON curriculum_object_revisions BEGIN SELECT RAISE(ABORT,'immutable curriculum revision'); END",
        "CREATE TRIGGER curriculum_validation_no_update BEFORE UPDATE ON curriculum_validation_events BEGIN SELECT RAISE(ABORT,'immutable validation event'); END",
    ]:op.execute(sql)

def downgrade():raise RuntimeError('Restore a verified backup; revision evidence must be preserved.')
