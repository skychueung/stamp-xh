#!/bin/bash
# =============================================================================
# STAMP /home/xh 文件迁移 —— 正式执行脚本
# 服务器：stamp218
# 执行时间：2026-06-02
# 原则：只迁移 stampup 内部文件，不删除 B 类，不破坏服务
# =============================================================================

set -euo pipefail

# 基础路径
HOME_DIR="/home/xh/kxc/stampup"
ARCHIVE_BASE="/home/xh/kxc/stampup/backups/archived-home-files/stamp_related_20260602"
MANIFEST_FILE="${ARCHIVE_BASE}/manifest/relocation_manifest.tsv"

# 计数器
MIGRATED_COUNT=0
SKIPPED_COUNT=0
ERROR_COUNT=0

# 初始化 manifest
echo -e "timestamp\tsource_path\ttarget_path\tstatus\titem_type\tbytes" > "$MANIFEST_FILE"

log_manifest() {
    local src="$1"
    local tgt="$2"
    local status="$3"
    local itype="$4"
    local bytes="${5:-0}"
    local ts
    ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${ts}\t${src}\t${tgt}\t${status}\t${itype}\t${bytes}" >> "$MANIFEST_FILE"
}

migrate_dir() {
    local src="$1"
    local tgt="$2"
    if [ -d "$src" ]; then
        local bytes
        bytes=$(du -sb "$src" | awk '{print $1}')
        mv "$src" "$tgt"
        log_manifest "$src" "$tgt" "MIGRATED" "dir" "$bytes"
        ((MIGRATED_COUNT++)) || true
        echo "[OK] Migrated dir: $src -> $tgt"
    else
        log_manifest "$src" "$tgt" "SKIPPED_NOT_FOUND" "dir" "0"
        ((SKIPPED_COUNT++)) || true
        echo "[SKIP] Source not found: $src"
    fi
}

migrate_file() {
    local src="$1"
    local tgt="$2"
    if [ -f "$src" ]; then
        local bytes
        bytes=$(stat -c%s "$src" 2>/dev/null || echo 0)
        mv "$src" "$tgt"
        log_manifest "$src" "$tgt" "MIGRATED" "file" "$bytes"
        ((MIGRATED_COUNT++)) || true
        echo "[OK] Migrated file: $src -> $tgt"
    else
        log_manifest "$src" "$tgt" "SKIPPED_NOT_FOUND" "file" "0"
        ((SKIPPED_COUNT++)) || true
        echo "[SKIP] Source not found: $src"
    fi
}

echo "=============================================="
echo "STAMP stampup 文件迁移 —— 正式执行"
echo "=============================================="
echo ""
echo "归档根目录: $ARCHIVE_BASE"
echo "Manifest:   $MANIFEST_FILE"
echo ""

# ---------------------------------------------------------------------------
# A 类：明确属于 stampup，执行迁移
# ---------------------------------------------------------------------------

echo "========== 开始迁移 A 类文件/目录 =========="
echo ""

# 目录迁移
migrate_dir "${HOME_DIR}/stamp_check_logs" "${ARCHIVE_BASE}/logs/stamp_check_logs"
migrate_dir "${HOME_DIR}/stamp_backup_20260512_181319" "${ARCHIVE_BASE}/old_project_copies/stamp_backup_20260512_181319"
migrate_dir "${HOME_DIR}/stamp_real" "${ARCHIVE_BASE}/old_project_copies/stamp_real"
migrate_dir "${HOME_DIR}/backend" "${ARCHIVE_BASE}/old_project_copies/backend"
migrate_dir "${HOME_DIR}/docs" "${ARCHIVE_BASE}/old_project_copies/docs"
migrate_dir "${HOME_DIR}/scripts" "${ARCHIVE_BASE}/old_project_copies/scripts"
migrate_dir "${HOME_DIR}/src" "${ARCHIVE_BASE}/old_project_copies/src"
migrate_dir "${HOME_DIR}/data" "${ARCHIVE_BASE}/old_project_copies/data"
migrate_dir "${HOME_DIR}/public" "${ARCHIVE_BASE}/old_project_copies/public"

