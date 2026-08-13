# P33V-A1 工程交付清单

## 目标
为 STAMP 靶向肽开发副本实现注册、登录、退出、管理员审批和受保护页面。

## 范围与边界
- 开发副本：`/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev`
- 前端端口：`12823`
- 后端端口：`12824`
- 正式服务 `8001/8080` 及 `/home/xh/stamp` **未修改、未重启**
- 未运行模型、未加载 checkpoint、未使用 GPU
- P33U-D8 保持未启动
- D5/D7 及所有科学证据冻结

## 访问地址
- 登录页：http://100.75.69.36:12823/login
- 注册页：http://100.75.69.36:12823/register
- 用户管理（仅 admin）：http://100.75.69.36:12823/admin/users

## 基准 SHA
- Git HEAD：`f073baa3d894650689555cfef5d4292d71470760`
- Phase 0 数据库备份 SHA：
  - `backups/stamp_dev.db.phase0.20260704_002941.bak`：`6c2c4468b2a44a8f86aa42e359b1ce58161b5fb61853449457a41e8484d85db6`
  - `backups/p33t_results.db.phase0.20260704_002941.bak`：`3f474b491e4dbf723737c3eba84e92e3b992b5c87b6c8d5ebeb5c764622304ff`
- 当前开发数据库 SHA：
  - `data_dev/db/stamp_dev.db`：`9796c7807e2d9f80fea81516bd65928441b4ea9bd3c68656ad8b1b660017d476`
  - `data_dev/db/p33t_results.db`：`1471a36ade947bc873d97e341c753caf010fcee1a10153a03e2ae3a8198770f3`

## 新增/修改文件
### 后端
- `backend/app/core/limiter.py` — 共享 slowapi limiter
- `backend/app/core/security.py` — bcrypt、签名 Cookie、CSRF、依赖注入
- `backend/app/core/config.py` — 增加 `secret_key`
- `backend/app/models/user.py` — User ORM 模型
- `backend/app/models/__init__.py` — 导出 User
- `backend/app/routers/auth.py` — `/api/v1/auth/*`
- `backend/app/routers/admin.py` — `/api/v1/admin/users/*`
- `backend/app/routers/p33t.py` — 9 个 `/api/v1/target-design/*` 端点接入认证
- `backend/app/routers/target_design_workflow.py` — workflow artifact 下载接入认证
- `backend/alembic/env.py` — 修复 DB URL fallback
- `backend/alembic/versions/2026_07_04_0043-1e3bcd1d779f_add_users_table_for_p33v_a1.py` — users 表迁移（SHA：`41297bbc73aca181e4645f749f3c08f9df4edc920a5a5cb523df9a1072818b67`）
- `backend/scripts/bootstrap_admin.py` — 管理员 kxc 初始化脚本
- `backend/tests/test_auth_p33v_a1.py` — 认证集成测试
- `backend/requirements.txt` — 增加 bcrypt、itsdangerous、slowapi

### 前端
- `src/App.tsx` — 路由、ProtectedRoute、登录后回跳
- `src/contexts/AuthContext.tsx` — Cookie 认证状态
- `src/components/platform/Sidebar.tsx` — 用户信息、退出按钮
- `src/pages/LoginPage.tsx`
- `src/pages/RegisterPage.tsx`
- `src/pages/ChangePasswordPage.tsx`
- `src/pages/ForbiddenPage.tsx`
- `src/pages/AdminUsersPage.tsx`
- `src/lib/errorUtils.ts` — 统一 FastAPI `detail` 解析与中文提示
- `src/lib/errorUtils.test.ts` — FastAPI 错误解析单元测试
- `src/lib/passwordPolicy.ts` — 客户端密码策略校验
- `src/lib/passwordPolicy.test.ts` — 密码策略单元测试

### 配置
- `backend/.env` / `backend/.env.example` — 增加 `STAMP_SECRET_KEY`、`STAMP_COOKIE_SAMESITE`

## 数据库迁移
### 升级
```bash
cd /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/backend
source .venv/bin/activate
alembic upgrade head
```

### 回滚
```bash
cd /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/backend
source .venv/bin/activate
alembic downgrade -1
```

当前迁移链：`fce11772abec`（baseline）→ `1e3bcd1d779f`（add users table）。
回滚 `-1` 将删除 `users` 表，其他业务表不受影响。

## 管理员初始化
- 用户名：`kxc`
- 角色：`admin`
- 状态：`active`
- 首次登录强制修改密码：是
- 初始化命令示例（密码通过 stdin 注入，不进入历史记录）：
  ```bash
  cd /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/backend
  source .venv/bin/activate
  read -s PASSWORD
  echo "$PASSWORD" | python scripts/bootstrap_admin.py
  unset PASSWORD
  ```
- 若 `kxc` 已存在，脚本会停止并报告，不会覆盖密码或权限。

## API 契约
### 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册，默认 `role=user`，`status=pending` |
| POST | `/api/v1/auth/login` | 登录，设置 HttpOnly + CSRF Cookie |
| POST | `/api/v1/auth/logout` | 退出，需要 `X-CSRF-Token` 头 |
| GET  | `/api/v1/auth/me` | 当前用户信息 |
| POST | `/api/v1/auth/change-password` | 修改密码，需要 `X-CSRF-Token` 头 |

