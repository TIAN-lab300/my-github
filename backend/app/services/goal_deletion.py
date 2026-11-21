"""Permanent removal of archived goals, with independent scoring evidence retained."""
import json
from app.core.db import transaction,one,rows,run,audit,touch,dump
from app.core.security import goal_access,fail


def delete_archived(ident,user):
    with transaction() as db:
        goal=goal_access(db,user,ident)
        if goal['status']!='archived':fail(409,'请先归档目标，再删除')
        if one(db,"SELECT id FROM agent_runs WHERE goal_id=:g AND status='running'",g=ident):
            fail(409,'该目标仍有运行处理中，请结束运行后再删除')
        run(db,'DELETE FROM project_delivery_reviews WHERE delivery_id IN (SELECT d.id FROM project_deliveries d JOIN project_milestones m ON m.id=d.milestone_id WHERE m.goal_id=:g)',g=ident)
        run(db,'DELETE FROM project_deliveries WHERE milestone_id IN (SELECT id FROM project_milestones WHERE goal_id=:g)',g=ident)
        for table in ('project_milestones','project_delivery_plans','project_workspaces'):run(db,'DELETE FROM '+table+' WHERE goal_id=:g',g=ident)
        run(db,'UPDATE project_worklogs SET goal_id=NULL,source_id=NULL WHERE goal_id=:g',g=ident)
        run(db,'DELETE FROM reservations WHERE goal_id=:g',g='project:'+ident)
        path_ids='SELECT id FROM paths WHERE goal_id=:g'
        session_ids='SELECT id FROM assessment_sessions WHERE path_id IN ('+path_ids+')'
        # Keep exposure identities: deleting a goal must not allow repeated questions to farm mastery.
        run(db,'UPDATE question_exposures SET session_id=NULL WHERE session_id IN ('+session_ids+')',g=ident)
        run(db,'UPDATE assessment_sessions SET previous_id=NULL WHERE previous_id IN ('+session_ids+')',g=ident)
        run(db,'DELETE FROM assessment_sessions WHERE path_id IN ('+path_ids+')',g=ident)
        for table in ('path_assessments','path_question_bank','remediation_tasks','checkins'):
            run(db,'DELETE FROM '+table+' WHERE path_id IN ('+path_ids+')',g=ident)
        run(db,"DELETE FROM reservations WHERE goal_id=:g OR (source_type='path' AND source_id IN ("+path_ids+'))',g=ident)
        run(db,'DELETE FROM agent_steps WHERE run_id IN (SELECT id FROM agent_runs WHERE goal_id=:g)',g=ident)
        run(db,'DELETE FROM agent_runs WHERE goal_id=:g',g=ident)
        run(db,'DELETE FROM paths WHERE goal_id=:g',g=ident)
        run(db,'DELETE FROM diagnoses WHERE goal_id=:g',g=ident)
        run(db,'DELETE FROM goal_revisions WHERE goal_id=:g',g=ident)
        run(db,'DELETE FROM course_goal_bindings WHERE goal_id=:g',g=ident)
        run(db,'DELETE FROM goal_curriculum_dependencies WHERE goal_id=:g',g=ident)
        context=one(db,'SELECT graph_version FROM project_goal_contexts WHERE goal_id=:g',g=ident)
        run(db,'DELETE FROM project_goal_contexts WHERE goal_id=:g',g=ident)
        run(db,'DELETE FROM project_goal_proposals WHERE confirmed_goal_id=:g',g=ident)
        # Scored attempts may also support other goals/course evidence; detach rather than erase them.
        run(db,'UPDATE attempts SET goal_id=NULL WHERE goal_id=:g',g=ident)
        run(db,'DELETE FROM goals WHERE id=:g',g=ident)
        if context:run(db,'DELETE FROM graph_versions WHERE id=:v AND active=0',v=context['graph_version'])
        # Remove deleted goal definitions from derived portrait history as well.
        def scrub(value):
            if isinstance(value,dict):
                return {key:([scrub(item) for item in items if not isinstance(item,dict) or item.get('id')!=ident] if key=='goals' and isinstance(items,list) else scrub(items)) for key,items in value.items()}
            if isinstance(value,list):return [scrub(item) for item in value]
            return value
        for snapshot in rows(db,'SELECT id,payload FROM profile_snapshots'):
            original=json.loads(snapshot['payload']);clean=scrub(original)
            if clean!=original:run(db,'UPDATE profile_snapshots SET payload=:p WHERE id=:i',p=dump(clean),i=snapshot['id'])
        touch(db,user['id']);audit(db,user['id'],'archived_goal_deleted',ident,'目标与版本、路径及运行记录已永久删除')
    return {'ok':True}
