from pathlib import Path
import re
root=Path(__file__).resolve().parents[3] / 'docx'
requirements=(root/'2026-10-27-smart-learning-planner-requirements-spec.md').read_text(encoding='utf-8')
items=re.findall(r'^\| (SF-([A-Z]+)-(\d+)) \| ([^|]+?) \| 系统应支持：([^|]+?) \|$',requirements,re.M)
assert len(items)==127
# Each entry specifies the object or payload that must be frozen, read or changed.
details={
'AUTH':[
'username/password→public_user和HttpOnly会话；Argon2验证，令牌只存哈希',
'username.trim与原始password分别校验；密码长度10～128，空值422',
'passwordVisible为组件内布尔状态；切换input.type，值及光标位置保留',
'同步提交锁覆盖请求全过程；网络失败释放锁，账号保留，错误显示在表单旁',
'must_change=1只允许me、改密和退出；改密成功递增auth_version并重新认证',
'old_password/new_password/confirm_password；旧密验证通过才更新哈希和撤销会话',
'忘记密码弹层展示管理员联系路径；重置后交付临时密码并设置must_change',
'GET me返回id/name/role/status/must_change；导航由role映射，接口独立鉴权',
'expires_at按服务器UTC判定；401清理所有私密视图，returnTo只允许站内授权路由',
'POST logout删除当前令牌会话并清cookie；随后读取受保护接口401',
'users.status和auth_version参与每次会话查询；停用/重置事务内递增版本',
'login_attempts保存失败次数和cooldown_until；429返回Retry-After和剩余秒数',
'BroadcastChannel或storage事件传播logout；收到后清除身份和缓存',
'审计字段actor/action/target/result/time/request_id；失败登录采用安全账号摘要'],
'ACCOUNT':[
'CLI初始化管理员，username唯一；重复执行返回已有账号，不覆盖密码或真实数据',
'username/name/role/temporary_password；只允许teacher/student，重复账号409',
'q/account_role/status/page；每页50条，返回公开字段，created_at/id稳定排序',
'PATCH users/me仅允许name；拒绝空白与超长，保存后更新页头姓名',
'目标账号active↔disabled；状态变化与auth_version递增同事务，恢复需重新登录',
'生成随机临时密码，仅本次受控交付；password_hash、must_change与auth_version原子更新',
'角色由初始化/建号入口决定；本人资料接口字段白名单，保护管理员不被普通管理动作修改',
'停用/重置先展示账号、影响及确认按钮；取消时零写请求，成功后刷新列表'],
'CLASS':[
'name/description/version；仅owner可改active班级，版本不符409',
'列表限定owner或active membership；详情返回本人关系，教师附成员状态',
'expires_in_hours/max_uses；随机原码仅创建响应展示，持久化hash，提供复制反馈',
'先校验码、归档、撤销及有效期，再校验使用上限；加入和计数同事务',
'(class_id,user_id)唯一；有效成员重复加入返回already_joined且used不增长',
'成员列表只含公开资料和成员状态；教师学生投影接口再次校验班级所有权',
'成员变left；取消未完成assignments与活动teacher reservations，保留attempts',
'归档事务撤销邀请、取消待办与预约并touch学生；恢复也不复活旧邀请和旧分配',
'student_ids/expected_version；复制原题目为关联补发draft，相同接收人待发布草稿复用'],
'RESOURCE':[
'class_id/kind/tag/q/status/parse_status/page组合；先授权再分页，不泄漏隐私数量',
'标题、说明、标签、source_license、class_id、cloud_allowed分别存储，范围和云端授权独立',
'逐文件返回id或error；20MiB/文件、10文件/批、100MiB/批，失败清理临时附件',
'扩展名/MIME/文件头联合检查；文本UTF-8、PDF可抽取正文，扫描件failed并给修正建议',
'parse_jobs按version唯一；queued/running/ready/failed，最多3次和租约恢复，重复重试复用任务',
'候选版本expected_version；解析索引成功后核版本切draft，失败保留现版，旧引用绑定version_id',
'owner教师与active班级校验；正文须ready且indexed；下架禁止新召回，历史证据走快照权限',
'详情DTO隐去storage_key；下载重新授权；Markdown采用安全渲染，拒绝可执行HTML和脚本协议',
'播放器只请求授权附件URL；字幕绑定resource_version_id及时间范围，字幕失败不标正文成功',
'image/attachment允许预览下载；parse_status=not_applicable，OCR能力单独标记',
'url/title/description/review_status；HTTP(S)校验，审核发布与正文抓取验证分开记录',
'student owner且scope=private；教师查询不可见；cloud_allowed单独切换并在发送时重查',
'(student_id,session_id)唯一；更新minutes/proportion而非累加，来源授权及正数时长校验',
'附件发布允许not_applicable，正文RAG仅召回ready/indexed片段，UI显示附件不可检索'],
'SEARCH':[
'query/scope/top_k；SQL授权ID限定召回候选，展示和云端发送前回查权限',
'关键词与向量各取候选后RRF融合；chunk_id/version_id/page/time定位真实片段',
'返回match_type/excerpt/score/source/coverage_status；元数据命中不冒充正文支持',
'按目标节点生成missing_mapping/prerequisite/duration/question/evidence结构化缺口',
'联网许可、上传资料模式及freshness共同决定触发；禁止联网时保留缺口草稿',
'source_snapshot保存规范URL、标题、域名、支持片段、fetched_at/published_at/hash',
'节点标stable或time_sensitive；按声明时间窗核对发布日期，未知日期保存null',
'规范URL和内容hash去重；最多2轮，缺口无变化则退出并保留失败原因',
'空结果/配额/网络/解析失败分码返回，提示上传补充，保留已核实结果'],
'GOAL':[
'title/target_skill_ids/due_date/weekly_minutes/class_id/version；归档释放本目标未来预约',
'goal_spec含范围、先修、截止、难度与资源模式；用户确认后冻结spec_version',
'校验标题、日期、知识点存在性、正数预算及目标范围，字段级错误返回422',
'daily_minutes/weekly_minutes/timezone/weekdays/version；ZoneInfo计算学习日，UTC存事件',
'class_id默认null；关联时校验有效成员，关联变动不能泄漏旧私人备注',
'活动目标修改生成影响说明和新输入版本；原路径需重评估，不能覆盖已完成事实',
'返回available/required/conflicts/reasons；区分预算证实不足与搜索未找到'],
'DIAG':[
'题库question_id/version/skill_id/options/answer/rubric；每个目标节点至少一个有效题',
'冻结goal_spec、question_snapshot和创建时间；未提交诊断重复创建复用',
'answers按题号存草稿；未知题号/非法选项422，草稿无评分与掌握度副作用',
'交卷显示未答清单和确认；提交携带diagnosis_id，完整性服务端校验',
'结果含逐题正确性、解析、知识点与证据质量；历史读取同一快照',
'学习后才领等价卷；新题快照隔离，未交重测复用，题库耗尽409',
'缺映射或生成失败返回missing_skills和可重试原因，不能生成空卷成功状态'],
'PATH':[
'graph_version含nodes/edges与来源；保存时拓扑检查、自环和不存在端点拒绝',
'POST创建run_id；GET轮询，持久步骤及输入指纹，中断标记可重试',
'candidate/pending_acceptance/active分离；草稿不计预约，不进入正式执行',
'先修拓扑和mastery阈值筛选；跳过节点记录证据，保留所有目标覆盖',
'排期联合所有目标与教师预约，按用户时区学习日计算；预约原子写入',
'VR-001～008逐条返回rule_id/pass/reason；任何硬规则失败阻止接受',
'解释绑定节点、资源版本、片段与规则；无来源说明缺口，点击后重新鉴权',
'accept携带版本指纹；版本状态与预约同事务，旧路径superseded并保留',
'path item映射skill/task/source，解锁依赖先修完成与掌握门槛，越序409'],
'TASK':[
'TaskInput冻结mode/resource/questions；draft编辑需version并重新校验截止',
'recipients空数组表示发布时全班；显式选择去重校验本班active成员',
'发布冻结题目/资源版本/接收人；tasks状态和assignments同事务提交',
'按due_at排序，状态筛选覆盖not_started/in_progress/completed/overdue/cancelled',
'assignment归本人；text/link/checkin分别校验，普通完成与评分状态独立',
'比较服务器提交时间和due_at保存late；first_completed_at首次写入不被重试覆盖',
'withdraw取消未完成分配和活动预约；close阻止新提交，两者保留历史',
'previous_task_id关联修订draft；旧题目、分配和成绩不更新',
'teacher owner限定提交查询，输出作答/状态/版本反馈，排除私人目标',
'截止前窗口预约teacher负荷；冲突显式返回学生和分钟，生成重评估提示'],
'ASSESS':[
'rule_version冻结评分规范；多选按集合严格相等，填空按明确大小写空白规则',
'提交后返回score/answer/explanation/skill/recommendations，历史同attempt返回',
'subjective提交pending_review且score=null，未复核不写掌握证据',
'复核携带rubric_version/score/comment；校验owner和分数0～1',
'评分版本追加reason/reviewer/time；停用旧观察后按有效证据时间序重放BKT',
'(attempt_id,question_id,rule_version)有效观察唯一，业务键胜于客户端幂等键',
'存prior/posterior/parameter_version/evidence_id，默认初值标未测，阈值可解释',
'minutes>0、proportion在0～1；difficulty/notes保存，checkin不写mastery observation'],
'REPLAN':[
'触发快照记录低掌握、连续2项逾期、预算目标变化和证据冲突，返回依据',
'预算相对变化>30%、范围变动或局部失败时global，其他local，记录decision_reason',
'diff按稳定节点ID比较新增/删除/保留、日期分钟变化、风险与规则结果',
'事务内重查目标、掌握度、成员、预算与资源版本，仅切本目标未来预约',
'reject仅改preview状态，旧path与预约继续；保留风险和先修阻断',
'fingerprint比较所有输入版本，任一变化409并给重新生成入口',
'remediation独立task及关联skill/path，去重业务键，旧完成事实保留'],
'PROFILE':[
'from/to/class/goal/resource/task/type/page，所有查询先限定本人事实',
'独立read_progress/submission_progress/mastery，不用阅读比例替代掌握',
'事件唯一键去重；完成率completed/assigned，按时率on_time/completed，分母0为null',
'六段context/behavior/mastery/evidence/risk/data_quality仅本人完整获取',
'先圈定本班授权事实再聚合，返回分母、统计窗、分布及风险依据',
'teacher owner及active membership控制投影，只有显式class_id目标和本班证据',
'事实与refresh_event同事务；同watermark复用，不可变新快照，失败返回旧版stale',
'snapshot_id/version/window/generated_at/watermark可查，保留旧内容及规则版本',
'risk附evidence_ids/observed_at，解释只引用已有数值，无数据返回unknown'],
'AI':[
'config版本保存endpoint/model/generation/search/timeout/prompt_version及secret_env引用',
'真实认证、JSON及搜索分别记录tested/passed/error，未测试能力显示unknown',
'只有全项必要评价通过才active，切换事务保证唯一活动版，失败保留上一版',
'诊断/路径/审查/重规划按状态路由，各节点经授权服务调用工具，规则审查独立',
'run/step记录输入版本、tool、时间、错误和脱敏结构化输出，去除密钥原文',
'JSON最多2次修复、规划最多3次，统一180秒deadline；失败候选不发布',
'checkpoint持久，取消令牌每步与提交前重查；重试保留parent_run_id和新输入指纹',
'正文及embedding发送前逐资源检查cloud_allowed和当前访问权，撤销即时生效',
'认证/余额/429/超时/搜索错误映射独立code，基础作答不依赖网关可用性'],
'OPS':[
'actor/target/action/result/start/end/page；管理员只读，时间必须含时区，稳定排序',
'CLI初始化幂等；危险重置仅显式演示目录及确认令牌，审计记录操作者和范围',
'数据库实际查询、附件临时读写、active配置和密钥存在布尔；故障503且隐藏路径秘密',
'SQLite一致性备份+附件hash清单+schema/app/config版本，包含完整性校验',
'目标目录须不存在，恢复后核外键、数量、hash和授权检索；失败目录隔离',
'锁定依赖、迁移、初始化、启动、账号交付和排障按步骤给出，独立电脑复现',
'SF→版本→输入/预期/实际→证据→结论；贡献/AI使用署名，失败和复测记录追加']
}
for group in details:
 assert len(details[group])==sum(i[1]==group for i in items),(group,len(details[group]))
