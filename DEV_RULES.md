# Peptide Frontend — 开发规则

> 硬性约束清单。任何代码修改前，先通读本文件。

---

## 一、接口与功能保护

1. **不得破坏 `/api/predict`**
   - `src/lib/api.ts` 中的 `runPrediction()` 函数是核心数据通道
   - 禁止修改其入参结构、出参映射逻辑、HTTP 方法或 URL 路径
   - 如需扩展，新建函数，不得覆盖原有逻辑

2. **不得删除 `/filter` 和 `/demo`**
   - `src/App.tsx` 中必须保留这两条路由，且均指向 `PeptideFilterPage`
   - 旧功能页是团队日常使用的生产页面，不可下线

3. **旧功能页必须保留**
   - `PeptideFilterPage` 及其引用的所有子组件（`SiteHeader`、`HeroSection`、`InputConsolePanel`、`ResultsPanel`、`PipelineSection`、`ResultsSnapshotSection`、`CandidateDetailDrawer`、`CandidateCompareDrawer`、`ErrorBanner`、`ApiWarmupBanner`、`LoadingOverlay`、`SiteFooter`）不得删除或重命名
   - 允许样式微调，但禁止功能删减

---

## 二、术语与品牌规范

4. **新页面不得出现 AMP，统一使用 STAMP**
   - 所有新增文案、路由、变量名、注释中，使用 `STAMP` 替代 `AMP`
   - 旧页面中的 AMP 引用可保留，但不得扩散到新页面

5. **主色必须为 `#156B98`**
   - 平台品牌色为湘湖蓝 `#156B98`
   - 新增组件、样式、图表配色必须以该色为主色
   - Tailwind 自定义颜色名：`xh-primary`（已在 `tailwind.config.js` 配置）

---

## 三、代码质量

6. **不得使用 `any`**
   - 全项目开启严格 TypeScript，禁止 `any` 类型
   - 未知类型使用 `unknown` + 类型守卫，或补充 `interface`/`type`
   - 现有代码中的 `any` 应逐步替换，新增代码零容忍

7. **`npm run build` 必须通过**
   - 每次提交前必须执行 `npm run build`，零报错、零警告
   - TypeScript 类型错误、ESLint 错误、Vite 构建错误均视为阻塞项
   - CI（如有）以构建成功为合并门槛

---

## 四、修改前必读

8. **修改前先读以下三个文件**
   - `src/lib/api.ts` — 理解后端接口契约
   - `src/App.tsx` — 理解路由结构，避免路由冲突
   - `src/pages/PeptideFilterPage.tsx` — 理解旧页面组件依赖，避免误删

---

## 五、历史会话检索

9. **遇到重复报错、历史方案、路径问题、Hermes / Kimi / Codex 配置问题时，优先使用 CASS 搜索历史记录**
   - CASS (Context-Aware Session Search) 是本地 AI 项目的记忆检索层
   - 安装路径：`D:\ai\product\cass`
   - 数据目录：`D:\ai\product\cass\data`
   - 索引范围：Kimi Code (`C:\Users\33319\.kimi\sessions`) + Codex (`C:\Users\33319\.codex\sessions`)
   - 常用命令：
     ```powershell
     $env:CASS_DATA_DIR="D:\ai\product\cass\data"
     cass search "关键词" --robot --limit 10
     cass index          # 增量索引
     cass doctor --fix   # 诊断修复
     ```
   - 当前索引：30 conversations / 2,042 messages

---

## 六、新增页面 checklist

新增页面或路由时，依次确认：

- [ ] 路由在 `App.tsx` 中注册，不覆盖已有路由
- [ ] 未使用 `AMP`，已替换为 `STAMP`
- [ ] 主色使用 `#156B98` 或 `xh-primary`
- [ ] 无 `any` 类型
- [ ] `npm run build` 通过
- [ ] 旧页面（`/filter`、`/demo`）仍可正常访问
- [ ] `/api/predict` 调用正常

---

*最后更新：2026-04-27*
