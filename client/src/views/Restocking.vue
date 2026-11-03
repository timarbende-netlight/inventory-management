<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card budget-card">
        <div class="budget-row">
          <label for="budget-slider" class="budget-label">{{ t('restocking.budget') }}</label>
          <span class="budget-value">{{ formatMoney(budget) }}</span>
        </div>
        <input
          id="budget-slider"
          v-model.number="budget"
          type="range"
          min="0"
          max="100000"
          step="1000"
          class="budget-slider"
        />
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.totalCost') }}</div>
          <div class="stat-value">{{ formatMoney(totalCost) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.remaining') }}</div>
          <div class="stat-value">{{ formatMoney(remainingBudget) }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.estimatedDelivery') }}</div>
          <div class="stat-value">{{ t('restocking.days', { count: maxLeadTime }) }}</div>
        </div>
      </div>

      <div v-if="successOrder" class="banner banner-success">
        <span>{{ t('restocking.orderPlaced', { orderNumber: successOrder.order_number }) }}</span>
        <router-link to="/orders" class="banner-link">{{ t('restocking.viewOrders') }}</router-link>
      </div>
      <div v-if="submitError" class="banner banner-error">{{ submitError }}</div>

      <div class="card">
        <div class="card-header header-row">
          <h3 class="card-title">{{ t('restocking.recommended') }} ({{ recommendation.length }})</h3>
          <button
            class="place-btn"
            :disabled="recommendation.length === 0 || submitting"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placing') : t('restocking.placeOrder') }}
          </button>
        </div>
        <div v-if="recommendation.length === 0" class="empty">
          {{ t('restocking.noRecommendations') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.sku') }}</th>
                <th>{{ t('restocking.item') }}</th>
                <th>{{ t('restocking.supplier') }}</th>
                <th class="num">{{ t('restocking.quantity') }}</th>
                <th class="num">{{ t('restocking.unitCost') }}</th>
                <th class="num">{{ t('restocking.lineTotal') }}</th>
                <th class="num">{{ t('restocking.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="line in recommendation" :key="line.item_sku">
                <td><strong>{{ line.item_sku }}</strong></td>
                <td>{{ line.item_name }}</td>
                <td>{{ line.supplier }}</td>
                <td class="num">{{ line.quantity }}</td>
                <td class="num">{{ formatMoney(line.unit_cost, 2) }}</td>
                <td class="num"><strong>{{ formatMoney(line.line_total, 2) }}</strong></td>
                <td class="num">{{ t('restocking.days', { count: line.lead_time_days }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrencyWithDecimals } from '../utils/currency'

const round2 = (n) => Math.round(n * 100) / 100

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency } = useI18n()

    const loading = ref(true)
    const error = ref(null)
    const catalog = ref([])
    const budget = ref(25000) // always USD
    const submitting = ref(false)
    const submitError = ref(null)
    const successOrder = ref(null)

    const formatMoney = (value, decimals = 0) =>
      formatCurrencyWithDecimals(value, currentCurrency.value, decimals)

    const loadCatalog = async () => {
      try {
        loading.value = true
        error.value = null
        catalog.value = await api.getRestockingCatalog()
      } catch (err) {
        error.value = 'Failed to load restocking catalog: ' + err.message
        console.error('Load error:', err)
      } finally {
        loading.value = false
      }
    }

    const recommendation = computed(() => {
      const ranked = catalog.value
        .filter(i => i.trend !== 'decreasing' && i.current_demand > 0)
        .map(i => ({
          ...i,
          growth: (i.forecasted_demand - i.current_demand) / i.current_demand,
          desired: Math.max(i.forecasted_demand - i.quantity_on_hand, 0)
        }))
        .filter(i => i.desired > 0 && i.unit_cost > 0)
        .sort((a, b) => b.growth - a.growth)

      // Priority fill: highest-growth items are filled first. When the remaining
      // budget cannot cover an item's full desired quantity, we buy as many whole
      // units as still fit, so that line (typically the last funded one) may be
      // only partially filled. Cent-rounding keeps the total within budget.
      let remaining = round2(budget.value)
      const lines = []
      for (const item of ranked) {
        let qty = item.desired
        if (round2(qty * item.unit_cost) > remaining) {
          qty = Math.floor(remaining / item.unit_cost)
          while (qty > 0 && round2(qty * item.unit_cost) > remaining) qty--
        }
        if (qty <= 0) continue
        const lineTotal = round2(qty * item.unit_cost)
        remaining = round2(remaining - lineTotal)
        lines.push({
          item_sku: item.item_sku,
          item_name: item.item_name,
          supplier: item.supplier,
          unit_cost: item.unit_cost,
          lead_time_days: item.lead_time_days,
          quantity: qty,
          line_total: lineTotal
        })
      }
      return lines
    })

    const totalCost = computed(() =>
      round2(recommendation.value.reduce((sum, l) => sum + l.line_total, 0))
    )
    const remainingBudget = computed(() => round2(budget.value - totalCost.value))
    const maxLeadTime = computed(() =>
      recommendation.value.reduce((m, l) => Math.max(m, l.lead_time_days), 0)
    )

    const placeOrder = async () => {
      if (recommendation.value.length === 0 || submitting.value) return
      submitting.value = true
      submitError.value = null
      successOrder.value = null
      try {
        successOrder.value = await api.createRestockOrder({
          budget: budget.value,
          items: recommendation.value.map(l => ({ item_sku: l.item_sku, quantity: l.quantity }))
        })
      } catch (err) {
        submitError.value = err.response?.data?.detail || t('restocking.placeFailed')
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadCatalog)

    return {
      t,
      loading,
      error,
      budget,
      recommendation,
      totalCost,
      remainingBudget,
      maxLeadTime,
      submitting,
      submitError,
      successOrder,
      formatMoney,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.5rem;
}

.budget-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.75rem;
}

.budget-label {
  font-weight: 500;
  color: #64748b;
}

.budget-value {
  font-size: 1.5rem;
  font-weight: 600;
  color: #0f172a;
}

.budget-slider {
  width: 100%;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.place-btn {
  background: #0f172a;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1rem;
  font-weight: 500;
  cursor: pointer;
}

.place-btn:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

.num {
  text-align: right;
}

.empty {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}

.banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  border: 1px solid;
}

.banner-success {
  background: #f0fdf4;
  border-color: #86efac;
  color: #166534;
}

.banner-error {
  background: #fef2f2;
  border-color: #fca5a5;
  color: #991b1b;
}

.banner-link {
  color: inherit;
  font-weight: 600;
  text-decoration: underline;
}
</style>
