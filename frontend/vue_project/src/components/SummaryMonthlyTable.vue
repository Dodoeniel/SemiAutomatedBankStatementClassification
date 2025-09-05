<template>
  <v-container class="pa-0">
    <v-card>
      <v-card-title class="d-flex align-center">
        Monatsübersicht
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

      <!-- EINKOMMEN -->
      <v-card-text>
        <h3 class="text-h6 mb-2">EINKOMMEN</h3>
        <v-table density="comfortable" class="elevation-1">
          <thead>
            <tr>
              <th style="min-width: 220px">Kategorie</th>
              <th v-for="(m, i) in MONTHS_SHORT" :key="'inc-h-'+i" class="text-right">{{ m }}</th>
              <th class="text-right">Jahr</th>
              <th class="text-right">Sparkline</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in incomeRows" :key="'inc-'+row.name">
              <td>{{ row.name }}</td>
              <td v-for="(val, i) in row.values" :key="'inc-v-'+row.name+'-'+i" class="text-right">
                <v-tooltip location="top" max-width="380">
                  <template #activator="{ props }">
                    <span v-bind="props" @mouseenter="loadCellDetails('income', row.name, `${selectedYear}-${String(i+1).padStart(2,'0')}`)">
                      {{ fmt(val) }}
                    </span>
                  </template>
                  <div style="font-size:12px">
                    <div class="mb-1"><strong>{{ row.name }}</strong> – {{ selectedYear }}-{{ String(i+1).padStart(2,'0') }}</div>
                    <div v-if="detailsCache[detailsKey('income', row.name, `${selectedYear}-${String(i+1).padStart(2,'0')}`)]">
                      <template v-if="!detailsCache[detailsKey('income', row.name, `${selectedYear}-${String(i+1).padStart(2,'0')}`)].error">
                        <div class="text-medium-emphasis mb-1">
                          Einträge: {{ detailsCache[detailsKey('income', row.name, `${selectedYear}-${String(i+1).padStart(2,'0')}`)].count || 0 }} · Summe:
                          {{ fmt(detailsCache[detailsKey('income', row.name, `${selectedYear}-${String(i+1).padStart(2,'0')}`)].total || 0) }}
                        </div>
                        <ul style="margin:0; padding-left:16px; max-height:160px; overflow:auto">
                          <li v-for="(e, ei) in (detailsCache[detailsKey('income', row.name, `${selectedYear}-${String(i+1).padStart(2,'0')}`)].entries || []).slice(0,8)" :key="ei">
                            {{ fmtDate(e.date) }} · {{ e.description?.slice(0,60) }} · {{ fmt(e.amount) }}
                          </li>
                        </ul>
                      </template>
                      <template v-else>
                        <em>Details konnten nicht geladen werden.</em>
                      </template>
                    </div>
                    <div v-else>
                      <em>Lade Details…</em>
                    </div>
                  </div>
                </v-tooltip>
              </td>
              <td class="text-right font-weight-medium">{{ fmt(row.total) }}</td>
              <td class="text-right" style="width:140px">
                <v-sparkline :model-value="row.values" line-width="2" smooth auto-draw />
              </td>
            </tr>
            <tr v-if="incomeRows.length === 0">
              <td :colspan="MONTHS_SHORT.length + 3" class="text-center text-medium-emphasis">
                Keine Einkünfte für {{ selectedYear }}.
              </td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>

      <v-divider class="my-4" />

      <!-- AUSGABEN -->
      <v-card-text>
        <h3 class="text-h6 mb-2">AUSGABEN</h3>
        <v-table density="comfortable" class="elevation-1">
          <thead>
            <tr>
              <th style="min-width: 220px">Kategorie</th>
              <th v-for="(m, i) in MONTHS_SHORT" :key="'exp-h-'+i" class="text-right">{{ m }}</th>
              <th class="text-right">Jahr</th>
              <th class="text-right">Sparkline</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in expenseRows" :key="'exp-'+row.name">
              <td>{{ row.name }}</td>
              <td v-for="(val, i) in row.values" :key="'exp-v-'+row.name+'-'+i" class="text-right">
                <v-tooltip location="top" max-width="380">
                  <template #activator="{ props }">
                    <span v-bind="props" @mouseenter="loadCellDetails('expense', row.name, `${selectedYear}-${String(i+1).padStart(2,'0')}`)">
                      {{ fmt(val) }}
                    </span>
                  </template>
                  <div style="font-size:12px">
                    <div class="mb-1"><strong>{{ row.name }}</strong> – {{ selectedYear }}-{{ String(i+1).padStart(2,'0') }}</div>
                    <div v-if="detailsCache[detailsKey('expense', row.name, `${selectedYear}-${String(i+1).padStart(2,'0')}`)]">
                      <template v-if="!detailsCache[detailsKey('expense', row.name, `${selectedYear}-${String(i+1).padStart(2,'0')}`)].error">
                        <div class="text-medium-emphasis mb-1">
                          Einträge: {{ detailsCache[detailsKey('expense', row.name, `${selectedYear}-${String(i+1).padStart(2,'0')}`)].count || 0 }} · Summe:
                          {{ fmt(detailsCache[detailsKey('expense', row.name, `${selectedYear}-${String(i+1).padStart(2,'0')}`)].total || 0) }}
                        </div>
                        <ul style="margin:0; padding-left:16px; max-height:160px; overflow:auto">
                          <li v-for="(e, ei) in (detailsCache[detailsKey('expense', row.name, `${selectedYear}-${String(i+1).padStart(2,'0')}`)].entries || []).slice(0,8)" :key="ei">
                            {{ fmtDate(e.date) }} · {{ e.description?.slice(0,60) }} · {{ fmt(e.amount) }}
                          </li>
                        </ul>
                      </template>
                      <template v-else>
                        <em>Details konnten nicht geladen werden.</em>
                      </template>
                    </div>
                    <div v-else>
                      <em>Lade Details…</em>
                    </div>
                  </div>
                </v-tooltip>
              </td>
              <td class="text-right font-weight-medium">{{ fmt(row.total) }}</td>
              <td class="text-right" style="width:140px">
                <v-sparkline :model-value="row.values" line-width="2" smooth auto-draw />
              </td>
            </tr>
            <tr v-if="expenseRows.length === 0">
              <td :colspan="MONTHS_SHORT.length + 3" class="text-center text-medium-emphasis">
                Keine Ausgaben für {{ selectedYear }}.
              </td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import axios from 'axios'
