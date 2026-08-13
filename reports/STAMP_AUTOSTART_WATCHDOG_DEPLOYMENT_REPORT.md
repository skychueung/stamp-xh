# STAMP 自启动与 Watchdog 部署报告

**时间**：2026-06-01 23:40  
**执行机器**：lekang (Windows 11, D:\ai\project)  
**目标服务器**：stamp218 (xh@192.168.31.218)

---

## 一、现状对账（部署前）

| 项目 | 状态 |
|------|------|
| 前端 8080 | ✅ 在线（但为 `python3 -m http.server`，无 SPA fallback） |
| 后端 8001 | ✅ 在线（裸 uvicorn 进程，pid=2698330） |
| /pipeline | ❌ 404（http.server 不支持 SPA fallback） |
| 前端容器 | ❌ 无 nginx docker，用 python http.server 代替 |
| systemd service | ❌ 无 stamp-backend.service |
| crontab | ❌ 空 |
| watchdog | ❌ 无 |

---

## 二、后端自启动方案

**原计划**：创建 `/etc/systemd/system/stamp-backend.service`  
**实际情况**：`xh` 用户无 sudo 免密，无法写 `/etc/systemd/system/`  
**改用方案**：cron `@reboot` 开机自启 + watchdog 异常自愈

### 后端启动脚本

路径：`scripts/ops/start_backend.sh`

```bash
cd /home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/backend
nohup /usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 \
  >> /home/xh/stamp/logs/backend.log 2>&1 &
```

### Cron @reboot

```
@reboot /bin/bash /home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/scripts/ops/start_backend.sh
```

---

## 三、前端 nginx 容器

**变更**：停止 `python3 -m http.server 8080`，改用 nginx docker

| 项目 | 值 |
|------|-----|
| 容器名 | `stamp-frontend` |
| 镜像 | `nginx:latest`（服务器本地已有） |
| Restart Policy | `unless-stopped` |
| 挂载 dist | `/home/xh/stamp/dist:/usr/share/nginx/html:ro` |
| 挂载 nginx conf | `/home/xh/stamp/nginx-spa.conf:/etc/nginx/conf.d/default.conf:ro` |
| SPA fallback | ✅ `try_files $uri $uri/ /index.html` |

**效果**：`/pipeline` 从 404 → 200 ✅

---

## 四、Watchdog 脚本

路径：`scripts/ops/stamp_watchdog.sh`  
日志：`/home/xh/stamp/logs/stamp_watchdog.log`

功能：
- 检查 `http://127.0.0.1:8001/api/health`，不健康则 pkill + restart
- 检查 `http://127.0.0.1:8080/pipeline`，不健康则 `docker restart stamp-frontend`
- 10 分钟内连续失败 ≥3 次进入 cooldown，避免疯狂重启
- 每次执行写时间戳日志

---

## 五、Status 脚本

路径：`scripts/ops/stamp_status.sh`

输出：HTTP 状态、uvicorn 进程、docker 容器、磁盘、watchdog 日志

---

## 六、Cron 配置

```
*/3 * * * *  stamp_watchdog.sh   每 3 分钟健康检查
@reboot      start_backend.sh    开机自启后端
```

---

## 七、日志路径

| 日志 | 路径 |
|------|------|
| Watchdog | `/home/xh/stamp/logs/stamp_watchdog.log` |
| 后端 | `/home/xh/stamp/logs/backend.log` |
| 前端 | `docker logs stamp-frontend` |

---

## 八、验收结果

| 验收项 | 结果 |
|--------|------|
| 前端 8080 / → 200 | ✅ |
| 前端 8080 /pipeline → 200 | ✅（修复，原为 404） |
| 后端 8001 /api/health → 200 | ✅ |
| 后端 queue health → 200 | ✅ |
| 后端 resources health → 200 | ✅ |
| 前端 docker restart=unless-stopped | ✅ |
| Watchdog 脚本可运行 | ✅ |
| Cron 每 3 分钟存在 | ✅ |
| @reboot 后端自启 | ✅ |
| Status 脚本可输出 | ✅ |
| dist/ 完整 | ✅ |
| backend/data/ 完整 | ✅ |
| 模型文件 esm2_t33_650M_UR50D.pt 完整 | ✅ (2.5G) |
| systemd stamp-backend.service | ❌ 未创建（sudo 不可用，改用 cron） |

---

## 九、未处理风险

1. **磁盘 95% 满**：`/dev/nvme0n1p2 1.8T 1.7T 88G 95%`，需清理旧日志或文件
2. **sudo 无免密**：systemd system 级服务不可用；如需 systemd，需服务器管理员配置 sudoers
3. **后端无 .env**：`backend/.env` 不存在，当前靠默认配置运行，重启后需确认
4. **@reboot 竞争**：若服务器重启时后端已在运行（其他方式），@reboot 会启动第二个实例；watchdog 的 pkill 会清理，但有短暂双进程窗口

---

## 十、后续建议

1. 联系服务器管理员，为 `xh` 配置最小 sudoers：
   ```
   xh ALL=(ALL) NOPASSWD: /bin/systemctl restart stamp-backend
   ```
   然后迁移到 systemd service，更健壮
2. 清理磁盘，避免 95% 满导致服务异常
3. 创建 `backend/.env`（如有需要）
4. 考虑 `logrotate` 管理 watchdog 和 backend 日志

---

## 十一、Git 状态

服务器仓库有未提交修改（已有 modified 文件），本次新增文件：
- `scripts/ops/stamp_watchdog.sh`
- `scripts/ops/stamp_status.sh`
- `scripts/ops/start_backend.sh`
- `docs/operations/STAMP_SERVICE_AUTOSTART_AND_WATCHDOG.md`

**本次未提交 Git**。如需提交，执行：
```bash
cd /home/xh/kxc/靶向肽/stamp-targeted-peptide-platform
git add scripts/ops/ docs/operations/STAMP_SERVICE_AUTOSTART_AND_WATCHDOG.md
git commit -m "ops: add watchdog, status, start_backend scripts and ops doc"
```
