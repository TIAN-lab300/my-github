"""Export source-backed flowcharts as editable SVG, with no external services."""
from pathlib import Path
from html import escape

OUT=Path(__file__).resolve().parents[1]/'docs'/'diagrams'
OUT.mkdir(exist_ok=True)
G='#17642c'; O='#cc630d'; B='#28658c'

class Chart:
    def __init__(self,title,subtitle):
        self.parts=[f'''<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="1080" viewBox="0 0 1800 1080"><defs><marker id="g" markerWidth="10" markerHeight="10" refX="9" refY="4" orient="auto"><path d="M0,0 L9,4 L0,8" fill="{G}"/></marker><marker id="o" markerWidth="10" markerHeight="10" refX="9" refY="4" orient="auto"><path d="M0,0 L9,4 L0,8" fill="{O}"/></marker></defs><style>text{{font-family:'Microsoft YaHei','Noto Sans CJK SC',sans-serif;fill:#17251d}} .small{{font-size:18px}} .title{{font-size:42px;font-weight:700}} .node{{font-size:23px;font-weight:600}} .sub{{font-size:17px;fill:#4a5d50}}</style><rect width="1800" height="1080" fill="white"/>''']
        self.text(900,62,title,'title');self.text(900,102,subtitle,'small')
    def text(self,x,y,t,cls='small',color=None):
        self.parts.append(f'<text x="{x}" y="{y}" text-anchor="middle" class="{cls}"'+(f' style="fill:{color}"' if color else '')+f'>{escape(t)}</text>')
    def lane(self,y,h,title,sub=''):
        self.parts.append(f'<rect x="25" y="{y}" width="1750" height="{h}" rx="18" fill="#f0f6f0"/><path d="M43 {y} H155 V{y+h} H43 Q25 {y+h} 25 {y+h-18} V{y+18} Q25 {y} 43 {y}" fill="#deedd8"/>')
        for i,s in enumerate(title.split('|')):self.text(90,y+h/2+(i-(len(title.split('|'))-1)/2)*32,s,'node')
        if sub:self.text(90,y+h-25,sub,'sub')
    def box(self,x,y,w,h,title,sub='',decision=False,dashed=False):
        color=O if decision or dashed else G
        dash=' stroke-dasharray="8 6"' if dashed else ''
        if decision:
            shape=f'<polygon points="{x+24},{y} {x+w-24},{y} {x+w},{y+h/2} {x+w-24},{y+h} {x+24},{y+h} {x},{y+h/2}"'
        else:shape=f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12"'
        self.parts.append(shape+f' fill="{"#fff2df" if decision or dashed else "#ffffff"}" stroke="{color}" stroke-width="2"{dash}/>')
        lines=title.split('|');base=y+h/2-(len(lines)-1)*15-(12 if sub else -7)
        for i,s in enumerate(lines):self.text(x+w/2,base+i*30,s,'node')
        if sub:
            for i,s in enumerate(sub.split('|')):self.text(x+w/2,y+h-24-(len(sub.split('|'))-1)*13+i*21,s,'sub')
    def arrow(self,points,label='',lx=0,ly=0,orange=False,dashed=False):
        c=O if orange else G
        self.parts.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in points)+f'" fill="none" stroke="{c}" stroke-width="2.5" stroke-linejoin="round" marker-end="url(#{"o" if orange else "g"})"'+(' stroke-dasharray="8 6"' if dashed else '')+'/>')
        if label:self.text(lx,ly,label,'small',c)
    def save(self,name,note):
        self.text(900,1026,note,'small');self.text(900,1057,'绿色实线：已实现逻辑    橙色箭头：回退 / 调整    橙色虚线：待建设连接    ｜    依据当前源码与设计 · 2026-11-15','sub')
        (OUT/(name+'.svg')).write_text(''.join(self.parts)+'</svg>',encoding='utf-8')

