<template>
  <v-card class="pa-4">
    <v-card-title>Bank Statement hochladen</v-card-title>
    <v-card-text>
      <v-radio-group v-model="selectedBank" inline>
        <v-radio label="DKB Girokonto" value="dkb" > </v-radio>
        <v-radio label="DKB Kreditkarte" value="dkb_credit"></v-radio>
        <v-radio label="Revolut" value="revolut" > </v-radio>
        <v-radio label="American Express" value="amex" > </v-radio>
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
        :disabled="!selectedFile || !selectedBank"
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

const selectedBank = ref('')
const selectedFile = ref(null)
const loading = ref(false)
const message = ref('')
const error = ref(false)

console.log('VITE_API_BASE:', import.meta.env.VITE_API_BASE);

async function uploadFile() {
  if (!selectedFile.value || !selectedBank.value) return
  loading.value = true
  message.value = ''
  error.value = false

  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    formData.append('bank', selectedBank.value)

    // Ziel-Endpoint je nach Bank
    const endpoint = selectedBank.value === 'dkb_credit'
      ? `${API_BASE}/upload-statement-dkb-credit`
      : `${API_BASE}/upload-statement`

    const res = await axios.post(endpoint, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    message.value = `Erfolgreich hochgeladen: ${res.data.inserted} Einträge`
    selectedFile.value = null
  } catch (err) {
    error.value = true
    message.value = err.response?.data?.detail || 'Fehler beim Hochladen'
  } finally {
    loading.value = false
  }
}
</script>