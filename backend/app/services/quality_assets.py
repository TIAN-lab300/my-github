"""Concrete authored assets for versioned teaching evaluation."""
from app.services.teaching_examples import EXAMPLES

def enrich_v4(case,prerequisite_id):
    case['contract']='teaching-v4'
    case['target_action']='review' if case['prior_level']=='已掌握' and case['review_mastered'] else 'skip' if case['prior_level']=='已掌握' else 'learn'
    case['prerequisite']={'skill_id':prerequisite_id,'state':case.pop('prerequisite_state'),'evidence_id':case['id']+'-prereq'}
    case['sources']=[];case['assets']=[]
    for role,skill in [('target',case['skill_id']),('prerequisite',prerequisite_id)]:
        if not case['evidence_available']:continue
        if role=='prerequisite' and case['prerequisite']['state']=='mastered':continue
        example=EXAMPLES[skill];source=case['id']+('-source' if role=='target' else '-prereq-source')
        case['sources'].append({'id':source,'skill_id':skill,'role':role,'version':'authored-example-v1','text':example['text'],'media_type':'text','origin':'项目明确提供的原创评价示例，非外部网页'})
        for kind in ['example','assessment']:
            if kind=='assessment' and case.get('asset_incomplete'):continue
            asset={'id':source+'-'+kind,'skill_id':skill,'role':role,'source_id':source,'kind':kind,'prompt':example['prompt'],'code':example['code'],'answer':example['answer'],'rubric':example['rubric'],'worked':example['worked'],'question_count':1,'min_minutes':2,'max_minutes':8}
            if skill=='stack':asset.update(events=example['events'],states=example['states'],snapshot_count=7)
            case['assets'].append(asset)
    needs_work=case['target_action']!='skip' or case['prerequisite']['state']!='mastered'
    case['expected_status']='complete' if not needs_work else 'draft' if not case['evidence_available'] or case.get('asset_incomplete') else 'candidate'
    return case
