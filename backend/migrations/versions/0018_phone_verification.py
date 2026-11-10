from alembic import op
revision='0018'
down_revision='0017'
branch_labels=None
depends_on=None

def upgrade():
    op.execute("CREATE TABLE user_phones (user_id TEXT PRIMARY KEY REFERENCES users(id), phone TEXT NOT NULL UNIQUE, verified_at TEXT NOT NULL)")
    op.execute("CREATE TABLE sms_codes (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), phone TEXT NOT NULL, purpose TEXT NOT NULL, code_hash TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, used INTEGER NOT NULL DEFAULT 0)")

def downgrade():
    raise RuntimeError('Restore a verified backup.')
