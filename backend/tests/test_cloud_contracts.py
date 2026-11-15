import pytest
from fastapi import HTTPException
from app.services.cloud_contracts import validate_output

@pytest.mark.parametrize('agent,payload',[
 ('GoalDiagnosisAgent',{'summary':'','risks':[]}),
 ('GoalDiagnosisAgent',{'summary':'valid','risks':[1]}),
 ('LearningReplanAgent',{'reason':'valid','recommendations':'not-list'}),
 ('PlanReviewAgent',{'approved':True,'issues':['unsupported source']}),
 ('PlanReviewAgent',{'approved':'true','issues':[]}),
 ('PathBuildingAgent',{'reason':'valid','tasks':[{'skill_id':[]}]})])
def test_invalid_contract_rejected(agent,payload):
 with pytest.raises(HTTPException) as exc:validate_output(agent,payload)
 assert exc.value.detail['code']=='MODEL_SCHEMA_INVALID'

def test_empty_plan_allowed_and_limits_enforced():
 assert validate_output('PathBuildingAgent',{'reason':'all mastered','tasks':[]})['tasks']==[]
 with pytest.raises(HTTPException):validate_output('GoalDiagnosisAgent',{'summary':'x'*2001,'risks':[]})
