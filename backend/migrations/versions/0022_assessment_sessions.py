from alembic import op

revision = '0022'
down_revision = '0021'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE bank_versions (
        id TEXT PRIMARY KEY, question_id TEXT NOT NULL, version INTEGER NOT NULL,
        owner_id TEXT NOT NULL REFERENCES users(id), content TEXT NOT NULL,
        status TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(question_id, version))''')
    op.execute('''CREATE TABLE bank_reviews (
        id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES bank_versions(id),
        actor_id TEXT NOT NULL REFERENCES users(id), action TEXT NOT NULL,
        comment TEXT NOT NULL, created_at TEXT NOT NULL)''')
    op.execute('''CREATE TABLE assessment_sessions (
        id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES users(id),
        path_id TEXT NOT NULL REFERENCES paths(id), item_id TEXT NOT NULL,
        previous_id TEXT REFERENCES assessment_sessions(id), questions TEXT NOT NULL,
        answers TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'open',
        attempt_id TEXT REFERENCES attempts(id), created_at TEXT NOT NULL,
        submitted_at TEXT, rule_version TEXT NOT NULL DEFAULT 'sessions-v1')''')
    op.execute("CREATE UNIQUE INDEX one_open_assessment ON assessment_sessions(student_id,path_id,item_id) WHERE status='open'")
    op.execute('''CREATE TABLE question_exposures (
        student_id TEXT NOT NULL REFERENCES users(id), identity TEXT NOT NULL,
        session_id TEXT REFERENCES assessment_sessions(id), created_at TEXT NOT NULL,
        PRIMARY KEY(student_id, identity))''')


def downgrade():
    raise RuntimeError('Restore a verified backup.')
