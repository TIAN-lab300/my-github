"""Recorded technical review of the fifteen public-source summaries, not publication."""
import json
from app.core.db import transaction,one,rows,run,dump,now,audit
NOTES={
1:'须补齐序列至少两个元素、允许的四种双端操作及其常数时间约束；应标明双端队列而非一般FIFO队列。',
2:'须补齐k的有效范围、空序列和边界行为，以及双端操作假设；O(k)结论依赖这些条件。',
3:'线性阶结论与官方答案一致；必须明确T(1)=Θ(1)、规模取整与非负运行时间等假设。',
4:'线性阶结论成立；须保留原题单调性与基本情况，不能省略后直接用于自动评分。',
5:'官方ASM-1B结论为返回1；缺完整汇编代码和选项，且需标明x86-64语境。',
6:'官方ASM-1D涉及jl与jb，且对imull有接受范围说明；须补全多选选项、代码与评分边界。',
7:'需保留原题全局变量声明、宽度和完整汇编；仅有C表达式摘要不足以评分。',
8:'要点与来源一致；应限定为可赋值变量，并补齐题型、选项或人工评分量规。',
9:'未定义行为解释与来源一致；须补齐正式题面、评分点，不以某次正常运行当作正确性证据。',
10:'输入6、4时结果10和2正确；这是编程题，须补输入边界、输出规范、溢出约束与测试用例，不能直接套单选判分。',
11:'调和步长满足两项级数条件；须写明n从1开始及随机逼近前提，不能推广为任意RL算法保证收敛。',
12:'常数步长的平方和发散；结论与原题一致，但必须区分条件不满足与任何算法必定不收敛。',
13:'步长和有限，因此第一项不满足；须补齐题面假设与评分规则。',
14:'官方选择约150秒；缺原论文性能图、系统与无故障假设，不具备独立作答条件。',
15:'官方该题勾选向量平均或相加；原题是多选，须保留全部选项及课程约定，不能视为通用唯一实现。'
}

def review_baseline():
    report=[]
    with transaction() as db:
        admin=one(db,"SELECT id FROM users WHERE role='admin' AND status='active' ORDER BY created_at LIMIT 1")
        if not admin:raise ValueError('需要已有管理员')
        for record in rows(db,'SELECT * FROM question_review_candidates ORDER BY id'):
            q=json.loads(record['payload'])
            if record['id'] not in {f'QA-DRAFT-{n:03}' for n in NOTES}:continue
            if record['status'] not in ('pending_teacher_review','needs_completion') or q.get('published') or q.get('approved_for_scoring'):continue
            n=int(record['id'].split('-')[-1])
            review={'version':'technical-review-20261116-v1','reviewed_at':now(),'type':'assistant_technical_review',
                'decision':'needs_completion','answer_check':'conditionally_consistent_with_source',
                'findings':[NOTES[n],'当前仅为题答摘要，缺少可直接评分的完整题型结构。','来源使用许可仍需逐项核准；不作为未曝光重测试题。'],
                'checked_source':q['answer_url'],'locator':q['original_locator'],'approved_for_scoring':False}
            previous=q.get('technical_review')
            if previous and previous.get('version')==review['version']:review=previous
            else:
                q['technical_review']=review;q['published']=False;q['approved_for_scoring']=False;q['status']='needs_completion'
                run(db,'UPDATE question_review_candidates SET status=:s,payload=:p WHERE id=:i',s='needs_completion',p=dump(q),i=record['id'])
                audit(db,admin['id'],'candidate_technical_review',record['id'],dump(review))
            report.append({'id':record['id'],'course':q['course_name'],'review':review})
    return {'reviewed':len(report),'ready_to_publish':0,'needs_completion':len(report),'items':report}
