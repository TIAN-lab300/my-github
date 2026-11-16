import json
import pytest
from fastapi import HTTPException
from app.core.db import transaction,one,rows,insert
from app.services.public_catalog import import_catalog
from app.services.curriculum_structure import import_structure,validate,SOURCE,extend_graph
P='/api/v1'


def test_complete_structure_is_idempotent_and_visible(clients):
    import_catalog();result=import_structure()
    assert result['courses']==36 and result['chapters']==144 and result['skills']==377
    assert result['course_edges']==77 and result['skill_edges']==335
    assert import_structure()['already_imported']
    r=clients['student'].get(P+'/learning/courses/public-C01/structure')
    assert r.status_code==200
    data=r.json();assert len(data['chapters'])==4
    assert sum(len(ch['skills']) for ch in data['chapters'])==12
    assert not data['version']['official_verified']
    assert any(p['before_name']=='函数与参数传递' and p['after_name']=='递归基础' for p in data['skill_prerequisites'])
    ai=clients['student'].get(P+'/learning/courses/public-C21/structure').json()
    assert any(r['name']=='线性代数' for r in ai['external_requirements'])
    with transaction() as db:
        assert one(db,'SELECT COUNT(*) n FROM learning_skill_chapters')['n']==377
        assert one(db,'SELECT COUNT(*) n FROM observations')['n']==0
        assert one(db,'SELECT COUNT(*) n FROM learning_question_versions')['n']==0


def test_cycles_and_duplicate_membership_rejected():
    p=json.loads(SOURCE.read_text(encoding='utf-8'))
    p['course_edges'].append({'before_id':'public-C03','after_id':'public-C01','kind':'required','reason':'测试循环'})
    with pytest.raises(ValueError,match='cycle'):validate(p)
    p=json.loads(SOURCE.read_text(encoding='utf-8'))
    p['courses'][0]['chapters'][1]['skill_ids'].append(p['courses'][0]['chapters'][0]['skill_ids'][0])
    with pytest.raises(ValueError,match='more than one'):validate(p)


def test_manual_chapters_are_not_overwritten(clients):
    import_catalog()
    with transaction() as db:insert(db,'learning_chapters',id='manual',course_id='public-C01',title='教师原章节',position=1)
    with pytest.raises(ValueError,match='manual chapter'):import_structure()
    with transaction() as db:
        assert not rows(db,'SELECT * FROM curriculum_relation_versions')
        assert one(db,'SELECT COUNT(*) n FROM learning_chapters')['n']==1
        assert one(db,'SELECT title FROM learning_chapters WHERE id=:i',i='manual')['title']=='教师原章节'


def test_mapped_prerequisites_extend_graph_and_reject_missing(clients):
    import_catalog();import_structure()
    graph=[{'id':'g1','name':'程序运行','minutes':10,'prerequisites':[]},
        {'id':'g2','name':'类型表达式','minutes':10,'prerequisites':[]},
        {'id':'g3','name':'输入输出','minutes':10,'prerequisites':[]}]
    mappings=[{'skill_id':f'public-C01-K00{n}','graph_skill_id':f'g{n}'} for n in range(1,4)]
    with transaction() as db:
        result=extend_graph(db,'public-C01',mappings,graph)
        assert result[1]['prerequisites']==['g1'] and result[2]['prerequisites']==['g2']
        with pytest.raises(HTTPException) as e:extend_graph(db,'public-C01',mappings[2:],graph)
        assert e.value.detail['code']=='COURSE_PREREQUISITE_GAP'
        graph[0]['prerequisites']=['g3']
        with pytest.raises(HTTPException) as e:extend_graph(db,'public-C01',mappings,graph)
        assert e.value.detail['code']=='COURSE_GRAPH_CONFLICT'
