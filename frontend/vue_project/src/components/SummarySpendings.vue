<template>
  <v-container>
    <v-card>
      <v-card-title>Zusammenfassung der Ausgaben und Einkünfte</v-card-title>
      <v-card-text>
        <v-expansion-panels>
          <v-expansion-panel v-for="(groups, mainCat) in summary" :key="mainCat">
            <v-expansion-panel-title>{{ mainCat }}</v-expansion-panel-title>
            <v-expansion-panel-text>
              <v-expansion-panels>
                <v-expansion-panel v-for="(subcats, groupName) in groups" :key="groupName">
                  <v-expansion-panel-title>{{ groupName }}</v-expansion-panel-title>
                  <v-expansion-panel-text>
                    <v-list dense>
                      <v-list-group
                        v-for="(data, subcatName) in subcats"
                        :key="subcatName"
                        no-action
                      >
                        <template #activator>
                          <div>
                            <strong>{{ subcatName }}</strong><br />
                            Summe: {{ Number(data.summe).toFixed(2) }} €
                          </div>
                        </template>

                        <v-list-item v-for="(entry, idx) in data.entries" :key="idx">
                          <div>
                            <div>{{ entry.Verwendungszweck }}</div>
                            <div style="font-size: 0.85em; color: gray;">
                              {{ entry.Datum }} — {{ Number(entry.Betrag).toFixed(2) }} €
                            </div>
                          </div>
                        </v-list-item>
                      </v-list-group>
                    </v-list>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup>
import { ref, onMounted, computed} from "vue";
import axios from "axios";
const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const summary = ref({});

async function loadSummary() {
  try {
    const res = await axios.get(`${API_BASE}/summary_spendings`);
    summary.value = res.data;
  } catch (err) {
    console.error("Fehler beim Laden der Summary:", err);
  }
}

onMounted(loadSummary);
</script>