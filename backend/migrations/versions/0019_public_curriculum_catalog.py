"""Persist draft curriculum and public-source provenance separately from exam banks."""
from alembic import op
revision='0019'
down_revision='0018'
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE curriculum_catalog_courses (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, year INTEGER, category TEXT NOT NULL,
        elective INTEGER NOT NULL, assessment_mode TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft', source_basis TEXT NOT NULL)""")
    op.execute("""CREATE TABLE curriculum_catalog_skills (
        id TEXT PRIMARY KEY, course_id TEXT NOT NULL REFERENCES curriculum_catalog_courses(id),
        name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending_syllabus_review')""")
    op.execute("""CREATE TABLE public_source_catalog (
        id TEXT PRIMARY KEY, resource_id TEXT NOT NULL UNIQUE REFERENCES resources(id),
        url TEXT NOT NULL, original_language TEXT NOT NULL, metadata_json TEXT NOT NULL,
        import_hash TEXT NOT NULL, imported_at TEXT NOT NULL)""")
    op.execute("""CREATE TABLE curriculum_catalog_sources (
        course_id TEXT NOT NULL REFERENCES curriculum_catalog_courses(id),
        source_id TEXT NOT NULL REFERENCES public_source_catalog(id),
        status TEXT NOT NULL DEFAULT 'course_level_candidate',
        PRIMARY KEY(course_id,source_id))""")

def downgrade():
    raise RuntimeError('Restore a verified backup to preserve imported source provenance.')
