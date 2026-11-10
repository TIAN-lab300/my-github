# 第二批20项页面验收记录

2026-11-03，Edge无界面浏览器，1440×1000，独立8003服务和batch20数据目录。observed代表已执行下列观察，完整通过条件需与接口及异常证据合并审核。

| 编号 | 页面状态 | 实际结果 |
| --- | --- | --- |
| SF-CLASS-03 | observed | 自定义有效期与次数可填写，生成成功后显示复制入口；剪贴板内容待验证 |
| SF-CLASS-07 | observed | 教师成员列表显示移除入口，实际移除及退班后续验证 |
| SF-CLASS-08 | observed | 归档入口可见，归档后只读待独立操作验证 |
| SF-RESOURCE-01 | observed | 页面组合筛选触发kind=text服务端查询并返回200 |
| SF-RESOURCE-02 | observed | 上传信息与云端授权字段可见 |
| SF-RESOURCE-03 | observed | 混合上传页面显示正常文件，伪装媒体失败提示需结合接口证据 |
| SF-RESOURCE-04 | observed | 伪装MP4在上传结果显示格式失败 |
| SF-RESOURCE-05 | observed | 详情显示正文ready解析状态；排队失败重试待演练 |
| SF-RESOURCE-06 | observed | 版本历史与新正文上传入口可用，候选切换由接口测试覆盖 |
| SF-RESOURCE-08 | observed | 正文脚本文本未执行，原文件下载入口可见 |
| SF-RESOURCE-07 | observed | 教师页面发布成功并切换为下架操作 |
| SF-RESOURCE-11 | observed | 网址及推荐理由可编辑，保存发布待验证 |
| SF-RESOURCE-13 | observed | 学生通过详情页面保存17分钟学习记录 |
| SF-RESOURCE-12 | observed | 学生私有上传入口可操作，隔离由接口测试覆盖 |
| SF-ACCOUNT-04 | observed | 页面修改姓名成功，服务端重读一致 |
| SF-ACCOUNT-01 | pending | 本次页面演练未覆盖完整判据 |
| SF-CLASS-09 | pending | 本次页面演练未覆盖完整判据 |
| SF-RESOURCE-09 | pending | 本次页面演练未覆盖完整判据 |
| SF-RESOURCE-10 | pending | 本次页面演练未覆盖完整判据 |
| SF-RESOURCE-14 | pending | 本次页面演练未覆盖完整判据 |

截图见batch2-resource-page.png。脚本为frontend/batch2-page-acceptance.mjs。
本轮15项有页面观察，5项待补，未新增完整通过声明。管理员初始化属于CLI操作，应以初始化幂等测试验证。


## 第二轮补测

- SF-RESOURCE-14，observed。无正文音频可通过页面发布，明确显示无可检索正文
- SF-RESOURCE-09，observed。音频实际播放成功，上传字幕后回草稿，重新打开显示字幕正文
- SF-RESOURCE-10，observed。图片成功解码预览，点击下载取得原始文件名
- SF-CLASS-09，observed。通过页面选人并创建补发草稿，服务端重读为draft；原任务保持已发布
- SF-CLASS-07，observed。教师页面确认移除后，成员行不再提供有效成员移除按钮
- SF-CLASS-08，observed。确认归档后归档、编辑和生成邀请均禁用

截图为batch2-audio-caption.png和batch2-image.png。管理员初始化为CLI功能，页面验收不适用。第二轮6项实际操作完成；首轮与第二轮共19项有页面观察，完整异常边界及组合判据继续按逐项记录补齐。


## 第三轮判据补充

五个专项用例通过，报告为batch2-closure-tests.xml。

- SF-ACCOUNT-01通过。首次创建管理员要求改密；重复初始化保留密码哈希和账号，用例为test_sf_account_01_initialize_is_idempotent。
- SF-ACCOUNT-04通过。空白超长拒绝，姓名保存可重读，角色字段无法提权；页面保存已验证，用例为test_sf_account_04_validation_and_persistence。
- SF-CLASS-07通过。退出与移除均取消未完成分配并释放预约，完成作答保留，资源下载及提交失权，用例为test_sf_class_07_cancels_only_unfinished。
- SF-RESOURCE-08通过。下载字节与正文一致、attachment与nosniff有效，下架禁止下载；页面脚本不执行，用例为test_sf_resource_08_download_and_secret_fields。

