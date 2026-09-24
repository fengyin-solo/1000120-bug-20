<template>
  <section class="page" data-module="vehicle">
    <header class="page-head">
      <div>
        <h2>冷藏车管理</h2>
        <p class="page-desc">维护冷藏车辆，围绕车牌号码、车辆类型、制冷机组型号、车厢容积做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记冷藏车辆</button>
        <button class="btn" type="button" @click="exportRows">导出冷藏车清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="search">
      <label class="filter-item">
        <span>车牌号码</span>
        <input v-model="keyword" placeholder="按车牌号码检索" />
      </label>
      <label class="filter-item">
        <span>车辆类型</span>
        <select v-model="vehicleType">
          <option value="">全部</option>
          <option v-for="type in typeOptions" :key="type" :value="type">{{ type }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>制冷机组型号</span>
        <input v-model="unitModel" placeholder="按制冷机组型号检索" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyText }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条冷藏车记录</span>
      <div class="pager">
        <label>
          每页
          <select v-model.number="size" @change="changePageSize">
            <option v-for="option in sizeOptions" :key="option" :value="option">{{ option }}</option>
          </select>
          条
        </label>
        <button class="btn" type="button" :disabled="page <= 1" @click="gotoPage(page - 1)">上一页</button>
        <span>第 {{ page }} / {{ totalPages }} 页</span>
        <button class="btn" type="button" :disabled="page >= totalPages" @click="gotoPage(page + 1)">下一页</button>
      </div>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/vehicle'
const columns = ["车牌号码", "车辆类型", "制冷机组型号", "车厢容积", "温区数量", "所属车队", "年检到期日"]
const actions = ["安排出车", "回场登记", "停用车辆"]
const stats = [{"label": "可用车辆", "value": 0}, {"label": "出车中车辆", "value": 0}, {"label": "维修中车辆", "value": 0}]
const sizeOptions = [10, 20, 50]

const rows = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(10)
const errorMessage = ref('')
const keyword = ref('')
const vehicleType = ref('')
const unitModel = ref('')
const typeOptions = ref<string[]>([])
const loadedOnce = ref(false)

const totalPages = computed(() => Math.max(Math.ceil(total.value / size.value), 1))
const hasActiveFilter = computed(() => Boolean(keyword.value.trim() || vehicleType.value || unitModel.value.trim()))
const emptyText = computed(() =>
  hasActiveFilter.value
    ? '当前筛选条件下没有匹配的冷藏车，请调整条件或重置后重试'
    : '暂无冷藏车数据，可先登记冷藏车辆',
)

function filterQuery() {
  const params = new URLSearchParams()
  if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
  if (vehicleType.value) params.set('vehicle_type', vehicleType.value)
  if (unitModel.value.trim()) params.set('unit_model', unitModel.value.trim())
  return params
}

function search() {
  page.value = 1
  void reload()
}

function resetFilters() {
  keyword.value = ''
  vehicleType.value = ''
  unitModel.value = ''
  page.value = 1
  void reload()
}

function gotoPage(target: number) {
  const next = Math.min(Math.max(target, 1), totalPages.value)
  if (next === page.value) return
  page.value = next
  void reload()
}

function changePageSize() {
  page.value = 1
  void reload()
}

function exportRows() {
  const query = filterQuery().toString()
  window.open(`${ENDPOINT}/export${query ? `?${query}` : ''}`, '_blank')
}

function openCreate() {
  errorMessage.value = '冷藏车辆登记入口尚未接入审批流'
}

async function loadTypes() {
  try {
    const response = await request(`${ENDPOINT}/types`)
    if (!response.ok) return
    const payload = await response.json()
    typeOptions.value = payload.items ?? []
  } catch {
    // 类型选项加载失败时保留下拉的「全部」，不阻断列表查询
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    // 动作必须放在 values 里，与后端 EntryPayload 对齐，否则会被当成空动作拦下。
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message || '冷藏车动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '冷藏车操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const params = filterQuery()
  params.set('page', String(page.value))
  params.set('size', String(size.value))
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error('冷藏车辆列表读取失败')
    }
    const payload = await response.json()
    total.value = payload.total ?? 0
    // 停用车辆后当前页可能超出范围：回到最后一页重新拉取，保证列表与实际状态一致。
    if (!(payload.items ?? []).length && total.value > 0 && page.value > 1) {
      page.value = Math.max(Math.ceil(total.value / size.value), 1)
      await reload()
      return
    }
    rows.value = payload.items ?? []
    loadedOnce.value = true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '冷藏车列表读取失败'
  }
}

onMounted(() => {
  void loadTypes()
  void reload()
})
</script>
