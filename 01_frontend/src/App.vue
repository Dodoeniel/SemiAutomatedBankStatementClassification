<template>
  <v-app>
    <v-main>
      <v-container>
        <CsvUploader />
        <TransactionList />
        <SummarySpendings />
        <SummaryChart />
        <SummaryMonthlyTable />
      </v-container>
    </v-main>
  </v-app>
</template>


<script setup>
// Importiere die Komponente aus deinem components-Ordner
import TransactionList from './components/TransactionList.vue'
import CsvUploader from './components/CsvUploader.vue'
import SummarySpendings from "./components/SummarySpendings.vue";
import SummaryChart from "./components/SummaryChart.vue";
import SummaryMonthlyTable from "./components/SummaryMonthlyTable.vue";
</script>

<style>
/* Optionales globales Styling */
#app {
  font-family: Arial, sans-serif;
  margin: 20px;
}
</style>