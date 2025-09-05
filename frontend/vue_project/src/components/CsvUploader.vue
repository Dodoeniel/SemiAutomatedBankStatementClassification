<template>
  <v-card class="pa-4">
    <v-card-title>Bank Statement hochladen</v-card-title>
    <v-card-text>
      <v-radio-group v-model="selectedBank" inline>
        <v-radio label="DKB" value="dkb" > </v-radio>
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

const selectedBank = ref('')
const selectedFile = ref(null)
const loading = ref(false)
const message = ref('')
const error = ref(false)

async function uploadFile() {
  if (!selectedFile.value || !selectedBank.value) return
  loading.value = true
  message.value = ''
  error.value = false

  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    formData.append('bank', selectedBank.value)

    const res = await axios.post('http://localhost:8000/upload-statement', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    message.value = `Erfolgreich hochgeladen: ${res.data.inserted} Einträge`
  } catch (err) {
    error.value = true
    message.value = err.response?.data?.detail || 'Fehler beim Hochladen'
  } finally {
    loading.value = false
  }
}
</script>