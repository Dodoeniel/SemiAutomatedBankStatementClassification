<template>
  <v-container>
    <v-card>
      <v-card-title class="d-flex align-center flex-wrap">
        Cashflow
        <v-spacer />
        <v-btn color="primary" :loading="loading" :disabled="loading" @click="loadChartData">Neu laden</v-btn>
      </v-card-title>

      <v-card-text>
        <Bar v-if="cashflowChartData" :data="cashflowChartData" :options="cashflowOptions" />
        <div v-else>Lade Daten...</div>
      </v-card-text>
    </v-card>

    <v-card class="mt-4">
      <v-card-title class="d-flex align-center flex-wrap">
        {{ sankeyTitle }}
        <v-spacer />
        <v-btn-toggle v-model="sankeyMode" density="comfortable" class="mr-3">
          <v-btn value="month">Monat</v-btn>
          <v-btn value="year">Jahr</v-btn>
        </v-btn-toggle>
        <v-select
          v-if="sankeyMode === 'month'"
          v-model="selectedMonth"
          :items="monthOptions"
          label="Monat"
          density="comfortable"
          hide-details
          style="max-width: 180px"
        />
        <v-select
          v-else
          v-model="selectedYear"
          :items="yearOptions"
          label="Jahr"
          density="comfortable"
          hide-details
          style="max-width: 140px"
        />
      </v-card-title>
      <v-card-text>
        <div v-if="sankeyData.totalInflow > 0 || sankeyData.totalExpense > 0" class="sankey-wrap">
          <svg :viewBox="`0 0 ${SANKEY_WIDTH} ${SANKEY_HEIGHT}`" role="img" class="sankey-svg">
            <defs>
              <linearGradient id="incomeFlow" x1="0%" x2="100%">
                <stop offset="0%" stop-color="#2f8f83" stop-opacity="0.38" />
                <stop offset="100%" stop-color="#2f8f83" stop-opacity="0.13" />
              </linearGradient>
              <linearGradient id="expenseFlow" x1="0%" x2="100%">
                <stop offset="0%" stop-color="#d26a5c" stop-opacity="0.13" />
                <stop offset="100%" stop-color="#d26a5c" stop-opacity="0.40" />
              </linearGradient>
              <linearGradient id="netFlow" x1="0%" x2="100%">
                <stop offset="0%" stop-color="#4f6f8f" stop-opacity="0.13" />
                <stop offset="100%" stop-color="#4f6f8f" stop-opacity="0.40" />
              </linearGradient>
            </defs>

            <path
              v-for="link in sankeyData.links"
              :key="link.key"
              :d="link.path"
              :stroke-width="Math.max(1, link.width)"
              :stroke="link.color"
              :stroke-opacity="link.opacity"
              fill="none"
              stroke-linecap="round"
            />

            <g v-for="node in sankeyData.nodes" :key="node.key">
              <rect :x="node.x0" :y="node.y0" :width="node.x1 - node.x0" :height="Math.max(1, node.y1 - node.y0)" :rx="5" :fill="node.color" />
              <text :x="node.labelX" :y="node.labelY" class="sankey-label" :text-anchor="node.anchor">
                {{ node.label }}
              </text>
              <text :x="node.labelX" :y="node.labelY + 20" class="sankey-value" :text-anchor="node.anchor">
                {{ fmt(node.value) }}
              </text>
            </g>
          </svg>
        </div>
        <v-alert v-else type="info" variant="tonal">
          Für diesen Zeitraum sind noch keine klassifizierten Zahlungsflüsse vorhanden.
        </v-alert>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup>
import axios from 'axios'
import { computed, onMounted, ref } from 'vue'
import { Bar } from 'vue-chartjs'
import { sankey, sankeyJustify, sankeyLinkHorizontal } from 'd3-sankey'
import { Chart, BarController, BarElement, CategoryScale, LinearScale, Tooltip, Legend } from 'chart.js'
Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip, Legend)

