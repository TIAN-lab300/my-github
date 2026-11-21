"""Protect review evidence and pin curriculum dependency batches."""
from alembic import op

revision='0032'
down_revision='0031'


def upgrade():
    for table in ('curriculum_object_revisions','curriculum_validation_events'):
        op.execute(f"""CREATE TRIGGER {table}_no_delete BEFORE DELETE ON {table}
            BEGIN SELECT RAISE(ABORT,'protected curriculum history'); END""")
    op.execute('''CREATE UNIQUE INDEX curriculum_revision_identity
        ON curriculum_object_revisions(id,object_type,object_id)''')
    op.execute('''CREATE TABLE curriculum_dependency_snapshots(
        id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, created_at TEXT NOT NULL)''')
    op.execute('''CREATE INDEX dependency_snapshots_by_goal ON curriculum_dependency_snapshots(goal_id)''')
    op.execute('''CREATE TABLE curriculum_dependency_items(
        snapshot_id TEXT NOT NULL REFERENCES curriculum_dependency_snapshots(id),
        object_type TEXT NOT NULL, object_id TEXT NOT NULL, revision_id TEXT NOT NULL,
        PRIMARY KEY(snapshot_id,object_type,object_id),
        FOREIGN KEY(revision_id,object_type,object_id)
        REFERENCES curriculum_object_revisions(id,object_type,object_id))''')
    op.execute("""INSERT INTO curriculum_dependency_snapshots
        SELECT 'legacy:'||goal_id,goal_id,strftime('%Y-%m-%dT%H:%M:%fZ','now')
        FROM goal_curriculum_dependencies GROUP BY goal_id""")
    op.execute("""INSERT INTO curriculum_dependency_items SELECT 'legacy:'||goal_id,object_type,object_id,revision_id
        FROM goal_curriculum_dependencies""")
    op.execute("""CREATE TRIGGER curriculum_dependency_items_identity BEFORE INSERT ON curriculum_dependency_items
        WHEN NOT EXISTS(SELECT 1 FROM curriculum_object_revisions r WHERE r.id=NEW.revision_id
            AND r.object_type=NEW.object_type AND r.object_id=NEW.object_id)
        BEGIN SELECT RAISE(ABORT,'dependency revision identity mismatch'); END""")
    for table in ('curriculum_dependency_snapshots','curriculum_dependency_items'):
        for action in ('UPDATE','DELETE'):
            op.execute(f"""CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table}
                BEGIN SELECT RAISE(ABORT,'protected dependency history'); END""")
    for action in ('INSERT','UPDATE'):
        op.execute(f"""CREATE TRIGGER goal_dependencies_identity_{action.lower()}
            BEFORE {action} ON goal_curriculum_dependencies
            WHEN NOT EXISTS (SELECT 1 FROM curriculum_object_revisions r WHERE r.id=NEW.revision_id
                AND r.object_type=NEW.object_type AND r.object_id=NEW.object_id)
            BEGIN SELECT RAISE(ABORT,'dependency revision identity mismatch'); END""")
    for table in ('goals','diagnoses','agent_runs','paths'):
        op.execute(f'ALTER TABLE {table} ADD COLUMN curriculum_snapshot_id TEXT REFERENCES curriculum_dependency_snapshots(id)')
    op.execute("""UPDATE goals SET curriculum_snapshot_id='legacy:'||id
        WHERE EXISTS (SELECT 1 FROM curriculum_dependency_snapshots s WHERE s.goal_id=goals.id)""")
    for table in ('diagnoses','agent_runs','paths'):
        op.execute(f"""CREATE TRIGGER {table}_pin_curriculum AFTER INSERT ON {table}
            WHEN NEW.curriculum_snapshot_id IS NULL
            BEGIN UPDATE {table} SET curriculum_snapshot_id=
            (SELECT curriculum_snapshot_id FROM goals WHERE id=NEW.goal_id) WHERE id=NEW.id; END""")
    op.execute('''CREATE TRIGGER question_content_no_update BEFORE UPDATE OF question_id,course_id,skill_id,
        version,phase,prompt,options,answer,explanation,source ON learning_question_versions
        BEGIN SELECT RAISE(ABORT,'create a new question version'); END''')


def downgrade():
    raise RuntimeError('Restore a verified backup to preserve curriculum evidence.')
