"""冷藏车管理业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "vehicle"
REQUIRED_FIELDS = ["车牌号码", "车辆类型", "制冷机组型号"]
STATUS_ORDER = ["可用", "出车中", "维修中", "已停用"]
ACTION_RULES = {"安排出车": "出车中", "回场登记": "可用", "停用车辆": "已停用"}
NEGATIVE_ACTIONS = ["停用车辆"]

# 前端“全部”选项与空字符串都表示不加该维度的筛选
ALL_OPTION = "全部"


def _is_noop(value: str | None) -> bool:
    return value is None or value.strip() == "" or value.strip() == ALL_OPTION


class VehicleService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        vehicle_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword and keyword.strip():
            plate = keyword.strip()
            rows = [row for row in rows if plate in str(row.get("车牌号码", ""))]
        if not _is_noop(vehicle_type):
            vtype = vehicle_type.strip()
            rows = [row for row in rows if str(row.get("车辆类型", "")).strip() == vtype]
        if not _is_noop(status):
            target_status = status.strip()
            rows = [row for row in rows if row.get("status") == target_status]
        # 先按稳定口径排序再计数、再切片：total 永远是“筛选后”的条数，
        # 同一筛选条件下翻页不会出现重复或乱序。
        rows = sorted(rows, key=lambda row: int(row.get("id", 0)))
        total = len(rows)
        page = max(page, 1)
        start = (page - 1) * size
        return rows[start:start + size], total

    def filter_options(self) -> dict[str, Any]:
        """给筛选栏提供候选项：车辆类型取数据去重，状态用固定流转序列。"""
        rows = store.rows(MODULE)
        vehicle_types = sorted({
            str(row.get("车辆类型", "")).strip()
            for row in rows
            if str(row.get("车辆类型", "")).strip()
        })
        status_counts = {
            label: sum(1 for row in rows if row.get("status") == label)
            for label in STATUS_ORDER
        }
        return {
            "vehicle_types": vehicle_types,
            "statuses": STATUS_ORDER,
            "all": ALL_OPTION,
            "status_counts": status_counts,
        }

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"冷藏车辆 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于冷藏车管理可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"冷藏车辆已{action}"
