# STAMP 开发入口登录/注册收口报告

- 日期：2026-07-08
- Gate：`P33_AUTH_ENTRY_LOGIN_REGISTER_READY`
- 开发地址：`http://100.75.69.36:12823/`（实验室局域网对应 `http://192.168.31.218:12823/`）
- 开发副本：`/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev`

## 完成内容

1. 未登录访问根路由 `/` 时跳转到 `/login`。
2. 登录页保留主操作 `Log in`，并把原文字注册链接改为等宽可见按钮 `Register`。
3. 已登录用户访问 `/` 时继续进入原有 STAMP 首页，不形成登录重定向循环。
4. 注册流程仍为“提交后等待管理员审批”，未改变后端认证策略。

## 修改文件

- `src/App.tsx`
  - 修改后 SHA256：`b655c8ba7c1f6b7cb865d26edfcdeeae409a87a0de3ea652007a840a43c4846e`
- `src/pages/LoginPage.tsx`
  - 修改后 SHA256：`5df0cfdc47fbe341c2b6a6714b6df4a72904d412fab0101c734fc4d17ae2323a`

## 回滚

- 服务器备份：`/home/xh/kxc/stampup/backups/p33_auth_entry_20260708_192811/`
- 原 `src/App.tsx` SHA256：`4db1ce551c098a488706049d6f1bdd97e5a42a5d01da3fc495606af6c52fd3ec`
- 原 `src/pages/LoginPage.tsx` SHA256：`cf9c41236dfbf023c3d2a193b8196e333f79388bfa43247f14ed18a4cefb1d73`

## 验证

- `npm run build`：PASS（TypeScript/Vite 构建成功）。
- 开发前端 `12823`：已重启，PID `3375152`，加载新 bundle `index-DgqEs2Au.js`。
- 未登录认证探针：前端代理和后端直连均返回 `401 {"detail":"Not authenticated."}`，符合预期。
- 新 bundle 标记：`/login` 7 处、`/register` 4 处、`Register` 39 处。
- 后端认证测试：9 passed / 1 failed；唯一失败为测试预设管理员 `kxc` 密码与当前环境不一致，注册接口测试通过。本次未修改管理员密码或后端认证代码。
- 浏览器截图级验收：未执行；Codex 浏览器插件缺少其声明的运行脚本。本报告不冒充视觉验收。

## 边界

- 仅修改开发副本前端两个文件并重启 `12823`。
- 未修改或重启开发后端 `12824`。
- 未修改或重启正式环境 `8001/8080`，未触碰 `/home/xh/stamp`。
- 未运行模型、未加载 checkpoint、未使用 GPU。
