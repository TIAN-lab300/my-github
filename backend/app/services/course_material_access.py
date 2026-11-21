"""Visible course material metadata, shared by course pages and counts."""
from fastapi import HTTPException
from app.core.db import rows
from app.core.security import resource_access

def visible_materials(db,user,course_id,skill_id=None):
    links=rows(db,"SELECT m.*,r.title,r.description,r.source_license,r.scope,r.owner_id,r.class_id,r.status,r.kind,r.current_version,v.filename,v.bytes,v.parse_status,v.index_status FROM learning_material_links m JOIN resources r ON r.id=m.resource_id JOIN resource_versions v ON v.id=m.resource_version_id AND v.resource_id=r.id WHERE m.course_id=:c AND r.current_version=v.id AND ((v.parse_status='ready' AND length(trim(v.body))>0) OR (r.kind='link' AND v.parse_status='not_applicable') OR (r.kind='text' AND v.storage_key IS NOT NULL AND v.parse_status IN ('not_applicable','failed')))"+(' AND m.skill_id=:s' if skill_id else '')+' ORDER BY r.title,m.id',c=course_id,**({'s':skill_id} if skill_id else {}))
    result=[]
    for link in links:
        if link['status']!='published' and not (link['scope']=='private' and link['owner_id']==user['id']):continue
        try:resource_access(db,user,link['resource_id'])
        except HTTPException as exc:
            if exc.status_code in (403,404):continue
            raise
        result.append(link)
    return result


def imported_course_materials(db,user,course_id):
    items=rows(db,"SELECT r.id AS resource_id,r.title,r.description,r.source_license,r.scope,r.owner_id,r.status,r.current_version AS resource_version_id,r.kind,v.filename,v.bytes,v.parse_status,v.index_status FROM resources r JOIN resource_versions v ON v.id=r.current_version WHERE instr(r.tags,:tag)>0 ORDER BY r.title",tag='|course:'+course_id+'|')
    result=[]
    for item in items:
        try:resource_access(db,user,item['resource_id'])
        except HTTPException as exc:
            if exc.status_code in (403,404):continue
            raise
        result.append(item)
    return result
