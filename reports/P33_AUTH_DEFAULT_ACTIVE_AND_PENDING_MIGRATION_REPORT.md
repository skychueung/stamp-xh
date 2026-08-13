# STAMP 开发认证默认激活与 pending 迁移报告

- 日期：2026-07-08
- Gate：`P33_AUTH_DEFAULT_ACTIVE_PENDING_MIGRATION_COMPLETE`
- 开发副本：`/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev`
- 作用范围：开发前端 12823 / 开发后端 12824
- 正式环境：8080 / 8001 未修改

## 根因

1. `POST /api/v1/auth/register` 将新用户状态硬编码为 `pending`。
2. `User.status` ORM 默认值为 `pending`。
3. 登录接口将 pending 与 disabled 合并为同一个 403 文案。
4. 前端注册成功页与 AuthContext 硬编码“等待管理员审批”。

## 修复逻辑

- 默认环境：新注册用户为 `active`，注册后可直接登录。
- 可选审批环境：设置 `STAMP_REQUIRE_ADMIN_APPROVAL=true` 后，新注册用户为 `pending`，仍可由管理员审批。
- 登录时：
  - `active`：允许登录；
  - `pending` 且审批模式关闭：在正确密码验证后兼容激活并允许登录；
  - `pending` 且审批模式开启：返回明确的等待审批提示；
  - `disabled`：始终返回明确禁用提示并拒绝登录；
  - 未知状态：fail closed。
- 前端注册成功文案读取后端真实状态，不再默认显示等待审批。
- 前端 legacy 合并错误不再显示错误的等待审批文案。

## 修改文件

| 文件 | SHA256 |
|---|---|
| `backend/app/routers/auth.py` | `5153627225062e342990f6d3517d4853569b5c5c220da2e8e4492be285e47597` |
| `backend/app/models/user.py` | `201e3e39e966b5d75055595c5d557ce8a53bc998a6715520562f5dbbe4b19768` |
| `backend/scripts/migrate_pending_users_to_active.py` | `6ae28fab7a1758655465777e20207c4cdb88fa3a9b6a580fc4dde0fd4f0b2b78` |
| `backend/tests/test_auth_p33v_a1.py` | `665a004d7a7478a5989ee3843719e9922f1a356d5e2868697f2fcb5853c3f1da` |
| `src/contexts/AuthContext.tsx` | `9ac5b59026e3d3ba038cae5b6523d44bd772faa283bda9bf7e64bae7599d9223` |
| `src/pages/RegisterPage.tsx` | `7d7b57ec0353ed3426203cef6da20a68335fda3c8757f6cc3ee93bc7f08254ec` |
| `src/lib/loginForm.ts` | `f36fab74b663b61837ac30f01cb3de905b7bc737f673d2b10d9c83d8e8cedf72` |
| `src/lib/loginForm.test.ts` | `a94c228a2bec4ceba88a1aa34c1365d269ca93f7bc60477952ef4c3d97817c65` |

未修改科学计算、肽设计、候选生成、模型 registry 或正式环境文件。

## 备份与数据库迁移

- 完整备份：`/home/xh/kxc/stampup/backups/p33_auth_default_active_20260708_202143/`
- 备份数据库：`data_dev/db/stamp_dev.db`
- 备份数据库 SHA256：`1b932ec157dfaf5240fb6ebef95d1412573844f02920c8aa23c340229efb1cad`
- 数据库 schema 迁移：无。
- 数据迁移：有；安全脚本将 2 个 `role=user,status=pending` 账号改为 active。
- disabled 修改数：0；管理员记录及 password hash 与备份完全一致。
- 迁移后：`admin:active=1`、`user:active=7`、`user:pending=0`。
- 脚本默认 dry-run，仅显式 `--apply` 才提交；审批模式开启时拒绝执行。

## 测试与验证

- Python 编译检查：PASS。
- 后端认证测试：12/12 PASS。
- 后端认证 + 靶向肽关键回归：67/67 PASS（5 个既有 warning）。
- 前端登录错误映射：10/10 PASS。
- 前端 scoped ESLint（RegisterPage/loginForm）：PASS。
- `npm run build`：PASS；live bundle `index-hE7ozQdA.js`。
- Live 默认注册：201，状态 active，`approval_required=false`。
- Live 新用户登录：200。
- Live disabled 用户登录：403，禁用文案正确。
- Live 测试账号：2 个，验证后全部清理。
- 管理员 id/role/status/password hash 与备份一致。

## 服务与正式环境边界

- 12823 已重启：PID `3485293`。
- 12824 已重启：PID `3485237`。
- 正式 8001 PID `3074240` 保持不变。
- 正式 8080 监听保持不变。
- 未重置或记录任何真实密码。

## Git 状态

- Branch：`v1.5-md-computation-pilot`
- Commit：`f073baa3d894650689555cfef5d4292d71470760`
- 整体 dirty entries：1700（大量既存工作区改动，本任务未清理或回滚）。
- 本任务相关：`src/contexts/AuthContext.tsx` 为 modified；其余 7 个相关文件在当前基线中为 untracked。

## 风险与后续建议

- `STAMP_REQUIRE_ADMIN_APPROVAL` 默认 false；若未来需要审批模式，在启动 12824 前设置为 true 并重启开发后端。
- AuthContext 全文件 ESLint 仍有两条既存规则错误（effect 内 setState、fast-refresh export），不属于本任务改动行；未扩大范围重构。
- 用户提供的截图包含可见凭据，应视为已暴露并尽快轮换该普通用户密码；本任务未使用或保存截图中的密码。

## 回退

1. 先备份当前开发数据库与上述 8 个文件。
2. 从 `/home/xh/kxc/stampup/backups/p33_auth_default_active_20260708_202143/` 恢复 7 个原文件和开发数据库。
3. 删除本任务新增的 `backend/scripts/migrate_pending_users_to_active.py`。
4. 重新构建前端，只重启开发 12823/12824。
5. 禁止使用 `git reset --hard`、`git checkout .` 或 `git clean`。
