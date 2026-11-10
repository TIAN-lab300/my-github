from alembic import op
revision='0006'
down_revision='0005'
branch_labels=None
depends_on=None
def upgrade():
    op.execute('ALTER TABLE parse_jobs ADD COLUMN expected_version INTEGER')
def downgrade():
    op.execute('ALTER TABLE parse_jobs DROP COLUMN expected_version')