tech=(root/'2026-10-27-smart-learning-planner-technical-design.md').read_text(encoding='utf-8')
moduleinfo={}
for match in re.finditer(r'### ([A-Z]+) [^\n]+\n(.*?)(?=\n### |\Z)',tech,re.S):
 if match[1] in details:
  entry=re.search(r'实现归属与数据/API入口：([^\n]+)',match[2])
  if entry:moduleinfo[match[1]]=entry[1]
main=root/'2026-11-02-zhixing-followup-preimplementation-technical-design.md'
text=main.read_text(encoding='utf-8')
section='## 11. 127项逐项编码设计（2026-11-03修订）'
text=text.split(section)[0]
out=[section,'','本节覆盖全部127个稳定SF编号，包含已验收功能的维护契约和后续增量设计。下列新增字段、状态与端点属于设计目标，落地情况以验收台账为准。第2节保留2026-11-02历史快照，最新统计以subfunction-checklist.md为准。','',
'### 11.1 公共执行与验证契约','',
'所有接口使用/api/v1前缀。既有物理表classes、resource_versions、attempts、profile_refresh_events优先复用，模块逻辑表名在迁移设计时映射，禁止重复建设同一事实。既有接口以app/api路由为兼容基线，新增字段默认兼容旧数据，公开DTO隐藏密码哈希、令牌、storage_key和密钥环境值。','',
'写入流程为校验输入、认证、对象授权、读取版本、执行业务事务、追加审计/刷新事件、返回公开结果。长任务202并返回run/job ID，查询接口读取持久状态。401清私密视图，403/404阻止访问，409提示刷新，422定位输入，429附可重试时间，503说明依赖故障。失败事务不留部分业务写入。','',
'页面提供空态、加载、成功与失败反馈。写入期间同步防重，取消确认不发请求。查询筛选变动重置页码，异步结果绑定对象和请求版本，切页取消轮询，失败保留可恢复输入。日期存UTC，日预算按用户ZoneInfo时区计算。','',
'验收记录必须包含测试身份、预置状态、请求或页面操作、预期及实际、数据库副作用和版本证据。只读项增加越权及空结果验证，写入项增加越权、陈旧版本、重复提交及失败后重读。涉及显隐、确认、复制、播放和排版的判据必须有浏览器结果。','']
for group in details:
 out+=['### 11.'+str(list(details).index(group)+2)+' '+group+'模块共享契约','',moduleinfo.get(group,''),'']
 for sf,g,num,name,criterion in items:
  if g!=group:continue
  decision=details[g][int(num)-1]
  out+=['#### '+sf+' '+name,'',
  '**业务判据**。'+criterion,'',
  '**输入、处理和结果**。'+decision+'。','',
  '**数据与状态**。本项使用上方模块数据入口。'+('该项读取结果不触发新的评分或业务事实。' if any(x in name for x in ['查询','列表','查看','解释','显隐','导航','预览','历史','说明','筛选']) else '本项写入遵循11.1事务规则，业务结果与相关审计/刷新事件同时提交。')+'涉及的版本、唯一键和状态限制按本项输入处理契约执行。','',
  '**页面与授权**。入口使用现有原型对应模块页面。'+({'AUTH':'认证页面及当前身份会话执行。','ACCOUNT':'管理员操作账号，个人资料仅本人操作。','CLASS':'教师管理本人班级，学生操作本人成员关系。','RESOURCE':'资源所有者管理，读取校验private/class/school范围。','SEARCH':'仅检索当前身份授权且状态允许的资料。','GOAL':'仅学生本人操作目标，班级关联单独校验。','DIAG':'诊断归目标所有者，教师不读取私人诊断。','PATH':'正式路径归学生本人，图谱维护仅管理员。','TASK':'教师管理本人班级任务，学生只提交本人分配。','ASSESS':'本人查询反馈，教师只复核本人班级授权提交。','REPLAN':'只允许目标所有者创建与处理预览。','PROFILE':'学生读本人完整画像，教师读本人班级投影。','AI':'配置仅管理员维护，run查询校验发起者。','OPS':'审计及管理动作限管理员，备份恢复仅受控CLI。'}[g]),'',
  '**正常验收**。构造满足权限及前置状态的输入，执行“'+name+'”，逐项检查“'+criterion+'”，记录公开响应、页面结果与相关存储状态。','',
  '**异常和复测**。按11.1验证身份与对象边界，并针对本项处理规则中的限制构造反例。失败后重读原对象，检查状态和版本是否符合事务契约。修复后用相同输入复测，证据以'+sf+'命名并写入验收台账。','']
main.write_text(text+'\n\n'+'\n'.join(out)+'\n',encoding='utf-8')
for suffix in ['requirements-spec','design','technical-design']:
 p=root/('2026-10-27-smart-learning-planner-'+suffix+'.md')
 s=p.read_text(encoding='utf-8')
 marker='## 127项详细设计追踪补充（2026-11-03）'
 s=s.split(marker)[0]
 rows=[marker,'','127项逐项编码契约位于[后续任务编码前分析与技术设计第11节](2026-11-02-zhixing-followup-preimplementation-technical-design.md#11-127项逐项编码设计2026-11-03修订)。本补充保留既有FR/AT/SF编号。新增设计约束的实际落地与验收结论使用独立台账。','',
 '| 子功能 | 名称 | 设计契约摘要 |','| --- | --- | --- |']
 for sf,g,num,name,criterion in items:
  rows.append('| '+sf+' | '+name+' | '+(criterion if suffix=='requirements-spec' else details[g][int(num)-1])+' |')
 p.write_text(s+'\n\n'+'\n'.join(rows)+'\n',encoding='utf-8')
print('127 detailed sections, 3 cross-reference matrices written')