const API_BASE = import.meta.env.VITE_API_BASE || '/api'
const SANKEY_WIDTH = 1100
const SANKEY_HEIGHT = 560
const SANKEY_MARGIN = { top: 30, right: 210, bottom: 30, left: 180 }
const COLORS = {
  income: '#2f8f83',
  month: '#455a64',
  expense: '#d26a5c',
  net: '#4f6f8f',
}

const loading = ref(false)
const monthly = ref(null)
const selectedMonth = ref(null)
const selectedYear = ref(null)
const sankeyMode = ref('month')
const cashflowChartData = ref(null)

const cashflowOptions = {
  responsive: true,
  scales: {
    x: { stacked: false },
    y: { beginAtZero: true },
  },
  plugins: {
    legend: { position: 'bottom' },
    tooltip: {
      callbacks: {
        label: context => `${context.dataset.label}: ${fmt(context.raw)}`,
      },
    },
  },
}

const monthOptions = computed(() => monthly.value?.totals?.months || [])
const yearOptions = computed(() => {
  const years = new Set()
  for (const month of monthOptions.value) {
    if (typeof month === 'string' && month.length >= 4) years.add(month.slice(0, 4))
  }
  return Array.from(years).sort().reverse()
})
const sankeyTitle = computed(() => {
  if (sankeyMode.value === 'year') return `Jahresfluss ${selectedYear.value || ''}`
  return `Monatsfluss ${selectedMonth.value || ''}`
})

const currencyFmt = new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' })
function fmt(value) {
  return currencyFmt.format(Number(value || 0))
}

async function loadChartData() {
  loading.value = true
  try {
    const res = await axios.get(`${API_BASE}/v2/analytics/monthly`)
    monthly.value = res.data
    const months = monthly.value?.totals?.months || []
    if (!selectedMonth.value && months.length) {
      selectedMonth.value = months[months.length - 1]
    }
    if (!selectedYear.value && months.length) {
      selectedYear.value = months[months.length - 1].slice(0, 4)
    }
    rebuildCashflowChart()
  } catch (err) {
    console.error('Fehler beim Laden der Chart-Daten:', err)
  } finally {
    loading.value = false
  }
}

function rebuildCashflowChart() {
  const totals = monthly.value?.totals || { months: [], income: [], expense: [], net: [] }
  cashflowChartData.value = {
    labels: totals.months,
    datasets: [
      { label: 'Einnahmen', data: totals.income, backgroundColor: '#2f8f83', borderRadius: 4 },
      { label: 'Ausgaben', data: totals.expense, backgroundColor: '#d26a5c', borderRadius: 4 },
      { label: 'Netto', data: totals.net, backgroundColor: '#4f6f8f', borderRadius: 4 },
    ],
  }
}

