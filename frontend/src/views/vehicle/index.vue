<template>
  <section class="page" data-module="vehicle">
    <header class="page-head">
      <div>
        <h2>冷藏车管理</h2>
        <p class="page-desc">维护冷藏车辆，围绕车牌号码、车辆类型、制冷机组型号、车厢容积做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记冷藏车辆</button>
        <button class="btn" type="button" @click="exportRows">导出冷藏车管理清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label class="filter-item">
        <span>车牌号码</span>
        <input v-model="filters.keyword" placeholder="按车牌号码检索" />
      </label>
      <label class="filter-item">
        <span>车辆类型</span>
        <select v-model="filters.vehicle_type">
          <option value="">全部</option>
          <option v-for="t in vehicleTypes" :key="t" :value="t">{{ t }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>车辆状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <button class="btn primary" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>当前状态</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td>
            <button class="link" type="button" @click="openDetail(row)">{{ row['车牌号码'] ?? '—' }}</button>
          </td>
          <td v-for="column in columns.slice(1)" :key="column">{{ row[column] ?? '—' }}</td>
          <td>
            <span :class="['status-tag', statusClass(row.status)]">{{ row.status ?? '—' }}</span>
          </td>
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
        <tr v-if="!loading && !rows.length">
          <td :colspan="columns.length + 2" class="empty-state">
            {{ hasActiveFilters ? '当前筛选条件下没有命中的冷藏车辆，请调整车辆类型、状态或车牌关键字后重试' : '暂无冷藏车数据，可先登记冷藏车辆' }}
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条记录，第 {{ page }} / {{ totalPages || 1 }} 页</span>
      <div class="pager">
        <label class="page-size">
          每页
          <select v-model.number="size" @change="changePageSize">
            <option v-for="s in sizeOptions" :key="s" :value="s">{{ s }}</option>
          </select>
          条
        </label>
        <button class="btn" type="button" :disabled="page <= 1" @click="goPage(1)">首页</button>
        <button class="btn" type="button" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <button class="btn" type="button" :disabled="page >= totalPages" @click="goPage(page + 1)">下一页</button>
        <button class="btn" type="button" :disabled="page >= totalPages" @click="goPage(totalPages || 1)">末页</button>
      </div>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <div class="modal-card">
        <header class="modal-head">
          <h3>冷藏车辆明细</h3>
          <button class="btn ghost" type="button" @click="detail = null">关闭</button>
        </header>
        <dl class="detail-grid">
          <template v-for="column in detailColumns" :key="column.key">
            <dt>{{ column.label }}</dt>
            <dd>{{ detail[column.key] ?? '—' }}</dd>
          </template>
        </dl>
        <p class="detail-note">明细数据与列表来自同一接口数据源，停用等操作刷新后两边保持一致。</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>

interface PagePayload {
  items: Row[]
  total: number
  page: number
  size: number
}

interface FilterOptions {
  vehicle_types: string[]
  statuses: string[]
  status_counts: Record<string, number>
}

const ENDPOINT = '/api/vehicle'
const columns = ['车牌号码', '车辆类型', '制冷机组型号', '车厢容积', '温区数量', '所属车队', '年检到期日']
const detailColumns = [
  { key: 'id', label: '车辆ID' },
  { key: '车牌号码', label: '车牌号码' },
  { key: '车辆类型', label: '车辆类型' },
  { key: '制冷机组型号', label: '制冷机组型号' },
  { key: '车厢容积', label: '车厢容积' },
  { key: '温区数量', label: '温区数量' },
  { key: '所属车队', label: '所属车队' },
  { key: '年检到期日', label: '年检到期日' },
  { key: 'status', label: '当前状态' },
]
const actions = ['安排出车', '回场登记', '停用车辆']
const sizeOptions = [10, 20, 50]

const rows = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(10)
const loading = ref(false)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({ keyword: '', vehicle_type: '', status: '' })
const vehicleTypes = ref<string[]>([])
const statuses = ref<string[]>([])
const statusCounts = ref<Record<string, number>>({})
const detail = ref<Row | null>(null)

const totalPages = computed(() => (total.value ? Math.ceil(total.value / size.value) : 0))
const hasActiveFilters = computed(() =>
  Object.values(filters.value).some((value) => value.trim() !== ''),
)
const stats = computed(() => [
  { label: '可用车辆', value: statusCounts.value['可用'] ?? 0 },
  { label: '出车中车辆', value: statusCounts.value['出车中'] ?? 0 },
  { label: '维修中车辆', value: statusCounts.value['维修中'] ?? 0 },
  { label: '已停用车辆', value: statusCounts.value['已停用'] ?? 0 },
])

function statusClass(status: unknown): string {
  return {
    可用: 'status-ok',
    出车中: 'status-busy',
    维修中: 'status-fix',
    已停用: 'status-off',
  }[String(status)] ?? ''
}

function buildQuery(includePaging = true) {
  const params = new URLSearchParams()
  if (filters.value.keyword.trim()) params.set('keyword', filters.value.keyword.trim())
  if (filters.value.vehicle_type) params.set('vehicle_type', filters.value.vehicle_type)
  if (filters.value.status) params.set('status', filters.value.status)
  if (includePaging) {
    params.set('page', String(page.value))
    params.set('size', String(size.value))
  }
  return params.toString()
}

async function reload() {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}?${buildQuery()}`)
    if (!response.ok) {
      throw new Error('冷藏车辆列表读取失败')
    }
    const payload = (await response.json()) as PagePayload
    rows.value = payload.items ?? []
    total.value = payload.total ?? 0
    // 筛选条件变化后页码可能越界（例如在末页停用了车辆），回退到最后一个有效页。
    if (totalPages.value > 0 && page.value > totalPages.value) {
      page.value = totalPages.value
      await reload()
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '冷藏车辆列表读取失败'
  } finally {
    loading.value = false
  }
}

async function loadFilterOptions() {
  try {
    const response = await request(`${ENDPOINT}/filter-options`)
    if (!response.ok) return
    const options = (await response.json()) as FilterOptions
    vehicleTypes.value = options.vehicle_types ?? []
    statuses.value = options.statuses ?? []
    statusCounts.value = options.status_counts ?? {}
  } catch {
    // 候选项加载失败不阻断列表，下拉框退化为只有“全部”
  }
}

function applyFilters() {
  page.value = 1
  void reload()
}

function resetFilters() {
  filters.value = { keyword: '', vehicle_type: '', status: '' }
  page.value = 1
  void reload()
}

function goPage(target: number) {
  if (target < 1 || (totalPages.value && target > totalPages.value) || target === page.value) return
  page.value = target
  void reload()
}

function changePageSize() {
  page.value = 1
  void reload()
}

function exportRows() {
  const query = buildQuery(false)
  window.open(`${ENDPOINT}/export${query ? `?${query}` : ''}`, '_blank')
}

function openCreate() {
  errorMessage.value = '冷藏车辆登记入口尚未接入审批流'
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('冷藏车辆明细读取失败')
    }
    detail.value = (await response.json()) as Row
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '冷藏车辆明细读取失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null)
    // 业务失败时 HTTP 状态码仍是 200，必须检查 ok 字段，不能只看 response.ok
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message || '冷藏车管理动作未生效，请稍后重试')
    }
    await Promise.all([reload(), loadFilterOptions()])
    // 详情弹窗若开着，同步成最新数据
    if (detail.value && String(detail.value.id) === String(row.id) && payload.entry) {
      detail.value = payload.entry as Row
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '冷藏车管理操作失败'
  }
}

onMounted(() => {
  void loadFilterOptions()
  void reload()
})
</script>
