"""Course/skill/material/question/assessment relations; preserve existing draft catalogs."""
from alembic import op
revision='0021'
down_revision='0020'
branch_labels=None
depends_on=None

def upgrade():
    statements=[
    'CREATE UNIQUE INDEX catalog_skill_course ON curriculum_catalog_skills(id,course_id)',
    """CREATE TABLE learning_chapters(id TEXT PRIMARY KEY,course_id TEXT NOT NULL REFERENCES curriculum_catalog_courses(id),
      title TEXT NOT NULL,position INTEGER NOT NULL CHECK(position>=0),UNIQUE(course_id,position),UNIQUE(id,course_id))""",
    """CREATE TABLE learning_material_links(id TEXT PRIMARY KEY,course_id TEXT NOT NULL,skill_id TEXT NOT NULL,
      resource_id TEXT NOT NULL REFERENCES resources(id),resource_version_id TEXT NOT NULL REFERENCES resource_versions(id),
      locator TEXT NOT NULL DEFAULT '',UNIQUE(skill_id,resource_version_id),
      FOREIGN KEY(skill_id,course_id) REFERENCES curriculum_catalog_skills(id,course_id))""",
    """CREATE TABLE learning_skill_chapters(skill_id TEXT PRIMARY KEY,chapter_id TEXT NOT NULL,course_id TEXT NOT NULL,
      FOREIGN KEY(skill_id,course_id) REFERENCES curriculum_catalog_skills(id,course_id),
      FOREIGN KEY(chapter_id,course_id) REFERENCES learning_chapters(id,course_id))""",
    """CREATE TABLE learning_questions(id TEXT PRIMARY KEY,course_id TEXT NOT NULL REFERENCES curriculum_catalog_courses(id),
      owner_id TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,UNIQUE(id,course_id))""",
    """CREATE TABLE learning_question_versions(id TEXT PRIMARY KEY,question_id TEXT NOT NULL,course_id TEXT NOT NULL,
      skill_id TEXT NOT NULL,version INTEGER NOT NULL CHECK(version>0),phase TEXT NOT NULL CHECK(phase IN ('diagnostic','practice','retest')),
      prompt TEXT NOT NULL,options TEXT NOT NULL,answer INTEGER NOT NULL CHECK(answer>=0),explanation TEXT NOT NULL,
      source TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published','disabled')),
      reviewer_id TEXT REFERENCES users(id),created_at TEXT NOT NULL,UNIQUE(question_id,version),
      FOREIGN KEY(question_id,course_id) REFERENCES learning_questions(id,course_id),
      FOREIGN KEY(skill_id,course_id) REFERENCES curriculum_catalog_skills(id,course_id))""",
    """CREATE TABLE learning_sessions(id TEXT PRIMARY KEY,student_id TEXT NOT NULL REFERENCES users(id),
      material_link_id TEXT NOT NULL REFERENCES learning_material_links(id),minutes INTEGER NOT NULL CHECK(minutes>0 AND minutes<=1440),
      note TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL)""",
    """CREATE TABLE learning_assessments(id TEXT PRIMARY KEY,student_id TEXT NOT NULL REFERENCES users(id),
      course_id TEXT NOT NULL REFERENCES curriculum_catalog_courses(id),phase TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','submitted')),draft_answers TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL,submitted_at TEXT)""",
    """CREATE TABLE learning_assessment_items(id TEXT PRIMARY KEY,assessment_id TEXT NOT NULL REFERENCES learning_assessments(id),
      question_version_id TEXT NOT NULL REFERENCES learning_question_versions(id),skill_id TEXT NOT NULL REFERENCES curriculum_catalog_skills(id),
      position INTEGER NOT NULL,snapshot TEXT NOT NULL,UNIQUE(assessment_id,position),UNIQUE(assessment_id,question_version_id))""",
    """CREATE TABLE learning_responses(item_id TEXT PRIMARY KEY REFERENCES learning_assessment_items(id),
      selected_option INTEGER NOT NULL,correct INTEGER NOT NULL CHECK(correct IN (0,1)))""",
    """CREATE TABLE learning_evaluations(assessment_id TEXT PRIMARY KEY REFERENCES learning_assessments(id),
      correct_count INTEGER NOT NULL,total_count INTEGER NOT NULL CHECK(total_count>0),score REAL NOT NULL CHECK(score>=0 AND score<=100),
      rule_version TEXT NOT NULL,created_at TEXT NOT NULL)""",
    """CREATE TABLE learning_skill_evaluations(assessment_id TEXT NOT NULL REFERENCES learning_assessments(id),
      skill_id TEXT NOT NULL REFERENCES curriculum_catalog_skills(id),correct_count INTEGER NOT NULL,total_count INTEGER NOT NULL CHECK(total_count>0),
      probability REAL NOT NULL CHECK(probability>=0 AND probability<=1),evidence_count INTEGER NOT NULL CHECK(evidence_count>0),
      PRIMARY KEY(assessment_id,skill_id))""",
    'CREATE INDEX learning_attempt_owner ON learning_assessments(student_id,course_id,status)',
    'CREATE INDEX learning_bank_scope ON learning_question_versions(course_id,skill_id,phase,status)',
    ]
    for statement in statements:op.execute(statement)

def downgrade():
    raise RuntimeError('Restore a verified backup; assessment evidence must not be silently dropped.')
