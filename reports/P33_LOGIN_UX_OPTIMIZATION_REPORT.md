# STAMP 开发登录页 UX 优化报告

- 日期：2026-07-08
- Gate：`P33_LOGIN_UX_OPTIMIZATION_READY_BROWSER_VISUAL_CONFIRMATION_PENDING`
- 开发副本：`/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev`
- 开发入口：`http://192.168.31.218:12823/` / `http://100.75.69.36:12823/`

## 修改范围

实际只修改或新增以下三个前端文件：

| 文件 | 类型 | SHA256 |
|---|---|---|
| `src/pages/LoginPage.tsx` | 修改 | `a3701df59cd0ec39559edf17fdfd5f106f1b6fb8a0c93b048bacbdbf9b54d9cf` |
| `src/lib/loginForm.ts` | 新增 | `3aaced80a1a1365b7f41d89083c6a0cd1b41385b9a0733a591394866ad361630` |
| `src/lib/loginForm.test.ts` | 新增 | `13e1f588719051832688554c346dd2d14e7ab1e39adf87c7e1b3ec66eb2bcbed` |

未修改 `src/App.tsx`、`src/contexts/AuthContext.tsx`、全局样式、公共 UI 组件、后端或数据库。

## 备份与回退

- 备份目录：`/home/xh/kxc/stampup/backups/p33_login_ux_20260708_195734/`
- 原文件：`src/pages/LoginPage.tsx`
- 原 SHA256：`5df0cfdc47fbe341c2b6a6714b6df4a72904d412fab0101c734fc4d17ae2323a`
- 两个新增文件在实施前均不存在。

回退方法：先再次备份当前三个文件，然后将备份中的 `src/pages/LoginPage.tsx` 复制回开发副本，并删除本任务新增的 `src/lib/loginForm.ts`、`src/lib/loginForm.test.ts`，重新执行 `npm run build`，最后只重启 12823。禁止对仓库执行 reset/checkout/clean。

## 关键改动

- 新增 STAMP Platform / Targeted Peptide Design Platform 品牌区、浅灰蓝科技背景、460px 响应式卡片和移动端安全间距。
- 默认不渲染错误框；用户名或密码变化时清除旧错误。
- 用户名 autofocus；表单 `onSubmit` 支持 Enter。
- 空用户名、空密码使用指定前端提示，提交前不调用后端。
- 登录逻辑使用 `try/catch/finally`；loading 时禁用 fieldset 和提交按钮，并显示旋转图标与 `Signing in...`。
- 增加密码显示/隐藏按钮及 `aria-label` / `aria-pressed`。
- Remember me 只在成功登录后保存用户名到 localStorage，不保存密码；localStorage 异常不影响登录。
- 注册入口保留为次要 outline 按钮，继续跳转 `/register`。
- 新增纯函数处理表单校验和登录错误映射，区分错误凭据、待审批、禁用、锁定、网络和未知错误。

## 测试与构建

- `npm test -- src/lib/loginForm.test.ts`：PASS，1 file / 9 tests。
- 定向 ESLint（三个允许文件）：PASS，0 error。
- `npm run build`：PASS，TypeScript 与 Vite 构建成功。
- 当前 live bundle：`/assets/index-ClX-4InM.js`；CSS：`/assets/index-BdXsB0AI.css`。
- live bundle 已检出品牌、标题、Remember me、注册入口、loading 和友好错误文案。
- 正确管理员登录经 12823 代理实际返回 HTTP 200，用户 `kxc`、角色 `admin`、状态 `active`。
- 未登录 `/api/v1/auth/me` 经 12823 返回预期 401。

## 端口边界

- 仅重启 12823：新 PID `3434771`。
- 12824 未重启：PID `827879` 保持不变。
- 正式 8001 未重启：PID `3074240` 保持不变。
- 正式 8080 监听保持不变。

## 风险与验收缺口

- Codex 应用内浏览器对局域网 URL 的安全策略阻止 DOM、点击和截图访问；未使用其他浏览器工具绕过。因此桌面/移动截图级视觉验收、显示密码按钮点击、错误后输入清除和 Register 点击仍需用户在已打开的页面手工确认。
- 逻辑对应的纯函数测试、TypeScript build、live bundle、HTTP 认证和路由字符串均已验证。
- 构建仍有项目既存警告：服务器 Node.js 18.19.1 低于 Vite 建议版本，及既有大 chunk / h264-mp4-encoder 浏览器兼容警告；本次构建成功，未扩大范围升级运行时或依赖。
