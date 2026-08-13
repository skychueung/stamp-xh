#!/bin/bash
# =============================================================================
# STAMP /home/xh 文件迁移 —— DRY RUN 脚本
# 服务器：stamp218
# 生成时间：2026-06-02
# 原则：只 echo，不执行真实移动，不删除任何文件
# =============================================================================

set -euo pipefail

# 基础路径
HOME_DIR="/home/xh/kxc/stampup"
TARGET_BASE="/home/xh/kxc/stampup"
STAMP_PROJECT="${TARGET_BASE}/stamp-targeted-peptide-platform-target-design-dev"
BACKUP_DIR="${TARGET_BASE}/backups"
ARCHIVE_DIR="${TARGET_BASE}/backups/archived-home-files"

# 目标子目录
LOGS_DIR="${STAMP_PROJECT}/logs"
REPORTS_DIR="${STAMP_PROJECT}/reports"
DOCS_OPS_DIR="${STAMP_PROJECT}/docs/operations"
SCRIPTS_OPS_DIR="${STAMP_PROJECT}/scripts/ops"

echo "=============================================="
echo "STAMP stampup 文件迁移 —— DRY RUN"
echo "=============================================="
echo ""
echo "本脚本仅模拟将要执行的操作，不会移动任何文件。"
echo ""

# ---------------------------------------------------------------------------
# A 类：明确属于 STAMP，建议迁移
# ---------------------------------------------------------------------------

echo "========== A 类：明确可迁移文件 =========="
echo ""

# 1. stamp_check_logs 目录
echo "[DRY-RUN] mv ${HOME_DIR}/stamp_check_logs ${LOGS_DIR}/stamp_check_logs"

# 2. stamp_backup 目录
echo "[DRY-RUN] mv ${HOME_DIR}/stamp_backup_20260512_181319 ${BACKUP_DIR}/stamp_backup_20260512_181319"

# 3. stamp_real 目录
echo "[DRY-RUN] mv ${HOME_DIR}/stamp_real ${BACKUP_DIR}/stamp_real_20260512"

# 4. 部署包
echo "[DRY-RUN] mv ${HOME_DIR}/stamp-v1.4-deploy.tar.gz ${BACKUP_DIR}/stamp-v1.4-deploy.tar.gz"

# 5-28. 根目录下与正式项目同名的 STAMP 文档/脚本/日志（md5 已确认相同或明确归属）
echo "[DRY-RUN] mv ${HOME_DIR}/STAMP_WORKFLOW_AUDIT_v0.6d-P1c.md ${DOCS_OPS_DIR}/STAMP_WORKFLOW_AUDIT_v0.6d-P1c.md"
echo "[DRY-RUN] mv ${HOME_DIR}/stamp_demo_one.json ${DOCS_OPS_DIR}/stamp_demo_one.json"
echo "[DRY-RUN] mv ${HOME_DIR}/vite-dev-server.log ${LOGS_DIR}/vite-dev-server.log"
echo "[DRY-RUN] mv ${HOME_DIR}/vite-dev-server2.log ${LOGS_DIR}/vite-dev-server2.log"
echo "[DRY-RUN] mv ${HOME_DIR}/uvicorn.pid ${LOGS_DIR}/uvicorn.pid"
echo "[DRY-RUN] mv ${HOME_DIR}/DEPLOY_v1.4.sh ${SCRIPTS_OPS_DIR}/DEPLOY_v1.4.sh"
echo "[DRY-RUN] mv ${HOME_DIR}/DEPLOY_v0.6d-P1c_REPORT.md ${REPORTS_DIR}/DEPLOY_v0.6d-P1c_REPORT.md"
echo "[DRY-RUN] mv ${HOME_DIR}/CHANGELOG.md ${DOCS_OPS_DIR}/CHANGELOG.md"
echo "[DRY-RUN] mv ${HOME_DIR}/SEAL_v0.6d-P1c_FINAL.md ${REPORTS_DIR}/SEAL_v0.6d-P1c_FINAL.md"
echo "[DRY-RUN] mv ${HOME_DIR}/SEAL_v0.6d-P1c_REPORT.md ${REPORTS_DIR}/SEAL_v0.6d-P1c_REPORT.md"
echo "[DRY-RUN] mv ${HOME_DIR}/SOFT_RESTORE_REPORT.md ${REPORTS_DIR}/SOFT_RESTORE_REPORT.md"
echo "[DRY-RUN] mv ${HOME_DIR}/SOFT_RESTORE_v0.6d-P2a_DEMO_DEFAULT.md ${REPORTS_DIR}/SOFT_RESTORE_v0.6d-P2a_DEMO_DEFAULT.md"
echo "[DRY-RUN] mv ${HOME_DIR}/STRUCTURE_PIPELINE.md ${DOCS_OPS_DIR}/STRUCTURE_PIPELINE.md"
echo "[DRY-RUN] mv ${HOME_DIR}/TODO.md ${DOCS_OPS_DIR}/TODO.md"
echo "[DRY-RUN] mv ${HOME_DIR}/v0.7-P1a_EPITOPE_PARAMETER_AND_FLOW_REPORT.md ${REPORTS_DIR}/v0.7-P1a_EPITOPE_PARAMETER_AND_FLOW_REPORT.md"
echo "[DRY-RUN] mv ${HOME_DIR}/v0.7-real-backend-integration_REPORT.md ${REPORTS_DIR}/v0.7-real-backend-integration_REPORT.md"
echo "[DRY-RUN] mv ${HOME_DIR}/PROJECT_CONTEXT.md ${DOCS_OPS_DIR}/PROJECT_CONTEXT.md"
echo "[DRY-RUN] mv ${HOME_DIR}/README.md ${DOCS_OPS_DIR}/README_HOME.md"
echo "[DRY-RUN] mv ${HOME_DIR}/RUNBOOK.md ${DOCS_OPS_DIR}/RUNBOOK_HOME.md"
echo "[DRY-RUN] mv ${HOME_DIR}/info.md ${DOCS_OPS_DIR}/info_HOME.md"
echo "[DRY-RUN] mv ${HOME_DIR}/FINAL_REPORT_v1.4.md ${REPORTS_DIR}/FINAL_REPORT_v1.4.md"
echo "[DRY-RUN] mv ${HOME_DIR}/DEV_RULES.md ${DOCS_OPS_DIR}/DEV_RULES.md"
echo "[DRY-RUN] mv ${HOME_DIR}/DISPLAYABLE_SEQUENCES_v0.6d-P1c.md ${DOCS_OPS_DIR}/DISPLAYABLE_SEQUENCES_v0.6d-P1c.md"
echo "[DRY-RUN] mv ${HOME_DIR}/PEPMLM_GPU_GENERATION_REPORT.md ${REPORTS_DIR}/PEPMLM_GPU_GENERATION_REPORT.md"

