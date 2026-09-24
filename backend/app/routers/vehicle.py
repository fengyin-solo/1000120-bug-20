"""冷藏车管理接口：维护冷藏车辆，覆盖安排出车、回场登记、停用车辆等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.vehicle import VehicleService

router = APIRouter(prefix="/api/vehicle", tags=["冷藏车管理"])

service = VehicleService()

LIST_FIELDS = ["车牌号码", "车辆类型", "制冷机组型号", "车厢容积", "温区数量", "所属车队", "年检到期日"]
STATUSES = ["可用", "出车中", "维修中", "已停用"]


@router.get("/types")
def list_types() -> dict[str, Any]:
    """车辆类型筛选项：给列表页的类型下拉提供去重后的候选值。"""
    return {"items": service.list_types()}


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按车牌号码检索"),
    vehicle_type: str | None = Query(default=None, description="按车辆类型精确过滤"),
    unit_model: str | None = Query(default=None, description="按制冷机组型号检索"),
    status: str | None = Query(default=None, description="可用、出车中、维修中、已停用"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    size: int = Query(default=20, ge=1, le=200, description="每页条数，1-200"),
) -> PageResult[dict]:
    """按车牌号码、车辆类型、制冷机组型号与状态过滤冷藏车管理列表。

    total 按筛选后的口径统计；页码超出范围时返回空 items，不报错。
    """
    items, total = service.list_entries(
        keyword=keyword,
        vehicle_type=vehicle_type,
        unit_model=unit_model,
        status=status,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries(
    keyword: str | None = Query(default=None),
    vehicle_type: str | None = Query(default=None),
    unit_model: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict[str, Any]:
    """导出冷藏车管理清单：与列表页使用同一套筛选条件，保证看到同一份结果。"""
    items, total = service.list_entries(
        keyword=keyword,
        vehicle_type=vehicle_type,
        unit_model=unit_model,
        status=status,
        page=1,
        size=10000,
    )
    return {"module": "vehicle", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条冷藏车辆明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"冷藏车辆 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条冷藏车辆，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="冷藏车辆已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条冷藏车辆执行安排出车、回场登记、停用车辆；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
