<template>
  <v-container>
    <v-card>
      <v-card-title class="d-flex align-center flex-wrap">
        <span class="text-h6">Transaktionen</span>
        <v-spacer />

        <v-select
          class="mr-2"
          density="comfortable"
          hide-details="auto"
          style="max-width: 140px"
          :items="yearOptions"
          v-model="filters.year"
          label="Jahr"
          clearable
        />
        <v-select
          class="mr-2"
          density="comfortable"
          hide-details="auto"
          style="max-width: 140px"
          :items="monthOptions"
          v-model="filters.month"
          label="Monat"
          clearable
        />
        <v-select
          class="mr-2"
          density="comfortable"
          hide-details="auto"
          style="max-width: 220px"
          :items="sourceOptions"
          v-model="filters.source"
          label="Quelle"
          clearable
        />
        <v-select
          class="mr-2"
          density="comfortable"
          hide-details="auto"
          style="max-width: 190px"
          :items="classifiedOptions"
          v-model="filters.classified"
          label="Status"
        />
        <v-btn color="primary" :loading="loading" :disabled="loading" @click="load">Neu laden</v-btn>
      </v-card-title>

      <v-data-table
        :headers="headers"
        :items="transactions"
        :items-per-page="15"
        density="compact"
        class="elevation-1 transaction-table"
      >
        <template #item.budget_month="{ item }">
          <span class="mono-cell">{{ formatBudgetMonth(item.budget_month) }}</span>
        </template>

        <template #item.booking_date="{ item }">
          <span class="mono-cell">{{ formatDate(item.value_date || item.booking_date) }}</span>
        </template>

        <template #item.description="{ item }">
          <div class="description-cell">
            <div class="description-main">{{ item.counterparty || item.description }}</div>
            <div v-if="item.counterparty && item.description && item.counterparty !== item.description" class="description-sub">
              {{ item.description }}
            </div>
          </div>
        </template>

        <template #item.amount="{ item }">
          <span class="amount-cell">{{ formatCurrency(item.amount, item.currency) }}</span>
        </template>

        <template #item.status="{ item }">
          <v-chip :color="item.category_key ? 'success' : 'warning'" size="x-small" variant="tonal">
            {{ item.category_key ? sourceLabel(item.classification_source) : 'Offen' }}
          </v-chip>
        </template>

        <template #item.category_key="{ item }">
          <v-select
            :items="categoryOptions"
            v-model="selections[item.id]"
            label="Kategorie"
            hide-details="auto"
            density="compact"
            class="category-select"
            clearable
          />
        </template>

        <template #item.actions="{ item }">
          <v-btn-group density="compact">
            <v-btn size="x-small" color="success" min-width="34" @click="saveClassification(item.id)">OK</v-btn>
            <v-btn size="x-small" color="error" min-width="58" @click="deleteTransaction(item.id)">Löschen</v-btn>
          </v-btn-group>
        </template>
      </v-data-table>

      <v-card-text v-if="errorMsg" class="text-error mt-2">{{ errorMsg }}</v-card-text>
    </v-card>
  </v-container>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import axios from 'axios'
const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const loading = ref(false)
const errorMsg = ref('')
const transactions = ref([])
const categories = ref([])
const selections = reactive({})

const headers = [
  { title: 'Monat', key: 'budget_month', width: '58px' },
  { title: 'Datum', key: 'booking_date', width: '62px' },
  { title: 'Beschreibung', key: 'description', width: '34%' },
  { title: 'Betrag', key: 'amount', align: 'end', width: '94px' },
  { title: 'Status', key: 'status', width: '68px' },
  { title: 'Kategorie', key: 'category_key', sortable: false, width: '260px' },
  { title: '', key: 'actions', sortable: false, width: '138px' },
]

const classifiedOptions = [
  { title: 'Alle', value: 'all' },
  { title: 'Klassifiziert', value: 'classified' },
  { title: 'Unklassifiziert', value: 'unclassified' },
]

const sourceOptions = [
  { title: 'DKB Girokonto', value: 'dkb_giro' },
  { title: 'Revolut', value: 'revolut' },
  { title: 'American Express', value: 'amex' },
  { title: 'Deutsche Bank Miles & More', value: 'deutsche_bank_miles_more' },
]

const monthOptions = [
  { title: 'Jan', value: '01' },
  { title: 'Feb', value: '02' },
  { title: 'Mrz', value: '03' },
  { title: 'Apr', value: '04' },
  { title: 'Mai', value: '05' },
  { title: 'Jun', value: '06' },
  { title: 'Jul', value: '07' },
  { title: 'Aug', value: '08' },
  { title: 'Sep', value: '09' },
  { title: 'Okt', value: '10' },
  { title: 'Nov', value: '11' },
  { title: 'Dez', value: '12' },
]

const filters = reactive({ year: null, month: null, source: null, classified: 'all' })

const yearOptions = computed(() => {
  const years = new Set()
  transactions.value.forEach(t => {
    const y = (t.budget_month || '').slice(0, 4)
    if (/^\d{4}$/.test(y)) years.add(y)
  })
  const currentYear = new Date().getFullYear()
  years.add(String(currentYear))
  years.add(String(currentYear - 1))
  return Array.from(years).sort().reverse()
})