# 29-34. stampup 子目录副本
echo "[DRY-RUN] mv ${HOME_DIR}/backend ${ARCHIVE_DIR}/backend"
echo "[DRY-RUN] mv ${HOME_DIR}/docs ${ARCHIVE_DIR}/docs"
echo "[DRY-RUN] mv ${HOME_DIR}/scripts ${ARCHIVE_DIR}/scripts"
echo "[DRY-RUN] mv ${HOME_DIR}/src ${ARCHIVE_DIR}/src"
echo "[DRY-RUN] mv ${HOME_DIR}/data ${ARCHIVE_DIR}/data"
echo "[DRY-RUN] mv ${HOME_DIR}/public ${ARCHIVE_DIR}/public"

echo ""

# ---------------------------------------------------------------------------
# B 类：疑似属于 STAMP，需人工确认（全部注释掉）
# ---------------------------------------------------------------------------

echo "========== B 类：疑似 STAMP，需人工确认（已注释） =========="
echo ""
echo "# [DRY-RUN-SKIPPED] 以下为疑似文件，需人工确认后再决定是否迁移："
echo "# mv ${HOME_DIR}/gen_gpu0.log ${LOGS_DIR}/gen_gpu0.log"
echo "# mv ${HOME_DIR}/gen_gpu1.log ${LOGS_DIR}/gen_gpu1.log"
echo "# mv ${HOME_DIR}/gmx_MMPBSA.log ${LOGS_DIR}/gmx_MMPBSA.log"
echo "# mv ${HOME_DIR}/gpu_smoke_condarun.log ${LOGS_DIR}/gpu_smoke_condarun.log"
echo "# mv ${HOME_DIR}/P6B_PARSE_OUTPUT_RUN_2.log ${LOGS_DIR}/P6B_PARSE_OUTPUT_RUN_2.log"
echo "# mv ${HOME_DIR}/P6B_RUN_COLABFOLD_SMOKE_RUN_2.log ${LOGS_DIR}/P6B_RUN_COLABFOLD_SMOKE_RUN_2.log"
echo "# mv ${HOME_DIR}/ROSETTA_CRASH.log ${LOGS_DIR}/ROSETTA_CRASH.log"

echo ""

# ---------------------------------------------------------------------------
# D 类 / E 类：不迁移（仅列出以作记录）
# ---------------------------------------------------------------------------

echo "========== D 类 / E 类：明确不迁移 =========="
echo ""
echo "# 系统/环境文件（D类）：.ssh .bashrc .conda miniconda3 .cache .vscode-server .npm ..."
echo "# 非 STAMP 项目（E类）：ww/ yjj/ zhr/ zy/ lkf/ webui.log molecules/ rag_storage/ ..."
echo "# 已在正确位置（C类）：/home/xh/stamp 软链接、stamp-targeted-peptide-platform/ 全部内容"

echo ""
echo "=============================================="
echo "DRY RUN 完成。未执行任何真实文件移动。"
echo "=============================================="