本批20项中新增4项通过，16项仍需补齐完整判据。全项目累计31/127通过。


## 第四轮补测

7项闭环专项通过，剪贴板与链接页面2项通过。

- SF-CLASS-03通过。自定义6小时/3次与服务端一致，复制原码逐字相等。
- SF-RESOURCE-11通过。页面登记待审并发布，非法协议和带凭据网址拒绝，外链无正文且不进入正文检索。
- SF-RESOURCE-13通过。正数时长校验，重复保存17分钟同会话仅一条，完成状态持久化，跨资源会话冲突拒绝。

本批累计7/20通过，13项仍需补齐完整判据。全项目累计34/127通过。页面结果见batch2-copy-link.json，截图见batch2-link-review.png。


## 第五轮解析与版本页面补测

修复提交候选版本关闭详情而中断轮询的问题。SF-RESOURCE-05重试、失败回显及接口去重恢复4项测试通过，登记通过。SF-RESOURCE-06新正文后台完成后自动切换草稿，详情正文和历史可查询，仍需历史引用完整判据。结果为batch2-version-recovery.json，截图为batch2-version-recovery.png。累计本批8/20、全项目35/127通过。


## 第六轮私有资料补测

SF-RESOURCE-12通过。页面上传、阅读和跨角色下载隔离通过，cloud_allowed默认false，布尔修改和字段保护接口已验证。修复本人私有正文可生成候选但接受时被发布条件拒绝的问题，3项资源回归通过。证据为batch2-private.json、resource-batch-tests.xml及batch2-private.png。本批9/20、全项目36/127通过。


## 第七轮上传与附件边界

5项资源专项通过。SF-RESOURCE-02及14通过，上传字段保存与权限、附件不可作为正文证据的反例已验证。检索与规划统一增加ready/indexed条件，防止遗留派生数据进入证据。结合页面字段、混合上传、真实媒体播放及附件发布记录，本批11/20、全项目38/127通过。


## 第八轮证据合并与历史引用

全量62项通过，历史版本正文接口新增路径引用授权，路径页面增加引用正文入口。

- SF-CLASS-08通过。页面归档后编辑邀请禁用；接口取消未完成负荷、保留成绩、拒绝新邀请及提交。
- SF-CLASS-09通过。页面选择指定学生创建补发草稿；接口验证晚入班不自动分配、关联原任务、重复请求复用与指定发布。
- SF-RESOURCE-01通过。页面组合筛选已发送实际查询；接口验证班级、类型、标签、标题、发布/解析状态与分页前授权。
- SF-RESOURCE-06通过。候选解析原子切换、失败保留旧版、元数据审计；已接受路径可读取原版本，成员退出失权。
- SF-RESOURCE-07通过。正文发布须索引就绪，非所有者拒绝，下架阻止新详情与检索；既有路径历史正文保留原班级授权检查。
- SF-RESOURCE-09通过。浏览器实际播放音频并关联字幕，字幕生成独立版本回草稿；非音视频字幕拒绝，旧版记录保留。
- SF-RESOURCE-10通过。图片浏览器解码预览及原文件下载成功；附件接口状态not_applicable，班外下载拒绝。

本批18/20通过，全项目45/127通过。仍缺RESOURCE-03总量100MiB边界的独立实测、RESOURCE-04真实文本PDF与扫描PDF及完整MIME矩阵。新历史正文页面按钮已构建，浏览器点击该新增按钮待验证，历史授权行为已有接口回归。


## 第九轮最终边界验证

8项资源专项通过。实际发送6份各20MiB文件，前5份共100MiB成功，第6份拒绝；11文件整批拒绝、单文件超限和混合成功失败此前已验证。构造真实PDF验证带文本可抽取，空白PDF无可读正文时失败并提示。RESOURCE-03、04通过，本批20/20完成，全项目47/127通过。新增历史引用按钮仍待单独浏览器点击验证，历史权限与版本语义已用接口测试验证。
