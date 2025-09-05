<template>
  <v-container>
    <v-card>
      <v-card-title class="d-flex align-center flex-wrap">
        <span class="text-h6">Transaktionen</span>
        <v-spacer></v-spacer>

        <!-- Filterleiste -->
        <v-select
          class="mr-2"
          density="comfortable"
          hide-details="auto"
          style="max-width: 140px"
          :items="yearOptions"
          v-model="filters.year"
          label="Jahr"
          clearable
          @update:modelValue="scheduleLoad"
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
          @update:modelValue="scheduleLoad"
        />
        <v-select
          class="mr-2"
          density="comfortable"
          hide-details="auto"
          style="max-width: 190px"
          :items="classifiedOptions"
          v-model="filters.classified"
          label="Status"
          @update:modelValue="scheduleLoad"
        />
        <v-btn color="primary" :loading="loading" :disabled="loading" @click="load">Neu laden</v-btn>
      </v-card-title>

      <v-data-table
        :headers="headers"
        :items="transactions"
        :items-per-page="15"
        class="elevation-1"
      >
        <template #item.betrag="{ item }">
          {{ formatCurrency(item.betrag) }}
        </template>

        <template #item.status="{ item }">
          <v-chip :color="rowClassified(item) ? 'success' : 'warning'" size="small" variant="elevated">
            {{ rowClassified(item) ? 'klassifiziert' : 'unklassifiziert' }}
          </v-chip>
        </template>

        <template #item.category="{ item }">
          <v-select
            :items="categoryNames"
            v-model="selections[item.id].category"
            label="Kategorie"
            outlined
            hide-details="auto"
            density="comfortable"
            style="min-width: 200px"
            @update:modelValue="val => onCategoryChange(item.id, val)"
          />
        </template>

        <template #item.subcategory="{ item }">
          <v-select
            :items="subOptions(item.id).map(s => s.name)"
            v-model="selections[item.id].subcategory"
            label="Subkategorie"
            outlined
            hide-details="auto"
            density="comfortable"
            style="min-width: 200px"
          />
        </template>

        <template #item.actions="{ item }">
          <v-btn-group>
            <v-btn size="small" color="success" @click="saveClassification(item.id)">Speichern</v-btn>
            <v-btn size="small" color="secondary" @click="addKeywordFromTx(item.id)">Keyword</v-btn>
            <v-btn size="small" color="error" @click="deleteTransaction(item.id)">Löschen</v-btn>
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
const categories = reactive({ AUSGABEN: {}, EINKOMMEN: {} })
const selections = reactive({})

const headers = [
  { text: 'Datum', value: 'buchungsdatum' },
  { text: 'Empfänger', value: 'zahlungsempfaenger' },
  { text: 'Verwendungszweck', value: 'verwendungszweck' },
  { text: 'Betrag', value: 'betrag', align: 'end' },
  { text: 'Status', value: 'status' },
  { text: 'Kategorie', value: 'category' },
  { text: 'Subkategorie', value: 'subcategory' },
  { text: 'Aktionen', value: 'actions', sortable: false },
]

const classifiedOptions = [
  { title: 'Alle', value: 'all' },
  { title: 'Klassifiziert', value: 'classified' },
  { title: 'Unklassifiziert', value: 'unclassified' },
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

const filters = reactive({ year: null, month: null, classified: 'all' })

const yearOptions = computed(() => {
  const s = new Set()
  transactions.value.forEach(t => {
    const y = (t.buchungsdatum || '').slice(0, 4)
    if (/^\d{4}$/.test(y)) s.add(y)
  })
  // Fallback: auch aus Backend aggregierten Jahren holen (optional)
  return Array.from(s).sort()
})

const categoryNames = computed(() => Object.keys(categories.AUSGABEN || {}))

function isSetCategory(v) {
  if (v === null || v === undefined) return false
  const s = String(v).trim()
  if (s === '') return false
  if (s.toLowerCase() === 'nan') return false
  return true
}

function rowClassified(t) {
  if (isSetCategory(t?.cat_id)) return true
  if (isSetCategory(t?.final_category)) return true
  if (isSetCategory(t?.category_verwendungszweck)) return true
  if (isSetCategory(t?.category_empfaenger)) return true
  if (isSetCategory(t?.category_pflichtig)) return true
  return false
}

function formatCurrency(val) {
  const num = typeof val === 'number' ? val : parseFloat(String(val).replace(',', '.'))
  if (isNaN(num)) return '—'
  return num.toLocaleString('de-DE', { style: 'currency', currency: 'EUR' })
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    // Kategorien laden
    const catsRes = await axios.get(`${API_BASE}/categories`)
    Object.assign(categories, catsRes.data)

    // Versuche neuen All-Transactions-Endpoint mit Filtern
    const params = {}
    if (filters.year) params.year = filters.year
    if (filters.month) params.month = filters.month
    if (filters.classified && filters.classified !== 'all') params.classified = filters.classified

    let txRes
    try {
      txRes = await axios.get(`${API_BASE}/transactions`, { params })
    } catch (e) {
      // Fallback auf bestehenden Unclassified-Endpoint, wenn 404
      if (filters.classified === 'unclassified') {
        txRes = await axios.get(`${API_BASE}/transactions/unclassified`)
      } else {
        throw e
      }
    }

    transactions.value = txRes.data.transactions || txRes.data || []

    // Selections initialisieren (auch für bereits klassifizierte)
    transactions.value.forEach(tx => {
      const { cat, sub } = resolveCurrentCategory(tx)
      selections[tx.id] = { category: cat, subcategory: sub }
    })
  } catch (err) {
    console.error('Fehler beim Laden:', err)
    errorMsg.value = 'Konnte Transaktionen nicht laden.'
  } finally {
    loading.value = false
  }
}

