<template>
  <v-container class="pa-0">
    <v-card>
      <v-card-title class="d-flex align-center">
        Monatstabelle
        <v-spacer />
        <v-select
          v-model="selectedYear"
          :items="yearOptions"
          label="Jahr"
          density="compact"
          style="max-width: 140px"
        />
        <v-btn class="ml-3" color="primary" :loading="loading" :disabled="loading" @click="loadData">
          Neu laden
        </v-btn>
      </v-card-title>

      <v-divider />

      <v-card-text>
        <h3 class="text-h6 mb-2">EINNAHMEN</h3>
        <v-table density="compact" class="elevation-1 year-table">
          <thead>
            <tr>
              <th class="category-col">Kategorie</th>
              <th v-for="month in MONTHS_SHORT" :key="`inc-h-${month}`" class="text-right">{{ month }}</th>
              <th class="text-right">Jahr</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="group in groupedIncomeRows" :key="`inc-${group.name}`">
              <tr class="group-row">
                <td>{{ group.name }}</td>
                <td v-for="(value, index) in group.values" :key="`inc-group-${group.name}-${index}`" class="text-right">
                  {{ fmtCell(value) }}
                </td>
                <td class="text-right">{{ fmtCell(group.total) }}</td>
              </tr>
              <tr v-for="row in group.rows" :key="row.category.key" class="subcategory-row">
                <td>{{ row.category.name }}</td>
                <td v-for="(value, index) in row.values" :key="`inc-${row.category.key}-${index}`" class="text-right">
                  <CellTooltip
                    :value="value"
                    :category="row.category"
                    :budget-month="budgetMonth(index)"
                    :details="detailsCache[detailsKey(row.category.key, budgetMonth(index))]"
                    @load="loadCellDetails(row.category.key, budgetMonth(index))"
                  />
                </td>
                <td class="text-right font-weight-medium">{{ fmtCell(row.total) }}</td>
              </tr>
            </template>
            <tr v-if="groupedIncomeRows.length === 0">
              <td :colspan="MONTHS_SHORT.length + 2" class="text-center text-medium-emphasis">
                Keine Einnahmen für {{ selectedYear || 'das Jahr' }}.
              </td>
            </tr>            
          </tbody>
        </v-table>
      </v-card-text>

      <v-divider class="my-4" />

      <v-card-text>
        <h3 class="text-h6 mb-2">AUSGABEN</h3>
        <v-table density="compact" class="elevation-1 year-table">
          <thead>
            <tr>
              <th class="category-col">Kategorie</th>
              <th v-for="month in MONTHS_SHORT" :key="`exp-h-${month}`" class="text-right">{{ month }}</th>
              <th class="text-right">Jahr</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="group in groupedExpenseRows" :key="`exp-${group.name}`">
              <tr class="group-row">
                <td>{{ group.name }}</td>
                <td v-for="(value, index) in group.values" :key="`exp-group-${group.name}-${index}`" class="text-right">
                  {{ fmtCell(value) }}
                </td>
                <td class="text-right">{{ fmtCell(group.total) }}</td>
              </tr>
              <tr v-for="row in group.rows" :key="row.category.key" class="subcategory-row">
                <td>{{ row.category.name }}</td>
                <td v-for="(value, index) in row.values" :key="`exp-${row.category.key}-${index}`" class="text-right">
                  <CellTooltip
                    :value="value"
                    :category="row.category"
                    :budget-month="budgetMonth(index)"
                    :details="detailsCache[detailsKey(row.category.key, budgetMonth(index))]"
                    @load="loadCellDetails(row.category.key, budgetMonth(index))"
                  />
                </td>
                <td class="text-right font-weight-medium">{{ fmtCell(row.total) }}</td>
              </tr>
            </template>
            <tr v-if="groupedExpenseRows.length === 0">
              <td :colspan="MONTHS_SHORT.length + 2" class="text-center text-medium-emphasis">
                Keine Ausgaben für {{ selectedYear || 'das Jahr' }}.
              </td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, reactive, ref, resolveComponent } from 'vue'
import axios from 'axios'
const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const MONTHS_SHORT = ['JAN','FEB','MRZ','APR','MAI','JUN','JUL','AUG','SEP','OKT','NOV','DEZ']
const loading = ref(false)
const selectedYear = ref(null)
const monthly = ref({ income: emptyPayload(), expense: emptyPayload(), totals: { months: [] } })
const detailsCache = reactive({})

const currencyFmt = new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' })
const compactNumberFmt = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 0 })
function fmt(value) {
  return currencyFmt.format(Number(value || 0))
}

function fmtCell(value) {
  const amount = Number(value || 0)
  if (Math.abs(amount) < 0.5) return '–'
  return compactNumberFmt.format(amount)
}

