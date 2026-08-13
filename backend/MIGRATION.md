# STAMP Platform — Database Migration Guide (Alembic)

## 概述

本项目使用 **Alembic** + **SQLAlchemy 2.0** 管理 SQLite 数据库迁移。

- 所有表结构变更通过 migration 脚本追踪
- 现有生产数据不会丢失
- 支持升级 (upgrade) 与回滚 (downgrade)

## 目录结构

```
backend/
├── alembic/                    # Alembic 工作目录
│   ├── env.py                  # 环境配置（自动加载 app.models）
│   ├── script.py.mako          # 迁移脚本模板
│   ├── versions/               # 迁移脚本存放区
│   │   └── 2026_05_13_0218-fce11772abec_baseline_init.py
│   └── README
├── alembic.ini                 # Alembic 主配置
├── scripts/backup_db.py        # 数据库备份脚本
└── tests/test_migrations.py    # 迁移冒烟测试
```

## 快速命令

```bash
# 查看当前版本历史
alembic history

# 查看当前数据库版本
alembic current

# 自动根据 Model 变更生成迁移脚本
alembic revision --autogenerate -m "add_new_table"

# 执行升级到最新版本
alembic upgrade head

# 回滚一个版本
alembic downgrade -1

# 回滚到基线（清空所有表）
alembic downgrade base
```

> **Windows 环境**：请使用 `venv\Scripts\alembic.exe` 或 `python -m alembic`。

## 备份数据库（必须先备份再迁移）

```bash
python scripts/backup_db.py
```

默认保留最近 **10** 份备份，旧备份自动清理。

自定义参数：
```bash
python scripts/backup_db.py --db-path app/stamp_p5_lite.db --output-dir data/db_backups --keep 20
```

## 首次接入已有数据库（Baseline）

现有数据库已通过 `alembic stamp head` 标记为基线，后续新增 migration 会在此基础上递增，不会重复创建已有表。

如果在新环境从零部署：
```bash
alembic upgrade head
```
这会自动创建所有表（等同于以前的 `init_db()`）。

## 新增 Migration 的标准流程

1. **修改 `app/models/orm.py`** 中的模型定义
2. **生成迁移脚本**：
   ```bash
   alembic revision --autogenerate -m "描述本次变更"
   ```
3. **人工审查生成的脚本**（`alembic/versions/` 下最新文件），确认无误
4. **备份数据库**：
   ```bash
   python scripts/backup_db.py
   ```
5. **执行迁移**：
   ```bash
   alembic upgrade head
   ```
6. **运行冒烟测试**：
   ```bash
   pytest tests/test_migrations.py -v
   ```

## 回滚方式

### 回滚到上一个版本
```bash
alembic downgrade -1
```

### 回滚到指定版本
```bash
alembic downgrade fce11772abec
```

### 灾难恢复（从备份还原）
```bash
# 1. 停止后端服务
# 2. 找到最近的备份
ls data/db_backups/
# 3. 替换当前数据库
cp data/db_backups/stamp_p5_lite_backup_20260513_021800.db app/stamp_p5_lite.db
# 4. 重新 stamp 版本（如果备份是在 baseline 之前创建的，则不需要）
alembic stamp head
```

> **注意**：SQLite 的 `downgrade` 会删除表/列，如果该列含有数据，数据会丢失。因此生产环境降级前务必先运行 `backup_db.py`。

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `STAMP_DATABASE_URL` | 数据库连接 URL | `sqlite:///{backend}/app/stamp_p5_lite.db` |

Alembic 会自动读取 `STAMP_DATABASE_URL`，与 `app.database` 保持一致。

## 与旧版 `_migrate_sqlite_columns()` 的关系

原有的 `database.py::_migrate_sqlite_columns()` 是轻量快速补丁，用于 v1.2 之前的字段补齐。

**现在已被 Alembic 取代**：
- 新增字段 → 写 migration 脚本
- 修改字段类型 → 写 migration 脚本
- `_migrate_sqlite_columns()` 保留为兼容代码，但后续不再扩展

## 冒烟测试

```bash
pytest tests/test_migrations.py -v
```

测试覆盖：
- Alembic 配置完整性
- 空数据库 upgrade / downgrade 往返
- 升级后所有预期表存在
- 备份脚本生成有效文件
