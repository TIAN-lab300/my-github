"""Versioned course, chapter and knowledge prerequisite structure."""
from alembic import op
revision='0025'
down_revision='0024'

def upgrade():
    for sql in [
        '''CREATE TABLE curriculum_relation_versions(id TEXT PRIMARY KEY,payload_hash TEXT NOT NULL,
        basis TEXT NOT NULL,official_verified INTEGER NOT NULL DEFAULT 0 CHECK(official_verified=0),
        active INTEGER NOT NULL DEFAULT 0 CHECK(active IN(0,1)),created_at TEXT NOT NULL)''',
        'CREATE UNIQUE INDEX one_active_curriculum_relations ON curriculum_relation_versions(active) WHERE active=1',
        '''CREATE TABLE curriculum_course_prerequisites(version_id TEXT NOT NULL REFERENCES curriculum_relation_versions(id),
        before_id TEXT NOT NULL REFERENCES curriculum_catalog_courses(id),after_id TEXT NOT NULL REFERENCES curriculum_catalog_courses(id),
        kind TEXT NOT NULL CHECK(kind IN('required','recommended')),reason TEXT NOT NULL,
        PRIMARY KEY(version_id,before_id,after_id),CHECK(before_id!=after_id))''',
        '''CREATE TABLE curriculum_skill_prerequisites(version_id TEXT NOT NULL REFERENCES curriculum_relation_versions(id),
        before_id TEXT NOT NULL REFERENCES curriculum_catalog_skills(id),after_id TEXT NOT NULL REFERENCES curriculum_catalog_skills(id),
        kind TEXT NOT NULL CHECK(kind IN('required','recommended')),reason TEXT NOT NULL,
        PRIMARY KEY(version_id,before_id,after_id),CHECK(before_id!=after_id))''',
        '''CREATE TABLE curriculum_chapter_prerequisites(version_id TEXT NOT NULL REFERENCES curriculum_relation_versions(id),
        before_id TEXT NOT NULL REFERENCES learning_chapters(id),after_id TEXT NOT NULL REFERENCES learning_chapters(id),
        kind TEXT NOT NULL CHECK(kind IN('required','recommended')),reason TEXT NOT NULL,
        PRIMARY KEY(version_id,before_id,after_id),CHECK(before_id!=after_id))''',
        '''CREATE TABLE curriculum_external_requirements(version_id TEXT NOT NULL REFERENCES curriculum_relation_versions(id),
        course_id TEXT NOT NULL REFERENCES curriculum_catalog_courses(id),name TEXT NOT NULL,kind TEXT NOT NULL,
        reason TEXT NOT NULL,PRIMARY KEY(version_id,course_id,name))'''
    ]:op.execute(sql)

def downgrade():raise RuntimeError('Restore a verified backup; preserve prerequisite history.')
