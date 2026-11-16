"""Trace original bank releases and store project tasks without fabricated exam scores."""
from alembic import op
revision='0027'
down_revision='0026'

def upgrade():
    op.execute('''CREATE TABLE learning_bank_releases(id TEXT PRIMARY KEY,content_hash TEXT NOT NULL,
        provenance TEXT NOT NULL,review_kind TEXT NOT NULL,created_at TEXT NOT NULL)''')
    op.execute('''CREATE TABLE learning_bank_release_items(release_id TEXT NOT NULL REFERENCES learning_bank_releases(id),
        question_version_id TEXT NOT NULL UNIQUE REFERENCES learning_question_versions(id),
        PRIMARY KEY(release_id,question_version_id))''')
    op.execute('''CREATE TABLE learning_project_rubrics(id TEXT PRIMARY KEY,release_id TEXT NOT NULL REFERENCES learning_bank_releases(id),
        course_id TEXT NOT NULL,skill_id TEXT NOT NULL,payload TEXT NOT NULL,
        FOREIGN KEY(skill_id,course_id) REFERENCES curriculum_catalog_skills(id,course_id),
        UNIQUE(release_id,skill_id))''')

def downgrade():raise RuntimeError('Restore a verified backup to preserve assessment provenance.')
