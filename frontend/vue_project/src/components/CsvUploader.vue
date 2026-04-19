<template>
  <v-card class="pa-4">
    <v-card-title>Bank Statement hochladen</v-card-title>
    <v-card-text>
      <v-radio-group v-model="selectedSource" inline>
        <v-radio
          v-for="source in sources"
          :key="source.value"
          :label="source.title"
          :value="source.value"
        />
      </v-radio-group>

      <v-file-input
        label="Datei auswählen (CSV oder PDF)"
        accept=".csv,.pdf"
        prepend-icon="mdi-file-upload"
        show-size
        v-model="selectedFile"
      ></v-file-input>
    </v-card-text>
    <v-card-actions>
      <v-btn
        color="primary"
        :disabled="!selectedFile || !selectedSource"
        @click="uploadFile"
      >
        Hochladen
      </v-btn>
    </v-card-actions>
    <v-progress-linear
      v-if="loading"
      indeterminate
      color="primary"
      class="mb-2"
    ></v-progress-linear>
    <v-alert
      v-if="message"
      :type="error ? 'error' : 'success'"
      dense
      class="mt-2"
    >
      {{ message }}
    </v-alert>
  </v-card>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'
const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const sources = [
  { title: 'DKB Girokonto', value: 'dkb_giro' },
  { title: 'Revolut', value: 'revolut' },
  { title: 'American Express', value: 'amex' },
  { title: 'Deutsche Bank Miles & More', value: 'deutsche_bank_miles_more' },
]

const selectedSource = ref('')
const selectedFile = ref(null)
const loading = ref(false)
const message = ref('')
const error = ref(false)

async function uploadFile() {
  if (!selectedFile.value || !selectedSource.value) return
  loading.value = true
  message.value = ''
  error.value = false

  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    formData.append('source', selectedSource.value)

    const res = await axios.post(`${API_BASE}/v2/upload-statement`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    const data = res.data
    if (data.duplicate_file) {
      message.value = 'Diese Datei wurde bereits importiert. Es wurden keine neuen Transaktionen angelegt.'
    } else {
      message.value = [
        `Gelesen: ${data.parsed}`,
        `Neu: ${data.inserted}`,
        `Klassifiziert: ${data.classified}`,
        `Offen: ${data.unclassified}`,
        `Duplikate: ${data.skipped_duplicates}`,
      ].join(' · ')
    }
    selectedFile.value = null
  } catch (err) {
    error.value = true
    message.value = err.response?.data?.detail || 'Fehler beim Hochladen'
  } finally {
    loading.value = false
  }
}
</script>
