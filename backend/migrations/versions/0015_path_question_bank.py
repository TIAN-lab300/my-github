"""Freeze reviewed practice questions with each path item."""
from alembic import op
revision='0015'
down_revision='0014'
branch_labels=None
depends_on=None


def upgrade():
    op.execute("""CREATE TABLE path_question_bank (
        path_id TEXT NOT NULL REFERENCES paths(id), item_id TEXT NOT NULL,
        questions TEXT NOT NULL, PRIMARY KEY(path_id,item_id))""")


def downgrade():
    raise RuntimeError('Restore a verified backup to preserve question versions.')
