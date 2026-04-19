<template>
  <v-container>
    <v-card>
      <v-card-title class="d-flex align-center">
        Zusammenfassung
        <v-spacer />
        <v-btn color="primary" :loading="loading" :disabled="loading" @click="loadSummary">Neu laden</v-btn>
      </v-card-title>
      <v-card-text>
        <v-row class="mb-4">
          <v-col cols="12" md="4">
            <v-alert type="info" variant="tonal">
              Offen: {{ summary.unclassified?.total || 0 }} Transaktionen
            </v-alert>
          </v-col>
        </v-row>

        <v-expansion-panels>
          <v-expansion-panel v-for="section in sections" :key="section.key">
            <v-expansion-panel-title>{{ section.title }}</v-expansion-panel-title>
            <v-expansion-panel-text>
              <v-expansion-panels>
                <v-expansion-panel v-for="group in section.groups" :key="group.group">
                  <v-expansion-panel-title>
                    {{ group.group }} · {{ fmt(group.display_total) }}
                  </v-expansion-panel-title>
                  <v-expansion-panel-text>
                    <v-list density="compact">
                      <v-list-group
                        v-for="item in group.categories"
                        :key="item.category.key"
                      >
                        <template #activator="{ props }">
                          <v-list-item v-bind="props">
                            <v-list-item-title>{{ item.category.name }}</v-list-item-title>
                            <v-list-item-subtitle>
                              {{ item.count }} Einträge · {{ fmt(item.display_total) }}
                            </v-list-item-subtitle>
                          </v-list-item>
                        </template>

                        <v-list-item v-for="entry in item.entries.slice(0, 20)" :key="entry.id">
                          <v-list-item-title>{{ entry.description }}</v-list-item-title>
                          <v-list-item-subtitle>
                            {{ entry.value_date || entry.booking_date }} · {{ fmt(entry.display_amount) }} · {{ entry.source }}
                          </v-list-item-subtitle>
                        </v-list-item>
                      </v-list-group>
                    </v-list>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>

        <v-card v-if="summary.unclassified?.buckets?.length" variant="outlined" class="mt-4">
          <v-card-title>Offene Klassifikationen</v-card-title>
          <v-table density="compact">
            <thead>
              <tr>
                <th>Budget-Monat</th>
                <th>Quelle</th>
                <th class="text-right">Anzahl</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="bucket in summary.unclassified.buckets" :key="`${bucket.budget_month}-${bucket.source}`">
                <td>{{ bucket.budget_month || 'ohne Monat' }}</td>
                <td>{{ bucket.source }}</td>
                <td class="text-right">{{ bucket.count }}</td>
              </tr>
            </tbody>
          </v-table>
        </v-card>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const loading = ref(false)
const summary = ref({ income: [], expense: [], unclassified: { total: 0, buckets: [] } })

const sections = computed(() => [
  { key: 'expense', title: 'Ausgaben', groups: summary.value.expense || [] },
  { key: 'income', title: 'Einnahmen', groups: summary.value.income || [] },
])

const currencyFmt = new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' })
function fmt(value) {
  return currencyFmt.format(Number(value || 0))
}

async function loadSummary() {
  loading.value = true
  try {
    const res = await axios.get(`${API_BASE}/v2/analytics/summary`)
    summary.value = res.data
  } catch (err) {
    console.error('Fehler beim Laden der Summary:', err)
  } finally {
    loading.value = false
  }
}

onMounted(loadSummary)
</script>
