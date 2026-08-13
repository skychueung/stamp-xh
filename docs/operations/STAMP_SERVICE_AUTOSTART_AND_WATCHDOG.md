# STAMP 服务自启动与 Watchdog 运维手册

> 历史记录说明：本文主要描述正式环境的自启动和 watchdog 方案，不作为 STAMPUP 开发副本默认入口。
>
> STAMPUP 开发副本请优先使用：
>
> - `bash scripts/ops/stampup_start_backend.sh`
> - `bash scripts/ops/stampup_start_frontend.sh`
> - `bash scripts/ops/stampup_status.sh`
> - `bash scripts/ops/stampup_healthcheck.sh`
> - `bash scripts/ops/stampup_restart.sh`
> - `bash scripts/ops/stampup_stop.sh`

## 服务地址

| 服务 | 地址 |
|------|------|
| 前端 | http://192.168.31.218:8080/ |
| Pipeline | http://192.168.31.218:8080/pipeline |
| 后端 API | http://192.168.31.218:8001/api/health |

## 架构说明

- **后端**：裸 uvicorn 进程，`@reboot` cron 开机自启，watchdog 异常自愈
- **前端**：nginx docker 容器，`--restart unless-stopped`，Docker 守护进程自动重启
- **Watchdog**：cron 每 3 分钟检查，异常时自动重启

## 关键路径

| 项目 | 路径 |
|------|------|
| 项目根 | `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform` |
| 符号链接 | `/home/xh/stamp` |
| Watchdog 脚本 | `scripts/ops/stamp_watchdog.sh` |
| Status 脚本 | `scripts/ops/stamp_status.sh` |
| 后端启动脚本 | `scripts/ops/start_backend.sh` |
| Watchdog 日志 | `/home/xh/stamp/logs/stamp_watchdog.log` |
| 后端日志 | `/home/xh/stamp/logs/backend.log` |
| 前端容器名 | `stamp-frontend` |

## STAMPUP 开发副本

开发副本统一目录：

`/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev`

开发副本日志 / 报告目录：

- `logs_dev`
- `reports`

开发副本推荐入口：

- `scripts/ops/stampup_start_backend.sh`
- `scripts/ops/stampup_start_frontend.sh`
- `scripts/ops/stampup_status.sh`
- `scripts/ops/stampup_healthcheck.sh`
- `scripts/ops/stampup_restart.sh`
- `scripts/ops/stampup_stop.sh`

## 常用命令

```bash
# 状态总览
bash /home/xh/stamp/scripts/ops/stamp_status.sh

# 查看 watchdog 日志
tail -n 100 /home/xh/stamp/logs/stamp_watchdog.log

# 查看后端日志
tail -n 100 /home/xh/stamp/logs/backend.log

# 手动重启后端
pkill -f 'uvicorn app.main:app --host 0.0.0.0 --port 8001'
bash /home/xh/stamp/scripts/ops/start_backend.sh

# 查看前端容器
docker ps | grep stamp-frontend
docker logs --tail 100 stamp-frontend

# 手动重启前端
docker restart stamp-frontend

# 查看 crontab
crontab -l

# 手动运行 watchdog
bash /home/xh/stamp/scripts/ops/stamp_watchdog.sh
```

## Cron 配置

```
*/3 * * * *  watchdog 每 3 分钟健康检查
@reboot      开机自启后端 uvicorn
```

## 故障排查

| 症状 | 排查步骤 |
|------|----------|
| 后端 8001 无响应 | `ps aux \| grep uvicorn`，无进程则手动 `bash start_backend.sh` |
| 前端 8080 无响应 | `docker ps \| grep stamp-frontend`，无则 `docker start stamp-frontend` |
| /pipeline 404 | 确认容器是 nginx（非 python http.server），检查 nginx-spa.conf |
| Watchdog 不触发 | `crontab -l` 确认任务存在，检查 `/tmp/stamp_watchdog_cooldown` |
| 磁盘满 | `df -h /home/xh`，清理 logs 或旧文件 |

## 注意事项

- sudo 无免密，systemd system 级服务不可用，改用 cron @reboot
- 磁盘使用率 95%，需关注
- 不要删除 data/ dist/ 模型文件