const CellTooltip = defineComponent({
  props: {
    value: Number,
    category: Object,
    budgetMonth: String,
    details: Object,
  },
  emits: ['load'],
  setup(props, { emit }) {
    const VTooltip = resolveComponent('v-tooltip')
    return () => h('span', [
      h(VTooltip, { location: 'top', maxWidth: 420 }, {
        activator: ({ props: activatorProps }) => h(
          'span',
          { ...activatorProps, onMouseenter: () => emit('load') },
          fmtCell(props.value),
        ),
        default: () => h('div', { style: 'font-size:12px' }, [
          h('div', { class: 'mb-1' }, `${props.category?.name || ''} · ${props.budgetMonth}`),
          props.details
            ? props.details.error
              ? h('em', 'Details konnten nicht geladen werden.')
              : h('div', [
                h('div', { class: 'text-medium-emphasis mb-1' }, `Einträge: ${props.details.count || 0} · Summe: ${fmt(props.details.display_total || 0)}`),
                h('ul', { style: 'margin:0; padding-left:16px; max-height:160px; overflow:auto' },
                  (props.details.entries || []).slice(0, 8).map(entry => h('li', { key: entry.id }, `${entry.value_date || entry.booking_date} · ${(entry.description || '').slice(0, 60)} · ${fmt(entry.display_amount)}`)),
                ),
              ])
            : h('em', 'Lade Details...'),
        ]),
      }),
    ])
  },
})

function emptyPayload() {
  return { months: [], categories: [], display_data: {}, signed_data: {} }
}

function detailsKey(categoryKey, budgetMonthValue) {
  return `${categoryKey}|${budgetMonthValue}`
}

function budgetMonth(index) {
  return `${selectedYear.value}-${String(index + 1).padStart(2, '0')}`
}

async function loadCellDetails(categoryKey, budgetMonthValue) {
  const key = detailsKey(categoryKey, budgetMonthValue)
  if (detailsCache[key]) return
  try {
    const res = await axios.get(`${API_BASE}/v2/analytics/details`, {
      params: { category_key: categoryKey, budget_month: budgetMonthValue },
    })
    detailsCache[key] = res.data
  } catch (err) {
    detailsCache[key] = { error: true }
    console.error('Details laden fehlgeschlagen:', err)
  }
}

const yearOptions = computed(() => {
  const years = new Set()
  ;[
    ...(monthly.value.income?.months || []),
    ...(monthly.value.expense?.months || []),
  ].forEach(month => {
    if (typeof month === 'string' && month.length >= 4) years.add(month.slice(0, 4))
  })
  const arr = Array.from(years).sort()
  if (!selectedYear.value && arr.length) selectedYear.value = arr[arr.length - 1]
  return arr
})

function buildRows(payload, year) {
  const months = payload.months || []
  const idxByMonth = new Map(months.map((budgetMonthValue, index) => [budgetMonthValue, index]))
  return (payload.categories || []).map(category => {
    const values = Array.from({ length: 12 }, (_, monthIndex) => {
      const ym = `${year}-${String(monthIndex + 1).padStart(2, '0')}`
      const idx = idxByMonth.get(ym)
      return idx != null ? (payload.display_data?.[category.key]?.[idx] || 0) : 0
    })
    return {
      category,
      values,
      total: values.reduce((sum, value) => sum + value, 0),
    }
  })
}

function groupRows(rows) {
  const groups = new Map()
  for (const row of rows) {
    const groupName = row.category.group || 'Sonstiges'
    if (!groups.has(groupName)) {
      groups.set(groupName, {
        name: groupName,
        values: Array(12).fill(0),
        total: 0,
        rows: [],
      })
    }
    const group = groups.get(groupName)
    row.values.forEach((value, index) => {
      group.values[index] += value
    })
    group.total += row.total
    group.rows.push(row)
  }
  return Array.from(groups.values()).map(group => ({
    ...group,
    rows: group.rows.filter(row => Math.abs(row.total) >= 0.5),
  })).filter(group => Math.abs(group.total) >= 0.5)
}

const incomeRows = computed(() => selectedYear.value ? buildRows(monthly.value.income || emptyPayload(), selectedYear.value) : [])
const expenseRows = computed(() => selectedYear.value ? buildRows(monthly.value.expense || emptyPayload(), selectedYear.value) : [])
const groupedIncomeRows = computed(() => groupRows(incomeRows.value))
const groupedExpenseRows = computed(() => groupRows(expenseRows.value))

async function loadData() {
  loading.value = true
  try {
    const res = await axios.get(`${API_BASE}/v2/analytics/monthly`)
    monthly.value = {
      income: res.data.income || emptyPayload(),
      expense: res.data.expense || emptyPayload(),
      totals: res.data.totals || { months: [] },
    }
  } catch (err) {
    console.error('Fehler beim Laden der Monatstabelle:', err)
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.v-table th,
.v-table td {
  white-space: nowrap;
}

.year-table {
  table-layout: fixed;
  width: 100%;
}

.year-table :deep(table) {
  table-layout: fixed;
  width: 100%;
}

.year-table :deep(th),
.year-table :deep(td) {
  font-size: 0.82rem;
  padding-left: 6px !important;
  padding-right: 6px !important;
  width: 64px;
}

.year-table :deep(.category-col),
.year-table :deep(td:first-child) {
  width: 178px;
  max-width: 178px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.group-row {
  background: rgba(69, 90, 100, 0.08);
  font-weight: 700;
}

.subcategory-row td:first-child {
  padding-left: 20px !important;
  color: rgba(0, 0, 0, 0.72);
}
</style>