const categoryOptions = computed(() => {
  return categories.value
    .filter(c => c.active)
    .sort((a, b) => a.sort_order - b.sort_order)
    .map(c => ({
      title: `${c.group} · ${c.name}`,
      value: c.key,
    }))
})

function sourceLabel(value) {
  if (value === 'rule') return 'Regel'
  if (value === 'manual') return 'Manuell'
  if (value === 'imported') return 'Import'
  return 'offen'
}

function formatCurrency(value, currency = 'EUR') {
  const num = Number(value)
  if (Number.isNaN(num)) return '—'
  return num.toLocaleString('de-DE', { style: 'currency', currency: currency || 'EUR' })
}

function formatBudgetMonth(value) {
  if (!value || typeof value !== 'string' || value.length < 7) return '—'
  return `${value.slice(5, 7)}/${value.slice(2, 4)}`
}

function formatDate(value) {
  if (!value || typeof value !== 'string') return '—'
  if (/^\d{4}-\d{2}-\d{2}/.test(value)) {
    return `${value.slice(8, 10)}.${value.slice(5, 7)}.`
  }
  return value
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const [catsRes, txRes] = await Promise.all([
      axios.get(`${API_BASE}/v2/categories`),
      axios.get(`${API_BASE}/v2/transactions`, { params: buildParams() }),
    ])

    categories.value = catsRes.data.categories || []
    transactions.value = txRes.data.transactions || []

    transactions.value.forEach(tx => {
      selections[tx.id] = tx.category_key || null
    })
  } catch (err) {
    console.error('Fehler beim Laden:', err)
    errorMsg.value = err.response?.data?.detail || 'Konnte Transaktionen nicht laden.'
  } finally {
    loading.value = false
  }
}

function buildParams() {
  const params = {}
  if (filters.year) params.year = filters.year
  if (filters.month) params.month = filters.month
  if (filters.source) params.source = filters.source
  if (filters.classified && filters.classified !== 'all') params.classified = filters.classified
  return params
}

async function saveClassification(txId) {
  try {
    const categoryKey = selections[txId] || null
    await axios.post(`${API_BASE}/v2/transactions/${txId}/classify`, {
      category_key: categoryKey,
    })
    const tx = transactions.value.find(t => t.id === txId)
    if (tx) {
      tx.category_key = categoryKey
      tx.classification_source = categoryKey ? 'manual' : 'unknown'
      tx.classification_rule_key = null
      tx.classification_confidence = categoryKey ? 1 : 0
    }
  } catch (err) {
    console.error('Klassifikation konnte nicht gespeichert werden:', err)
    alert(err.response?.data?.detail || 'Konnte Klassifikation nicht speichern')
  }
}

async function deleteTransaction(txId) {
  if (!confirm('Diese Transaktion wirklich löschen?')) return
  try {
    await axios.delete(`${API_BASE}/v2/transactions/${txId}`)
    transactions.value = transactions.value.filter(tx => tx.id !== txId)
    delete selections[txId]
  } catch (err) {
    console.error('Transaktion konnte nicht gelöscht werden:', err)
    alert(err.response?.data?.detail || 'Konnte Transaktion nicht löschen')
  }
}

onMounted(load)

let reloadTimer = null
function scheduleLoad() {
  if (reloadTimer) clearTimeout(reloadTimer)
  reloadTimer = setTimeout(load, 250)
}

watch(() => filters.year, scheduleLoad)
watch(() => filters.month, scheduleLoad)
watch(() => filters.source, scheduleLoad)
watch(() => filters.classified, scheduleLoad)
</script>

<style scoped>
.transaction-table {
  table-layout: fixed;
}

.transaction-table :deep(table) {
  table-layout: fixed;
  width: 100%;
}

.transaction-table :deep(th),
.transaction-table :deep(td) {
  padding-left: 6px !important;
  padding-right: 6px !important;
  vertical-align: middle;
}

.mono-cell,
.amount-cell {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.description-cell {
  min-width: 0;
  overflow: hidden;
}

.description-main,
.description-sub {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.description-main {
  font-weight: 500;
}

.description-sub {
  color: rgba(0, 0, 0, 0.58);
  font-size: 0.76rem;
  margin-top: 2px;
}

.category-select {
  min-width: 0;
  width: 100%;
}

.category-select :deep(.v-field) {
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
}

.category-select :deep(.v-field__input) {
  min-width: 0;
  overflow: hidden;
  flex-wrap: nowrap;
}

.category-select :deep(.v-select__selection) {
  min-width: 0;
  overflow: hidden;
  flex: 1 1 auto;
}

.category-select :deep(.v-select__selection-text) {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.category-select :deep(.v-field__field) {
  min-width: 0;
  overflow: hidden;
}

.transaction-table :deep(.v-table__wrapper) {
  overflow-x: hidden;
}

.transaction-table :deep(td:last-child) {
  white-space: nowrap;
}
</style>