const API_BASE = import.meta.env.VITE_API_BASE || '/api'

// Feste Monatsköpfe (Jan..Dez)
const MONTHS_SHORT = ['JAN','FEB','MRZ','APR','MAI','JUN','JUL','AUG','SEP','OKT','NOV','DEZ']

const loading = ref(false)
const selectedYear = ref(null)

// Rohdaten vom Backend:
const incomes = ref({ months: [], categories: [], data: {} })
const expenses = ref({ months: [], categories: [], data: {} })

const cellLoading = ref(false)
const detailsCache = reactive({}) // key: `${type}|${name}|${ym}` -> { entries, total, count }

function detailsKey(type, name, ym) {
  return `${type}|${name}|${ym}`
}

async function loadCellDetails(type, name, ym) {
  const key = detailsKey(type, name, ym)
  if (detailsCache[key]) return
  cellLoading.value = true
  try {
    const res = await axios.get(`${API_BASE}/transactions/by_month_category`, {
      params: { type: type === 'income' ? 'incomes' : 'expenses', category: name, ym }
    })
    detailsCache[key] = res.data
  } catch (e) {
    detailsCache[key] = { error: true }
    console.error('Details laden fehlgeschlagen:', e)
  } finally {
    cellLoading.value = false
  }
}

// Jahr-Auswahl dynamisch aus den gelieferten months (YYYY-MM)
const yearOptions = computed(() => {
  const years = new Set()
  ;[...(incomes.value.months || []), ...(expenses.value.months || [])].forEach(m => {
    if (typeof m === 'string' && m.length >= 4) years.add(m.slice(0,4))
  })
  const arr = Array.from(years).sort()
  // Setze initiales Jahr, falls noch nicht gesetzt
  if (!selectedYear.value && arr.length) selectedYear.value = arr[arr.length - 1]
  return arr
})

// Hilfsfunktion: Baut für ein Payload (income/expense) Tabellenzeilen für das ausgewählte Jahr
function buildRowsForYear(payload, year, isExpenses = false) {
  const months = payload.months || []
  const idxByMonth = new Map(months.map((ym, i) => [ym, i]))

  return (payload.categories || []).map(cat => {
    // 12 Werte, je YYYY-MM existiert → holen, sonst 0
    const values = Array.from({ length: 12 }, (_, mi) => {
      const ym = `${year}-${String(mi+1).padStart(2,'0')}`
      const idx = idxByMonth.get(ym)
      const v = idx != null ? (payload.data?.[cat]?.[idx] ?? 0) : 0
      return v
    })
    // Für Ausgaben ggf. Negativsummen anzeigen (du hast negative Ausgaben; für Totals wollen wir den „Zahlungsstrom“ zeigen)
    // Wir lassen die Rohwerte so, wie sie vom Backend kommen: Ausgaben negativ, Erstattungen positiv.
    // In der Summe also reale Nettosumme:
    const total = values.reduce((a,b) => a + b, 0)
    return { name: cat, values, total }
  })
}

const incomeRows = computed(() => {
  if (!selectedYear.value) return []
  return buildRowsForYear(incomes.value, selectedYear.value, false)
})

const expenseRows = computed(() => {
  if (!selectedYear.value) return []
  return buildRowsForYear(expenses.value, selectedYear.value, true)
})

// Formatter für € de-DE
const currencyFmt = new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' })
function fmt(n) {
  // Für Ausgaben oft negativ — das ist ok, so siehst du Rückflüsse positiv
  return currencyFmt.format(n || 0)
}

function fmtDate(iso) {
  if (!iso || typeof iso !== 'string') return iso || ''
  if (iso.includes('-')) return iso
  return iso
}

async function loadData() {
  loading.value = true
  try {
    const res = await axios.get(`${API_BASE}/summary_spendings_monthly?type=all`)
    // Struktur: { expenses: {months,categories,data}, incomes: {months,categories,data} }
    expenses.value = res.data.expenses || { months: [], categories: [], data: {} }
    incomes.value  = res.data.incomes  || { months: [], categories: [], data: {} }
    // selectedYear wird durch yearOptions ggf. initial gesetzt
  } catch (e) {
    console.error('Fehler beim Laden der SummaryTable-Daten:', e)
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
</style>