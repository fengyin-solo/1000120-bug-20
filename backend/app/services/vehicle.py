"""冷藏车管理业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "vehicle"
PLATE_FIELD = "车牌号码"
TYPE_FIELD = "车辆类型"
MODEL_FIELD = "制冷机组型号"
REQUIRED_FIELDS = [PLATE_FIELD, TYPE_FIELD, MODEL_FIELD]
STATUS_ORDER = ["可用", "出车中", "维修中", "已停用"]
ACTION_RULES = {"安排出车": "出车中", "回场登记": "可用", "停用车辆": "已停用"}
NEGATIVE_ACTIONS = ["停用车辆"]


def _normalized(value: str | None) -> str | None:
    """把空白入参统一成 None，避免 ' ' 之类的值过滤掉全部记录。"""
    text = str(value or "").strip()
    return text or None


class VehicleService:
    def _filtered_rows(
        self,
        *,
        keyword: str | None = None,
        vehicle_type: str | None = None,
        unit_model: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        keyword = _normalized(keyword)
        vehicle_type = _normalized(vehicle_type)
        unit_model = _normalized(unit_model)
        status = _normalized(status)

        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get(PLATE_FIELD, ""))]
        if vehicle_type:
            rows = [row for row in rows if str(row.get(TYPE_FIELD, "")).strip() == vehicle_type]
        if unit_model:
            rows = [row for row in rows if unit_model in str(row.get(MODEL_FIELD, ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        # 先按车辆类型聚合、再按 id 排序：保证筛选后顺序稳定，
        # 翻页切片时同一类型不会在不同页之间串序或重复。
        return sorted(rows, key=lambda row: (str(row.get(TYPE_FIELD) or ""), int(row.get("id", 0))))

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        vehicle_type: str | None = None,
        unit_model: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        # total 必须在筛选之后、切片之前统计，与当前页记录同口径。
        rows = self._filtered_rows(
            keyword=keyword,
            vehicle_type=vehicle_type,
            unit_model=unit_model,
            status=status,
        )
        total = len(rows)
        page = max(page, 1)
        size = max(size, 1)
        start = (page - 1) * size
        return rows[start:start + size], total

    def list_types(self) -> list[str]:
        """提供车辆类型筛选项：返回去重、去空白后的全部类型。"""
        types = {str(row.get(TYPE_FIELD) or "").strip() for row in store.rows(MODULE)}
        return sorted(value for value in types if value)

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
