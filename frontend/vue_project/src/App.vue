<template>
  <v-app>
    <!-- Top Bar -->
    <v-app-bar elevation="1">
      <v-app-bar-title>Bank Statements Dashboard</v-app-bar-title>
      <v-spacer></v-spacer>
      <!-- Theme Toggle (optional, works if Vuetify theme plugin is configured) -->
      <v-btn icon @click="toggleTheme" :title="isDark ? 'Helles Theme' : 'Dunkles Theme'">
        <v-icon>{{ isDark ? 'mdi-white-balance-sunny' : 'mdi-moon-waning-crescent' }}</v-icon>
      </v-btn>
    </v-app-bar>

    <v-main>
      <v-container class="py-6" fluid>
        <!-- Tabs Navigation -->
        <v-card class="mx-auto" max-width="1600">
          <v-tabs v-model="tab" bg-color="transparent" grow>
            <v-tab value="upload">
              <v-icon start>mdi-upload</v-icon>
              Upload
            </v-tab>
            <v-tab value="transactions">
              <v-icon start>mdi-format-list-bulleted</v-icon>
              Transaktionen
            </v-tab>
            <v-tab value="summary">
              <v-icon start>mdi-view-list</v-icon>
              Zusammenfassung
            </v-tab>
            <v-tab value="chart">
              <v-icon start>mdi-chart-bar</v-icon>
              Chart
            </v-tab>
            <v-tab value="monthly">
              <v-icon start>mdi-table</v-icon>
              Monats-Tabelle
            </v-tab>
          </v-tabs>

          <v-divider></v-divider>

          <!-- Tab Content -->
          <v-window v-model="tab" class="pa-4">
            <v-window-item value="upload">
              <v-row>
                <v-col cols="12" md="8" lg="6">
                  <CsvUploader />
                </v-col>
                <v-col cols="12" md="4" lg="6" class="d-flex align-center">
                  <v-alert type="info" variant="tonal" class="w-100">
                    Lade deine DKB/Revolut/Amex Dateien hoch. PDFs werden für AMEX unterstützt.
                  </v-alert>
                </v-col>
              </v-row>
            </v-window-item>

            <v-window-item value="transactions">
              <v-row>
                <v-col cols="12">
                  <TransactionList />
                </v-col>
              </v-row>
            </v-window-item>

            <v-window-item value="summary">
              <v-row>
                <v-col cols="12">
                  <SummarySpendings />
                </v-col>
              </v-row>
            </v-window-item>

            <v-window-item value="chart">
              <v-row>
                <v-col cols="12" xl="10" class="mx-auto">
                  <SummaryChart />
                </v-col>
              </v-row>
            </v-window-item>

            <v-window-item value="monthly">
              <v-row>
                <v-col cols="12">
                  <SummaryMonthlyTable />
                </v-col>
              </v-row>
            </v-window-item>
          </v-window>
        </v-card>
      </v-container>
    </v-main>

    <v-footer app class="justify-center py-3">
      <span class="text-caption">© {{ new Date().getFullYear() }} · Private Budget Tools</span>
    </v-footer>
  </v-app>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useTheme } from 'vuetify'

import TransactionList from './components/TransactionList.vue'
import CsvUploader from './components/CsvUploader.vue'
import SummarySpendings from './components/SummarySpendings.vue'
import SummaryChart from './components/SummaryChart.vue'
import SummaryMonthlyTable from './components/SummaryMonthlyTable.vue'

const tab = ref('upload')

// Optional Theme Toggle (requires Vuetify theme configured in main.js)
const theme = useTheme()
const isDark = computed(() => theme.global.current.value.dark)
function toggleTheme() {
  theme.global.name.value = isDark.value ? 'light' : 'dark'
}
</script>

<style scoped>
/* Leichtes Polishing */
.v-application {
  background-color: rgb(var(--v-theme-background));
}
</style>