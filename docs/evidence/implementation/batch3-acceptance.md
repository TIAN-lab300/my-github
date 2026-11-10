# 第三批20项实现与验收（2026-11-03）

本批为TASK-01～10，ASSESS-01～05、07～08，PROFILE-01～03。已通过的ASSESS-06继续回归。验收基线为v3.3需求与后续编码前设计第11节。

使用独立backend/data/batch3和8004服务，Edge无界面1440×1100。页面脚本为frontend/batch3-browser.mjs；接口专项为backend/tests/test_batch3.py。

20项参数化接口专项与20项页面演练通过，无pageerror。最终全量84项通过，前端生产构建通过。迁移0007已在隔离库升级验证，当前8000运行库未升级。

| 编号 | 功能 | 接口及异常判据 | 页面实际观察 | 结果 |
| --- | --- | --- | --- | --- |
| SF-TASK-01 | 草稿创建编辑 | 草稿标题/说明/时长/截止/题目/接收人版本化编辑；非法接收人及旧版本拒绝 | 页面创建草稿并编辑四种题型快照 | 通过 |
| SF-TASK-02 | 接收人选择 | 发布时有效成员快照，指定一人后另一成员无待办 | 发布预览仅指定学生，发布后不可编辑，另一成员无分配 | 通过 |
| SF-TASK-03 | 发布冻结 | 已发布草稿编辑409，关联resource_version_id冻结，分配唯一 | 发布预览仅指定学生，发布后不可编辑，另一成员无分配 | 通过 |
| SF-TASK-04 | 学生待办筛选 | not_started→in_progress→completed及overdue/cancelled；暂存恢复，非法状态422 | 暂存后刷新恢复全部答案，进行中筛选有效 | 通过 |
| SF-TASK-05 | 文本链接打卡提交 | 文本/HTTP(S)链接/打卡保存，班外提交404，非法链接422 | 文本链接打卡三种普通任务页面提交成功 | 通过 |
| SF-TASK-06 | 逾期补交 | 逾期允许补交，late=1，重复提交不改变首次完成时间，按时率为0 | 页面逾期筛选与补交标记有效 | 通过 |
| SF-TASK-07 | 撤回与关闭 | 撤回取消待办和预约；关闭阻止提交，历史仍可查询 | 教师页面撤回关闭以及关联修订草稿创建成功 | 通过 |
| SF-TASK-08 | 变更重发 | 关闭/撤回后关联修订草稿，原任务作答保留，发布复核资料状态 | 教师页面撤回关闭以及关联修订草稿创建成功 | 通过 |
| SF-TASK-09 | 教师查看提交 | 教师本人可查看提交，另一教师详情404且列表无记录 | 教师查看本人提交并按公开rubric复核，页面更新评分状态 | 通过 |
| SF-TASK-10 | 负荷联动 | 预算不足返回冲突学生及页面提示，教师预约显式记录，原路径不修改 | 页面发布后保留预算冲突提示，学生路径仍为原活动版本 | 通过 |
| SF-ASSESS-01 | 客观规则评分 | single/boolean/fill/multi按assessment-v1评分；多选集合严格相等，输入选项校验 | 四种题型页面提交100%，展示答案解析知识点建议 | 通过 |
| SF-ASSESS-02 | 即时结果反馈 | 返回答案解析知识点建议；历史反馈一致，答案仅提交后可见 | 四种题型页面提交100%，展示答案解析知识点建议 | 通过 |
| SF-ASSESS-03 | 主观待复核 | 主观题pending_review、score=null，复核前无主观掌握观察 | 主观题页面待复核且无评分 | 通过 |
| SF-ASSESS-04 | 教师rubric复核 | rubric-v1分数0～1，.75达标；本人教师复核，其他教师404 | 教师查看本人提交并按公开rubric复核，页面更新评分状态 | 通过 |
| SF-ASSESS-05 | 评分更正 | grades版本1/2及原因保留，观察更正重放且有效证据不重复 | 评分更正原因与历史反馈可见 | 通过 |
| SF-ASSESS-07 | BKT更新与解释 | 未测为空；prior/posterior/attempt/parameter_version/threshold可读 | 记录页按任务查询并显示阅读提交掌握分层、BKT概率版本依据 | 通过 |
| SF-ASSESS-08 | 打卡边界 | 时长/比例越界422，困难与备注保存可更新，打卡不增加掌握观察 | 页面保存比例、困难和备注后可见，掌握证据数量未增长 | 通过 |
| SF-PROFILE-01 | 本人记录筛选 | UTC日期、目标、班级、资源、任务、类型和分页，限定本人；非法页码拒绝 | 记录页按任务查询并显示阅读提交掌握分层、BKT概率版本依据 | 通过 |
| SF-PROFILE-02 | 进度分层 | 阅读、提交、掌握独立计数，阅读完成不等于任务或掌握完成 | 记录页按任务查询并显示阅读提交掌握分层、BKT概率版本依据 | 通过 |
| SF-PROFILE-03 | 确定性统计 | 零分母null，真实完成率与按时率计算，源事件去重 | 记录页按任务查询并显示阅读提交掌握分层、BKT概率版本依据 | 通过 |

## 源码与持久化

- 0007_task_execution新增assignments.draft、attempts.late/scoring_version、tasks.resource_version_id，旧作答回填late，旧已发布任务补资源版本引用。
- backend/app/api/tasks.py；frontend/src/TaskInbox.tsx、PublishTask.tsx、QuestionEditor.tsx、RecordEditor.tsx
- backend/app/services/learning.py、api/tasks.py、api/goals.py；frontend/src/TaskInbox.tsx、main.tsx
- backend/app/api/profiles.py；frontend/src/RecordFilters.tsx、main.tsx

## 证据入口

- [全量84项报告](backend-tests.xml)和[20项专项报告](batch3-tests.xml)。全量报告另含冻结任务来源读取回归。
- [20项浏览器结果](batch3-browser.json)。
- [客观评分截图](batch3-objective.png)、[主观更正截图](batch3-review.png)、[分层记录截图](batch3-records.png)、[预算冲突截图](batch3-budget-conflict.png)。

## 失败与复测

- 首轮解释字段被展开写入mastery_snapshots，触发无列错误。改为显式写数值字段，解释随画像快照保存；全量复测通过。
- 已有打卡重复请求未保存更新备注。改为仅更新困难与备注，学习时长和预约释放继续幂等；专项复测通过。
- 筛选进行中时提交后任务自然移出结果。页面脚本改为切回全部后检查已完成反馈。
- 发布冲突提示随草稿组件卸载而消失。父页面保留通知，冲突页面复测通过。
- 题目编辑表单补齐明确可访问标签，切填空/主观题清选项，学生端按kind渲染，四题页面复测得100%。

## 完成边界

本批20项与先前47项合计67/127，通过状态依据本文件列出的正常及异常验证。剩余60项继续按台账处理。云端智能、向量与联网等能力的验收结论在各自条目记录。实际运行库迁移和8000服务更新尚待本地部署。
