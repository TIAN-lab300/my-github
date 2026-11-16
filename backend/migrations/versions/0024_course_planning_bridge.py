"""Explicit reviewed course-to-graph mappings and unique assessment evidence."""
from alembic import op
revision='0024'
down_revision='0023'

def upgrade():
    for sql in [
        '''CREATE TABLE curriculum_graph_mappings(id TEXT PRIMARY KEY,course_id TEXT NOT NULL,
        skill_id TEXT NOT NULL,graph_version TEXT NOT NULL,graph_skill_id TEXT NOT NULL,
        reviewer_id TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        UNIQUE(skill_id,graph_version),UNIQUE(graph_version,graph_skill_id),
        FOREIGN KEY(skill_id,course_id) REFERENCES curriculum_catalog_skills(id,course_id))''',
        '''CREATE TABLE course_goal_bindings(goal_id TEXT PRIMARY KEY REFERENCES goals(id),
        course_id TEXT NOT NULL REFERENCES curriculum_catalog_courses(id),graph_version TEXT NOT NULL,
        mappings TEXT NOT NULL,initial_assessment_id TEXT NOT NULL UNIQUE REFERENCES learning_assessments(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE course_evidence_attempts(assessment_id TEXT PRIMARY KEY REFERENCES learning_assessments(id),
        attempt_id TEXT NOT NULL UNIQUE REFERENCES attempts(id))''',
        '''CREATE TABLE learning_evidence_links(item_id TEXT PRIMARY KEY REFERENCES learning_assessment_items(id),
        observation_id TEXT NOT NULL UNIQUE REFERENCES observations(id),
        mapping_id TEXT NOT NULL REFERENCES curriculum_graph_mappings(id),
        student_id TEXT NOT NULL REFERENCES users(id),question_id TEXT NOT NULL REFERENCES learning_questions(id),
        UNIQUE(student_id,question_id))'''
    ]:op.execute(sql)

def downgrade():
    raise RuntimeError('Restore a verified backup; do not discard assessment evidence.')