c=Chart('首次诊断与学习路径生成流程','用户操作 → 服务端判分与证据 → 四智能体协作 → 确认生效')
c.lane(140,165,'用户|操作');c.lane(330,440,'系统|与智能体');c.lane(795,180,'数据库|与审核')
c.box(195,170,220,100,'① 确认目标|知识点与时间预算')
c.box(490,170,200,100,'③ 完成诊断|提交全部答案')
c.box(1400,170,310,100,'⑩ 查看依据与方案|接受 / 暂不接受')
c.box(195,380,220,120,'② 审核题库|覆盖目标技能？',decision=True)
c.box(490,380,200,120,'④ 判分并计算|BKT 掌握度','去重保存有效证据')
c.box(770,380,220,120,'⑤ 诊断智能体','目标 + 真实答题统计')
c.box(1070,380,220,120,'⑥ 路径构建智能体','待学技能 + 授权正文')
c.box(1400,380,310,120,'⑦ 审查智能体','教学审查 + 先修 / 预算规则')
c.box(1070,610,220,110,'⑧ 解释与保存候选','重规划智能体')
c.box(1400,610,310,110,'⑪ 接受时输入|版本仍一致？',decision=True)
c.box(770,610,220,110,'⑨ 展示路径预览','诊断依据 / 引用 / 风险')
c.box(490,610,200,110,'阻断后先处理','补正文 / 调预算 / 查配置')
c.box(195,835,220,100,'人工补齐与审核','题目 / 图谱 / 材料')
c.box(490,835,500,100,'诊断与证据库','diagnoses → attempts → observations|mastery_snapshots / learner_evidence')
c.box(1070,835,220,100,'候选与过程记录','paths / agent_runs')
c.box(1400,835,310,100,'⑫ 激活路径与预约','原路径替换；事务提交')
for p in [[(305,270),(305,380)],[(415,440),(450,440),(450,220),(490,220)],[(590,270),(590,380)],[(690,440),(770,440)],[(990,440),(1070,440)],[(1290,440),(1400,440)],[(1555,500),(1555,550),(1180,550),(1180,610)],[(1070,665),(990,665)],[(880,610),(880,560),(1015,560),(1015,290),(1555,290),(1555,270)],[(1555,270),(1735,270),(1735,665),(1710,665)],[(1555,720),(1555,835)],[(590,500),(590,550),(710,550),(710,805),(740,805),(740,835)],[(1180,720),(1180,835)]]:c.arrow(p)
c.text(440,418,'是','small',G);c.text(1595,795,'是','small',G)
c.text(1630,537,'通过','small',G)
c.text(1694,335,'仅接受','small',G)
c.text(1230,248,'暂不接受：候选不激活','sub')
c.arrow([(1070,465),(1010,465),(1010,530),(450,530),(450,665),(490,665)],'材料 / 预算不足：本次不产出有效方案',733,523,True)
c.text(1215,598,'审查不通过 → 修复；耗尽次数则失败','sub')
c.arrow([(305,500),(305,835)],'不足',343,690,True)
c.arrow([(195,885),(173,885),(173,350),(305,350),(305,380)],orange=True)
c.arrow([(1480,500),(1480,580),(1035,580),(1035,440),(1070,440)],'修复活动（最多 3 次）',1255,575,True)
c.arrow([(1400,665),(1325,665),(1325,745),(740,745),(740,440),(770,440)],'否：预览过期，重新生成',1035,740,True)
c.save('01-initial-diagnosis','缺少题目或有效正文时先补齐；暂不接受不激活；云端模式需配置激活且材料允许发送。')

c=Chart('学习反馈与重规划闭环','有效测验证据驱动掌握度；学习记录驱动执行调整；新方案确认后替换旧方案')
c.lane(140,165,'用户|操作');c.lane(330,430,'系统|与智能体');c.lane(785,190,'数据|与历史')
for args in [(195,170,280,100,'① 学习、测验或重测','路径任务 / 教师任务'),(650,170,280,100,'④ 主动生成重规划预览','选择本地或云端'),(1360,170,340,100,'⑧ 查看差异并决定','接受 / 拒绝'),(195,390,280,120,'② 更新有效证据|与执行记录','学习分钟不直接增加掌握度'),(650,390,280,120,'⑤ 判定调整范围','局部补强 / 全局重新安排'),(1035,390,280,120,'⑥ 重新执行四智能体','诊断 → 构建 → 审查 → 解释'),(1360,390,340,120,'⑨ 接受前再次校验','输入版本 / 权限 / 时间预算'),(650,610,280,100,'③ 对比活动路径依据','提示测验或执行记录变化'),(1035,610,280,100,'⑦ 保存候选与差异','新增 / 移除 / 保留 / 补强'),(1360,825,340,110,'⑩ 原子切换路径与预约','保留完成历史及原始证据'),(195,825,360,110,'学生证据与活动记录','observations / checkins|mastery_snapshots'),(650,825,540,110,'历史路径与本次冻结依据','paths.validation.learner_evidence|agent_runs / agent_steps / reservations')]:c.box(*args)
for p in [[(335,270),(335,390)],[(475,450),(560,450),(560,660),(650,660)],[(650,660),(605,660),(605,290),(790,290),(790,270)],[(790,270),(790,390)],[(930,450),(1035,450)],[(1175,510),(1175,610)],[(1315,660),(1335,660),(1335,220),(1360,220)],[(1530,270),(1530,390)],[(1530,510),(1530,825)],[(335,510),(335,825)],[(1175,710),(1175,825)]]:c.arrow(p)
c.arrow([(1360,450),(1340,450),(1340,570),(790,570),(790,510)],'否：输入变化，重建预览',1040,565,True)
c.text(1570,350,'仅接受','small',G)
c.text(1580,780,'校验通过','small',G)
c.arrow([(1035,485),(990,485),(990,735),(575,735),(575,660),(555,660)],'执行失败',1000,723,True)
c.box(195,610,360,100,'拒绝或失败：保留原路径','候选不替换活动路径')
c.arrow([(1530,170),(1530,125),(1750,125),(1750,750),(575,750),(575,660),(555,660)],orange=True)
c.text(790,358,'预算变化 >30%、图谱或技能范围变化 → 全局','sub')
c.text(790,550,'其他情况通常局部调整；已完成但薄弱 → 独立补强','sub')
c.save('02-learning-replanning','初测、路径测验及教师任务的有效证据参与现有规划；专业课程库证据桥接另见关系图。')

