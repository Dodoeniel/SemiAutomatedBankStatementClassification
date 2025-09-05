<template>
  <v-container>
    <v-card>
    <v-card-title>
    Monatsübersicht
    <v-spacer />
    <v-btn-toggle v-model="viewType" density="comfortable" class="mr-3">
        <v-btn value="all">Alle</v-btn>
        <v-btn value="expenses">Ausgaben</v-btn>
        <v-btn value="incomes">Einkünfte</v-btn>
    </v-btn-toggle>
    <v-btn color="primary" :loading="loading" :disabled="loading" @click="loadChartData">Neu laden</v-btn>
    </v-card-title>
      <v-card-text>
        <div v-if="chartData">
          <Bar :key="viewType" :data="chartData" :options="chartOptions" />
        </div>
        <div v-else>
          Lade Daten...
        </div>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup>
import axios from 'axios'
const API_BASE = import.meta.env.VITE_API_BASE || '/api'
import { ref, onMounted, watch } from 'vue'
import { Bar } from 'vue-chartjs'
import { Chart, BarController, BarElement, CategoryScale, LinearScale, Tooltip, Legend } from 'chart.js'
Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip, Legend)

const loading = ref(false)
const viewType = ref('all')     // 'all' | 'expenses' | 'incomes'
const chartData = ref(null)
const chartOptions = {
  responsive: true,
  scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } },
  plugins: { legend: { position: 'bottom' } }
}

async function loadChartData() {
  loading.value = true
  try {
    const res = await axios.get(`${API_BASE}/summary_spendings_monthly?type=${viewType.value}`)
    let payload
    if (viewType.value === 'expenses') payload = res.data.expenses
    else if (viewType.value === 'incomes') payload = res.data.incomes
    else {
      // ‚all‘: beide zusammen in einen Chart mergen
      const exp = res.data.expenses || { months: [], categories: [], data: {} }
      const inc = res.data.incomes  || { months: [], categories: [], data: {} }

      // Monate vereinheitlichen (Union), sortiert
      const monthsSet = new Set([...(exp.months || []), ...(inc.months || [])])
      const months = Array.from(monthsSet).sort()

      // Hilfsfunktion: mappt eine Serie auf die vereinheitlichten Monate
      const remapSeries = (payload, arr) => {
        return months.map(m => {
          const idx = (payload.months || []).indexOf(m)
          return idx >= 0 ? (arr[idx] || 0) : 0
        })
      }

      const datasets = []

      if (exp.categories && exp.categories.length) {
        exp.categories.forEach((cat, i) => {
          const arr = exp.data[cat] || []
          datasets.push({
            label: `Ausgaben · ${cat}`,
            data: remapSeries(exp, arr),
            backgroundColor: `hsl(${(i * 40) % 360}, 70%, 55%)`
          })
        })
      }

      if (inc.categories && inc.categories.length) {
        inc.categories.forEach((cat, i) => {
          const arr = inc.data[cat] || []
          datasets.push({
            label: `Einkünfte · ${cat}`,
            data: remapSeries(inc, arr),
            backgroundColor: `hsl(${(i * 40 + 200) % 360}, 70%, 45%)`
          })
        })
      }

      chartData.value = { labels: months, datasets }
      return
    }

    // expenses ODER incomes einzeln zeichnen
    const { categories = [], months = [], data = {} } = payload || {}
    const datasets = categories.map((cat, i) => ({
      label: cat,
      data: data[cat] || Array(months.length).fill(0),
      backgroundColor: `hsl(${(i * 40) % 360}, 70%, 55%)`
    }))
    chartData.value = { labels: months, datasets }

  } catch (e) {
    console.error('Fehler beim Laden der Chart-Daten:', e)
  } finally {
    loading.value = false
  }
}

onMounted(loadChartData)
watch(viewType, () => {
  loadChartData()
})
</script>