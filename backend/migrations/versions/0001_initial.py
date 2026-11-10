"""Initial persistent platform schema."""
from alembic import op
from app.core.schema import SCHEMA
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    for statement in SCHEMA.split(';'):
        if statement.strip():
            op.get_bind().exec_driver_sql(statement)

def downgrade():
    raise RuntimeError('Use a verified backup to restore data; destructive downgrade disabled.')