c=Chart('课程、知识点、题库与评价的数据库对应关系','上层为专业课程学习测验库；下层为目标规划库；两套知识点通过审核映射与唯一证据桥接连接')
c.lane(140,290,'课程|内容库');c.lane(450,240,'测验|评价库');c.lane(710,265,'目标|规划库')
c.box(190,175,300,100,'课程','curriculum_catalog_courses')
c.box(610,175,330,100,'课程知识点','curriculum_catalog_skills')
c.box(1060,175,300,100,'稳定题目 → 题目版本','learning_questions|learning_question_versions')
c.box(1460,175,280,100,'章节','learning_chapters')
c.box(610,315,330,90,'知识点 ↔ 资料版本','learning_material_links')
c.box(1060,315,300,90,'教学正文版本','resources / resource_versions')
c.box(190,490,300,120,'学生试卷','learning_assessments|student_id + course_id')
c.box(610,490,330,120,'试卷题目快照 → 作答','learning_assessment_items|learning_responses')
c.box(1060,490,300,120,'总评 + 知识点评价','learning_evaluations|learning_skill_evaluations')
c.box(1460,490,280,120,'学习记录','learning_sessions|关联资料；分钟不改掌握度')
c.box(190,770,300,140,'目标 + 审核知识图谱','goals / graph_versions|诊断 → attempts')
c.box(610,770,330,140,'逐题证据 → 掌握画像','observations|mastery_snapshots')
c.box(1060,770,300,140,'四智能体规划','agent_runs / agent_steps|证据快照 + 授权正文')
c.box(1460,770,280,140,'路径 → 排期预约','paths / reservations|确认后生效')
c.arrow([(490,225),(610,225)],'1 : N',550,212)
c.arrow([(940,225),(1060,225)],'1 : N 版本',1000,212)
c.arrow([(775,275),(775,315)],'1 : N',820,303)
c.arrow([(1060,360),(940,360)],'版本引用',1000,348)
c.arrow([(1600,275),(1600,294),(980,294),(980,155),(775,155),(775,175)],'章节—知识点关联表约束同课程',1230,289)
c.arrow([(340,275),(340,490)],'课程 1 : N 试卷',350,390)
c.arrow([(490,550),(610,550)],'1 : N',550,535)
c.arrow([(1210,275),(1385,275),(1385,445),(775,445),(775,490)],'冻结已审核题目版本；每个版本归属一个课程知识点',1110,440)
c.arrow([(940,550),(1060,550)],'判分 / BKT',1000,535)
c.arrow([(1600,490),(1600,420),(965,420),(965,385),(940,385)],'学习记录引用资料关联 ID',1450,415)
c.arrow([(1210,490),(1210,472),(585,472),(585,195),(610,195)],'知识点评价按 skill_id 归属',805,466)
c.text(1575,640,'试卷与学习记录均由 student_id 归属 users','sub')
c.text(450,302,'课程 1:N 章节（course_id）','sub')
c.arrow([(490,840),(610,840)],'判分',550,825)
c.arrow([(940,840),(1060,840)],'只读证据',1000,825)
c.arrow([(1360,840),(1460,840)],'候选 / 接受',1410,825)
c.arrow([(775,610),(775,770)],'已实现：审核技能映射 + 唯一证据桥接',1060,731,False,False)
c.text(1080,670,'curriculum_graph_mappings / learning_evidence_links（0024 已建）','sub')
c.save('03-course-knowledge-database','正式题目与知识点映射须审核；学生从课程初测创建目标后，新有效作答进入规划证据，重复作答不重复累计。')

links=''.join(f'<section><h2>{title}</h2><img src="{name}.svg" alt="{title}"/><p><a href="{name}.svg" download>下载可编辑 SVG</a> · <a href="{name}.png" download>下载 PNG</a></p></section>' for name,title in [('01-initial-diagnosis','首次诊断与路径生成'),('02-learning-replanning','学习反馈与重规划'),('03-course-knowledge-database','课程与知识点数据库关系')])
(OUT/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>知行学习诊断与重规划流程</title><style>body{font-family:"Microsoft YaHei",sans-serif;margin:24px;background:#f4f7f4;color:#183921}section{background:white;padding:20px;margin-bottom:24px}img{width:100%;height:auto}a{color:#17642c}</style><h1>知行 · 首次诊断、重规划与数据关系</h1><p>依据当前源码与设计，绿色为已实现逻辑；课程桥接须完成映射审核、正式题库与目标绑定后生效。</p>'+links+'</html>',encoding='utf-8')
print(OUT)