### 管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/v1/admin/users` | 列出用户（admin only） |
| POST | `/api/v1/admin/users/{id}/approve` | 批准 pending 用户（admin only，需 CSRF） |
| POST | `/api/v1/admin/users/{id}/disable` | 禁用用户（admin only，需 CSRF） |

### 受保护下载
- `/api/v1/target-design/*`（9 个端点）需要登录
- `/api/v1/workflows/target-design/artifacts/{ref}/download` 需要登录
- `/health`、`/api/health` 保持匿名

## 安全机制
- 密码存储：bcrypt 哈希（ rounds=12 ）
- 会话：itsdangerous 签名、HttpOnly、Secure 条件适配、SameSite=Lax、24h 过期
- 长期 token 不存 localStorage
- 登录错误统一提示，防止用户名枚举
- 登录限速：默认 5 次/分钟/IP
- 注册限速：默认 3 次/小时/IP
- 连续 5 次登录失败锁定 15 分钟
- 管理操作 CSRF 双提交校验
- 路径穿越与白名单防护保持原有逻辑

## 测试结果
```
python -m pytest tests/test_auth_p33v_a1.py -v
============================= test session starts ==============================
tests/test_auth_p33v_a1.py::test_register_pending PASSED
tests/test_auth_p33v_a1.py::test_login_pending_rejected PASSED
tests/test_auth_p33v_a1.py::test_disabled_user_rejected PASSED
tests/test_auth_p33v_a1.py::test_wrong_password_unified_message PASSED
tests/test_auth_p33v_a1.py::test_admin_approve_and_login_flow PASSED
tests/test_auth_p33v_a1.py::test_normal_user_cannot_access_admin PASSED
tests/test_auth_p33v_a1.py::test_csrf_required_for_logout PASSED
tests/test_auth_p33v_a1.py::test_sql_injection_username_rejected PASSED
tests/test_auth_p33v_a1.py::test_path_traversal_artifact_rejected PASSED
tests/test_auth_p33v_a1.py::test_unauthenticated_api_returns_401 PASSED
======================== 10 passed, 4 warnings in 3.60s ========================
```

额外手动验证：
- 6 次快速错误登录后第 6 次返回 `429 Too Many Requests`
- 未登录访问 `/api/v1/target-design/results` 返回 `401`
- 登录后访问返回 `200`
- 退出后 CSRF Cookie 被清除
- 管理员首次登录强制修改密码流程验证通过，测试后已重置为初始密码以待用户验收

## 构建
```bash
npm run build
```
结果：`tsc -b` 零 TypeScript 错误，`vite build` 成功。

## 服务状态
- 开发前端 `12823`：运行中（node）
- 开发后端 `12824`：运行中（python）
- 正式后端 `8001` PID：`3074240`（与 Phase 0 审计一致，未重启）
- 正式前端 `8080`：运行中（未重启）

## P33V-A1 密码修改页 UX 修复（本轮）
### 修复内容
- `AuthContext` 统一使用 `parseFastApiError` 解析登录、注册、修改密码的 FastAPI 错误。
- `ChangePasswordPage` 使用 `validatePasswordChange` 进行客户端密码策略校验，错误提示改为中文。
- 修改成功后跳转 `/target-design`。

### 验证结果
- 当前密码错误 → 提示：`当前密码错误，请重新输入。`
- 新密码不足 8 位 → 提示：`新密码长度不能少于 8 个字符。`
- 两次新密码不一致 → 提示：`两次输入的新密码不一致。`
- 修改成功后 `/api/v1/auth/me` 返回 `must_change_password=false`，跳转 `/target-design`。
- 旧密码登录失败，新密码登录成功且 `must_change_password=false`。
- 测试后已将 `kxc` 重置为初始密码并设置 `must_change_password=true`，等待用户登录验收。

### 新增/修改文件 SHA256
```
4a4d95134e28221f526ef9e38811a3ae7ad848f5f64c8c19ba19b46431573a1c  src/contexts/AuthContext.tsx
9e826fd0699032d5f859124a7cae823beef8e117fdec0d65a822d8b3e3e7278c  src/pages/ChangePasswordPage.tsx
875f2e40bd0654ed57568fe3adb4f45809da18b9547be8fff87ffa58e6f9b486  src/lib/errorUtils.ts
2b7922a826c424ce5f7a2422de6b9dbe47798805992f0d9ec26b777a5c2e1eeb  src/lib/errorUtils.test.ts
43e9582b6ddf1d671f072495d24fa081649be6362fdfb75a1e6e2fac53124ebb  src/lib/passwordPolicy.ts
b5ccc79c70a6ba47524013464802c9ad08c25cc494d35a03d787642dc097ddc4  src/lib/passwordPolicy.test.ts
49fe528d1f80f504d691f6d257406c9714f433125e48135e20094061a3cbaf0c  package.json
d16285617369a47283165520488798990e829cd9c261a98bb39c9a1006fe27b8  package-lock.json
```

## 构建与测试
```bash
npm test
# 结果：2 passed (11 tests)

npm run build
# 结果：tsc -b 零 TypeScript 错误，vite build 成功
```

## 交付 Gate
- 成功 Gate：`P33V_AUTH_REGISTRATION_LOGIN_ADMIN_COMPLETE`
- 本轮修复 Gate：`P33V_A1_PASSWORD_CHANGE_UX_REPAIR_COMPLETE`