const sankeyData = computed(() => {
  const empty = { totalInflow: 0, totalExpense: 0, nodes: [], links: [] }
  if (!monthly.value || !selectedMonth.value) return empty

  const totals = monthly.value.totals || { months: [], income: [], expense: [], net: [] }
  const monthIndices = selectedSankeyMonthIndices(totals.months)
  if (!monthIndices.length) return empty

  const incomeItems = groupPeriodValues(monthly.value.income, monthIndices, 4)
  const expenseItems = groupPeriodValues(monthly.value.expense, monthIndices, 8)
  const totalInflow = sumAtIndices(totals.income, monthIndices)
  const totalExpense = sumAtIndices(totals.expense, monthIndices)
  const net = sumAtIndices(totals.net, monthIndices)
  const positiveNet = Math.max(net, 0)
  const periodLabel = sankeyMode.value === 'year' ? selectedYear.value : selectedMonth.value

  const nodes = [
    ...incomeItems.map(item => ({
      id: `income:${item.key}`,
      key: `income:${item.key}`,
      label: item.label,
      color: COLORS.income,
    })),
    { id: 'period', key: 'period', label: periodLabel, color: COLORS.month },
    ...expenseItems.map(item => ({
      id: `expense:${item.key}`,
      key: `expense:${item.key}`,
      label: item.label,
      color: COLORS.expense,
    })),
    ...(positiveNet > 0 ? [{ id: 'net', key: 'net', label: 'Übrig', color: COLORS.net }] : []),
  ]

  const links = [
    ...incomeItems.map(item => ({
      source: `income:${item.key}`,
      target: 'period',
      value: item.value,
      color: COLORS.income,
      opacity: 0.22,
    })),
    ...expenseItems.map(item => ({
      source: 'period',
      target: `expense:${item.key}`,
      value: item.value,
      color: COLORS.expense,
      opacity: 0.24,
    })),
    ...(positiveNet > 0 ? [{
      source: 'period',
      target: 'net',
      value: positiveNet,
      color: COLORS.net,
      opacity: 0.20,
    }] : []),
  ]

  const graph = sankey()
    .nodeId(node => node.id)
    .nodeAlign(sankeyJustify)
    .nodeWidth(22)
    .nodePadding(20)
    .extent([
      [SANKEY_MARGIN.left, SANKEY_MARGIN.top],
      [SANKEY_WIDTH - SANKEY_MARGIN.right, SANKEY_HEIGHT - SANKEY_MARGIN.bottom],
    ])
    ({
      nodes: nodes.map(node => ({ ...node })),
      links: links.map(link => ({ ...link })),
    })

  const linkPath = sankeyLinkHorizontal()
  const renderedNodes = graph.nodes.map(node => ({
    ...node,
    key: node.id,
    value: node.value || 0,
    color: node.color,
    anchor: node.x0 < SANKEY_WIDTH / 2 ? 'end' : 'start',
    labelX: node.x0 < SANKEY_WIDTH / 2 ? node.x0 - 10 : node.x1 + 10,
    labelY: (node.y0 + node.y1) / 2 - 6,
  }))

  const renderedLinks = graph.links.map((link, index) => ({
    key: `${link.source.id}-${link.target.id}-${index}`,
    path: linkPath(link),
    width: link.width,
    color: link.color,
    opacity: link.opacity,
  }))

  return {
    totalInflow,
    totalExpense,
    nodes: renderedNodes,
    links: renderedLinks,
  }
})

function selectedSankeyMonthIndices(months) {
  if (sankeyMode.value === 'year') {
    if (!selectedYear.value) return []
    return months
      .map((month, index) => month?.startsWith(selectedYear.value) ? index : -1)
      .filter(index => index >= 0)
  }

  const monthIndex = months.indexOf(selectedMonth.value)
  return monthIndex >= 0 ? [monthIndex] : []
}

function sumAtIndices(values = [], indices = []) {
  return indices.reduce((sum, index) => sum + Number(values?.[index] || 0), 0)
}

function groupPeriodValues(payload, monthIndices, topN) {
  const totals = new Map()
  for (const category of payload?.categories || []) {
    const value = sumAtIndices(payload.display_data?.[category.key], monthIndices)
    if (value <= 0) continue
    const key = category.group || category.name
    totals.set(key, (totals.get(key) || 0) + value)
  }

  const sorted = Array.from(totals.entries())
    .map(([label, value]) => ({ key: slug(label), label, value }))
    .sort((a, b) => b.value - a.value)

  if (sorted.length <= topN) return sorted
  const top = sorted.slice(0, topN)
  const rest = sorted.slice(topN).reduce((sum, item) => sum + item.value, 0)
  if (rest > 0) top.push({ key: 'other', label: 'Sonstiges', value: rest })
  return top
}

function slug(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

onMounted(loadChartData)
</script>

<style scoped>
.sankey-wrap {
  width: 100%;
  overflow-x: auto;
}

.sankey-svg {
  min-width: 900px;
  width: 100%;
  height: auto;
  display: block;
}

.sankey-label {
  fill: #263238;
  font-size: 14px;
  font-weight: 600;
}

.sankey-value {
  fill: #546e7a;
  font-size: 12px;
}
</style>
