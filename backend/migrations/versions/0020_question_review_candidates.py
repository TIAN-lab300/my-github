from alembic import op
revision='0020'
down_revision='0019'
branch_labels=None
depends_on=None
def upgrade():
    op.execute("CREATE TABLE question_source_packs(id TEXT PRIMARY KEY,payload TEXT NOT NULL,imported_at TEXT NOT NULL)")
    op.execute("CREATE TABLE question_review_candidates(id TEXT PRIMARY KEY,pack_id TEXT NOT NULL REFERENCES question_source_packs(id),skill_id TEXT NOT NULL REFERENCES curriculum_catalog_skills(id),payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending_teacher_review',imported_at TEXT NOT NULL)")
def downgrade():
    raise RuntimeError('Restore a verified backup.')