function resolveCurrentCategory(tx) {
  const id = tx.cat_id ?? tx.final_category ?? tx.category_verwendungszweck ?? tx.category_empfaenger ?? tx.category_pflichtig
  if (!id) return { cat: '', sub: '' }
  const { catName, subName } = findCatAndSubById(id)
  return { cat: catName || '', sub: subName || '' }
}

function findCatAndSubById(idInput) {
  const idStr = String(idInput).trim()
  const idNum = /^-?\d+$/.test(idStr) ? Number(idStr) : null

  const match = (sub) => {
    const sIdStr = String(sub.id).trim()
    if (idNum !== null) {
      const sIdNum = /^-?\d+$/.test(sIdStr) ? Number(sIdStr) : null
      if (sIdNum !== null && sIdNum === idNum) return true
    }
    return sIdStr === idStr
  }

  for (const [catName, subs] of Object.entries(categories.AUSGABEN || {})) {
    const found = subs.find(match)
    if (found) return { catName, subName: found.name }
  }
  for (const [catName, subs] of Object.entries(categories.EINKOMMEN || {})) {
    const found = subs.find(match)
    if (found) return { catName, subName: found.name }
  }
  return { catName: '', subName: '' }
}

function subOptions(txId) {
  const cat = selections[txId]?.category
  if (!cat || !categories.AUSGABEN[cat]) return []
  return categories.AUSGABEN[cat]
}

async function saveClassification(txId) {
  const sel = selections[txId]
  const sub = subOptions(txId).find(s => s.name === sel.subcategory)
  if (!sub) {
    alert('Bitte Subkategorie wählen')
    return
  }
  try {
    await axios.post(`${API_BASE}/transactions/classify`, {
      transaction_id: txId,
      category_type: 'verwendungszweck',
      category_id: String(sub.id),
    })
    // Nach dem Speichern Status im UI behalten (nicht entfernen), aber selections neu setzen
    const tx = transactions.value.find(t => t.id === txId)
    if (tx) {
      tx.category_verwendungszweck = String(sub.id)
      tx.cat_id = String(sub.id)
    }
  } catch (e) {
    console.error('Fehler beim Speichern:', e)
    alert('Konnte Klassifizierung nicht speichern')
  }
}

async function addKeywordFromTx(txId) {
  const tx = transactions.value.find(t => t.id === txId)
  const kw = prompt('Keyword eingeben:', tx?.verwendungszweck || '')
  if (!kw) return
  const sel = selections[txId]
  const sub = subOptions(txId).find(s => s.name === sel.subcategory)
  try {
    await axios.post(`${API_BASE}/keywords`, {
      keyword: kw,
      category: 'AUSGABEN',
      subcategory: sel.category || '',
      id: sub ? String(sub.id) : '0',
    })
    alert('Keyword hinzugefügt')
  } catch (e) {
    console.error('Fehler beim Hinzufügen des Keywords:', e)
    alert('Konnte Keyword nicht hinzufügen')
  }
}

async function deleteTransaction(txId) {
  try {
    await axios.delete(`${API_BASE}/transactions/${txId}`)
    transactions.value = transactions.value.filter(t => t.id !== txId)
    delete selections[txId]
  } catch (error) {
    console.error('Fehler beim Löschen der Transaktion:', error)
    alert('Fehler beim Löschen der Transaktion')
  }
}

onMounted(load)

let reloadTimer = null
function scheduleLoad() {
  if (reloadTimer) clearTimeout(reloadTimer)
  reloadTimer = setTimeout(() => {
    load()
  }, 250)
}

// Falls der Browser/Autocomplete den v-select-Wert ohne update-Event setzt
watch(() => filters.year, () => scheduleLoad())
watch(() => filters.month, () => scheduleLoad())
watch(() => filters.classified, () => scheduleLoad())

function onCategoryChange(txId, val) {
  if (!selections[txId]) selections[txId] = { category: '', subcategory: '' }
  selections[txId].category = val
  selections[txId].subcategory = ''
}
</script>