from typing import Literal
from pydantic import BaseModel, Field

class Login(BaseModel):
    username: str = Field(min_length=1,max_length=80)
    password: str = Field(min_length=1,max_length=128)

class ChangePassword(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str

class Account(BaseModel):
    username: str = Field(min_length=2,max_length=80,pattern=r'^[a-zA-Z0-9_.-]+$')
    name: str = Field(min_length=1,max_length=80)
    role: Literal['teacher','student']
    password: str

class ClassInput(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    description: str = Field(default='',max_length=1000)

class InviteInput(BaseModel):
    expires_in_hours: int = Field(default=24,ge=1,le=720)
    max_uses: int = Field(default=30,ge=1,le=500)

class StudyInput(BaseModel):
    session_id: str = Field(min_length=8,max_length=80)
    minutes: int = Field(gt=0,le=1440)
    completed: bool = True

class Question(BaseModel):
    id: str
    skill: str = Field(min_length=1,max_length=100)
    prompt: str = Field(min_length=1,max_length=2000)
    options: list[str] = Field(default_factory=list,max_length=12)
    answer: str = Field(default='',max_length=2000)
    explanation: str = Field(default='',max_length=2000)
    kind: Literal['single','boolean','fill','multi','subjective'] = 'single'

class CodeCase(BaseModel):
    stdin: str = Field(default='',max_length=2000)
    stdout: str = Field(max_length=2000)


class TaskInput(BaseModel):
    class_id: str
    title: str = Field(min_length=1,max_length=100)
    description: str = Field(min_length=1,max_length=3000)
    due_at: str
    minutes: int = Field(gt=0,le=1440)
    mode: Literal['quiz','text','link','checkin','code'] = 'quiz'
    code_cases: list[CodeCase] = Field(default_factory=list,max_length=10)
    resource_id: str | None = None
    questions: list[Question] = Field(default_factory=list,max_length=50)
    recipients: list[str] = Field(default_factory=list,max_length=500)

class Submission(BaseModel):
    answers: dict[str,str] = Field(default_factory=dict)
    text: str = Field(default='',max_length=20000)
    minutes: int = Field(gt=0,le=1440)

class Review(BaseModel):
    score: float = Field(ge=0,le=1)
    comment: str = Field(min_length=1,max_length=3000)

class GoalInput(BaseModel):
    title: str = Field(min_length=1,max_length=200)
    target_skill_ids: list[str] = Field(default_factory=list,max_length=30)
    weekly_minutes: int = Field(gt=0,le=10080)
    due_date: str
    class_id: str | None = None
    preference: Literal['unspecified','video','text'] = 'unspecified'

class BudgetInput(BaseModel):
    daily_minutes: int = Field(gt=0,le=1440)
    weekly_minutes: int = Field(gt=0,le=10080)
    timezone: str = 'Asia/Shanghai'
    days: list[int] = Field(default_factory=lambda:list(range(7)))
    version: int

class Checkin(BaseModel):
    path_id: str
    item_id: str
    minutes: int = Field(gt=0,le=1440)
    proportion: float = Field(ge=0,le=1)
    difficulty: str = Field(default='',max_length=500)
    note: str = Field(default='',max_length=1000)

class ModelInput(BaseModel):
    model: str = Field(min_length=1,max_length=100)
    endpoint: str = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    secret_env: str = Field(default='DASHSCOPE_API_KEY',pattern=r'^[A-Z][A-Z0-9_]{1,79}$')
    timeout_seconds: int = Field(default=45,ge=3,le=60)
    max_tokens: int = Field(default=2048,ge=256,le=8192)
    temperature: float = Field(default=.2,ge=0,le=2)
    prompt_version: str = Field(default='zhixing-v1',min_length=1,max_length=80)
