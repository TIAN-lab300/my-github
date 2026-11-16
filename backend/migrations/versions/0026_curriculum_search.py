"""Persist public course links and keep catalogue search separate from evidence FTS."""
from alembic import op
revision='0026'
down_revision='0025'

def upgrade():
    op.execute('''CREATE TABLE curriculum_course_links(id TEXT PRIMARY KEY,
        course_id TEXT NOT NULL REFERENCES curriculum_catalog_courses(id),title TEXT NOT NULL,
        school TEXT NOT NULL,platform TEXT NOT NULL,url TEXT NOT NULL,note TEXT NOT NULL,
        checked_at TEXT NOT NULL,verification TEXT NOT NULL,UNIQUE(course_id,url))''')
    op.execute("CREATE VIRTUAL TABLE curriculum_search_index USING fts5(course_id UNINDEXED,body,tokenize='unicode61')")
    # Existing installations get the same catalogue search on first upgrade;
    # fresh installations are populated by import_catalog after course import.
    from app.services.curriculum_search import rebuild
    rebuild(op.get_bind())

def downgrade():raise RuntimeError('Restore a verified backup to preserve course links.')
