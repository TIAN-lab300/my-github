# 20项集中交付与验收

日期：2026-11-02。范围为登录14项及账号6项，共20项。不是20项从零新增：已有实现补齐边界后，本批完成逐项验收。

新增补齐：账号角色/状态过滤和分页、冷却剩余时间与Retry-After、会话失效清理全部个人页面状态、同步请求锁防止瞬时重复提交。浏览器首次测试发现双请求，修复后复测通过。

验收环境：独立backend/data/batch20数据库、127.0.0.1:8002、隐藏Edge；不修改原演示数据库或账号。

| 编号 | 功能 | 验收证据 |
| --- | --- | --- |
| SF-ACCOUNT-02 | 创建账号 | 通过：backend/tests/test_batch20.py::test_subfunction[SF-ACCOUNT-02] |
| SF-ACCOUNT-03 | 列表与筛选 | 通过：backend/tests/test_batch20.py::test_subfunction[SF-ACCOUNT-03] |
| SF-ACCOUNT-05 | 停用与恢复 | 通过：backend/tests/test_batch20.py::test_subfunction[SF-ACCOUNT-05] |
| SF-ACCOUNT-06 | 密码重置 | 通过：backend/tests/test_batch20.py::test_subfunction[SF-ACCOUNT-06] |
| SF-ACCOUNT-07 | 角色保护 | 通过：backend/tests/test_batch20.py::test_subfunction[SF-ACCOUNT-07] |
| SF-ACCOUNT-08 | 误操作防护 | 通过：frontend/batch20-browser.mjs |
| SF-AUTH-01 | 账号密码登录 | 通过：backend/tests/test_batch20.py::test_subfunction[SF-AUTH-01] |
| SF-AUTH-02 | 输入检查 | 通过：backend/tests/test_batch20.py::test_subfunction[SF-AUTH-02] |
| SF-AUTH-03 | 密码显隐 | 通过：frontend/batch20-browser.mjs |
| SF-AUTH-04 | 提交防重与反馈 | 通过：frontend/batch20-browser.mjs |
| SF-AUTH-05 | 首次登录改密 | 通过：backend/tests/test_batch20.py::test_subfunction[SF-AUTH-05] |
| SF-AUTH-06 | 本人修改密码 | 通过：backend/tests/test_batch20.py::test_subfunction[SF-AUTH-06] |
| SF-AUTH-07 | 忘记密码处理 | 通过：frontend/batch20-browser.mjs |
| SF-AUTH-08 | 当前身份与角色导航 | 通过：backend/tests/test_batch20.py::test_subfunction[SF-AUTH-08] |
| SF-AUTH-09 | 会话过期 | 通过：backend/tests/test_batch20.py::test_subfunction[SF-AUTH-09] |
| SF-AUTH-10 | 安全退出 | 通过：backend/tests/test_batch20.py::test_subfunction[SF-AUTH-10] |
| SF-AUTH-11 | 停用与重置即时失效 | 通过：backend/tests/test_batch20.py::test_subfunction[SF-AUTH-11] |
| SF-AUTH-12 | 失败限流与恢复 | 通过：backend/tests/test_batch20.py::test_subfunction[SF-AUTH-12] |
| SF-AUTH-13 | 跨标签页退出同步 | 通过：frontend/batch20-browser.mjs |
| SF-AUTH-14 | 认证审计 | 通过：backend/tests/test_batch20.py::test_subfunction[SF-AUTH-14] |

结果：15项独立接口用例通过，5项浏览器用例通过，全量后端36项通过，前端生产构建通过。机器记录为backend-tests.xml和batch20-browser.json。

范围限制：其余107项未由本批结论覆盖；外部云端、向量等缺口仍保留。验收是本地配置下的行为验证，不构成压力测试或长期运行评价。