# 文件迁移
migrate_file "${HOME_DIR}/stamp-v1.4-deploy.tar.gz" "${ARCHIVE_BASE}/old_project_copies/stamp-v1.4-deploy.tar.gz"
migrate_file "${HOME_DIR}/STAMP_WORKFLOW_AUDIT_v0.6d-P1c.md" "${ARCHIVE_BASE}/reports/STAMP_WORKFLOW_AUDIT_v0.6d-P1c.md"
migrate_file "${HOME_DIR}/stamp_demo_one.json" "${ARCHIVE_BASE}/json/stamp_demo_one.json"
migrate_file "${HOME_DIR}/vite-dev-server.log" "${ARCHIVE_BASE}/logs/vite-dev-server.log"
migrate_file "${HOME_DIR}/vite-dev-server2.log" "${ARCHIVE_BASE}/logs/vite-dev-server2.log"
migrate_file "${HOME_DIR}/uvicorn.pid" "${ARCHIVE_BASE}/logs/uvicorn.pid"
migrate_file "${HOME_DIR}/DEPLOY_v1.4.sh" "${ARCHIVE_BASE}/scripts/DEPLOY_v1.4.sh"
migrate_file "${HOME_DIR}/DEPLOY_v0.6d-P1c_REPORT.md" "${ARCHIVE_BASE}/reports/DEPLOY_v0.6d-P1c_REPORT.md"
migrate_file "${HOME_DIR}/CHANGELOG.md" "${ARCHIVE_BASE}/reports/CHANGELOG.md"
migrate_file "${HOME_DIR}/SEAL_v0.6d-P1c_FINAL.md" "${ARCHIVE_BASE}/reports/SEAL_v0.6d-P1c_FINAL.md"
migrate_file "${HOME_DIR}/SEAL_v0.6d-P1c_REPORT.md" "${ARCHIVE_BASE}/reports/SEAL_v0.6d-P1c_REPORT.md"
migrate_file "${HOME_DIR}/SOFT_RESTORE_REPORT.md" "${ARCHIVE_BASE}/reports/SOFT_RESTORE_REPORT.md"
migrate_file "${HOME_DIR}/SOFT_RESTORE_v0.6d-P2a_DEMO_DEFAULT.md" "${ARCHIVE_BASE}/reports/SOFT_RESTORE_v0.6d-P2a_DEMO_DEFAULT.md"
migrate_file "${HOME_DIR}/STRUCTURE_PIPELINE.md" "${ARCHIVE_BASE}/reports/STRUCTURE_PIPELINE.md"
migrate_file "${HOME_DIR}/TODO.md" "${ARCHIVE_BASE}/reports/TODO.md"
migrate_file "${HOME_DIR}/v0.7-P1a_EPITOPE_PARAMETER_AND_FLOW_REPORT.md" "${ARCHIVE_BASE}/reports/v0.7-P1a_EPITOPE_PARAMETER_AND_FLOW_REPORT.md"
migrate_file "${HOME_DIR}/v0.7-real-backend-integration_REPORT.md" "${ARCHIVE_BASE}/reports/v0.7-real-backend-integration_REPORT.md"
migrate_file "${HOME_DIR}/PROJECT_CONTEXT.md" "${ARCHIVE_BASE}/reports/PROJECT_CONTEXT.md"
migrate_file "${HOME_DIR}/README.md" "${ARCHIVE_BASE}/reports/README_HOME.md"
migrate_file "${HOME_DIR}/RUNBOOK.md" "${ARCHIVE_BASE}/reports/RUNBOOK_HOME.md"
migrate_file "${HOME_DIR}/info.md" "${ARCHIVE_BASE}/reports/info_HOME.md"
migrate_file "${HOME_DIR}/FINAL_REPORT_v1.4.md" "${ARCHIVE_BASE}/reports/FINAL_REPORT_v1.4.md"
migrate_file "${HOME_DIR}/DEV_RULES.md" "${ARCHIVE_BASE}/reports/DEV_RULES.md"
migrate_file "${HOME_DIR}/DISPLAYABLE_SEQUENCES_v0.6d-P1c.md" "${ARCHIVE_BASE}/reports/DISPLAYABLE_SEQUENCES_v0.6d-P1c.md"
migrate_file "${HOME_DIR}/PEPMLM_GPU_GENERATION_REPORT.md" "${ARCHIVE_BASE}/reports/PEPMLM_GPU_GENERATION_REPORT.md"

echo ""
echo "=============================================="
echo "迁移统计"
echo "=============================================="
echo "成功迁移: $MIGRATED_COUNT"
echo "跳过/未找到: $SKIPPED_COUNT"
echo "错误: $ERROR_COUNT"
echo "Manifest: $MANIFEST_FILE"
echo "=============================================="
