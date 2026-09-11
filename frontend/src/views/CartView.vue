<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const items = ref([])
const total = ref(0)
const loading = ref(true)
const toast = ref('')

function showToast(msg) {
  toast.value = msg
  setTimeout(() => (toast.value = ''), 2200)
}

async function load() {
  loading.value = true
  const r = await api.cart()
  if (r.code === 0) {
    items.value = r.items || []
    total.value = r.total || 0
  }
  loading.value = false
}

async function setQty(it, qty) {
  const r = await api.cartQty(it.code, qty)
  if (r.code === 0) {
    items.value = r.items || []
    total.value = r.total || 0
  }
}

async function remove(it) {
  const r = await api.cartRemove(it.code)
  if (r.code === 0) {
    items.value = r.items || []
    total.value = r.total || 0
    showToast('已移除')
  }
}

async function clearAll() {
  if (!items.value.length) return
  for (const it of [...items.value]) await api.cartRemove(it.code)
  await load()
  showToast('购物车已清空')
}

function checkout() {
  showToast(`演示环境：已模拟结算 ${items.value.length} 种商品，合计 £${total.value.toFixed(2)}`)
}

function openDetail(it) {
  router.push({ name: 'detail', params: { code: it.code } })
}

const priceFmt = (v) => (v == null || v === '' ? '—' : '£' + v)
const subtotal = (it) => ((it.price || 0) * it.qty).toFixed(2)
const allQty = computed(() => items.value.reduce((s, i) => s + i.qty, 0))

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="topbar">
      <button class="back" @click="router.back()">← 返回</button>
      <h1>购物车</h1>
      <span class="cnt" v-if="items.length">共 {{ allQty }} 件</span>
      <button v-if="items.length" class="clear" @click="clearAll">清空购物车</button>
    </div>

    <main class="body">
      <div v-if="loading" class="empty">加载中…</div>
      <div v-else-if="!items.length" class="empty">
        <p>购物车还是空的</p>
        <button class="btn btn-primary" @click="router.push('/home')">去逛逛</button>
      </div>
      <template v-else>
        <div class="list">
          <div v-for="it in items" :key="it.code" class="row">
            <img :src="it.img" alt="" @click="openDetail(it)" />
            <div class="info" @click="openDetail(it)">
              <b>{{ it.cn_name || it.en_name }}</b>
              <i>{{ it.category }}</i>
              <em class="p">{{ priceFmt(it.price) }}</em>
            </div>
            <div class="stepper">
              <button :disabled="it.qty <= 1" @click="setQty(it, it.qty - 1)">−</button>
              <b>{{ it.qty }}</b>
              <button @click="setQty(it, it.qty + 1)">＋</button>
            </div>
            <em class="sub">£{{ subtotal(it) }}</em>
            <button class="rm" @click="remove(it)">删除</button>
          </div>
        </div>

        <div class="settle">
          <div class="s-left">
            共 <b>{{ allQty }}</b> 件商品
          </div>
          <div class="s-right">
            <span class="total">合计：<b>£{{ total.toFixed(2) }}</b></span>
            <button class="pay" @click="checkout">去结算</button>
          </div>
        </div>
      </template>
    </main>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </div>
</template>

<style scoped>
.page { min-height: 100vh; background: #f4f5f7; }
.topbar {
  background: #fff; border-bottom: 2px solid var(--brand);
  display: flex; align-items: center; gap: 16px; padding: 14px 22px;
}
.topbar h1 { font-size: 19px; }
.back {
  font-size: 13px; color: var(--ink-2); background: #fff;
  border: 1px solid #ddd; border-radius: 999px; padding: 7px 16px;
}
.back:hover { color: var(--brand); border-color: var(--brand); }
.cnt { font-size: 12.5px; color: var(--ink-3); }
.clear {
  margin-left: auto; font-size: 12.5px; color: var(--ink-3); background: #fff;
  border: 1px solid var(--line); border-radius: 999px; padding: 7px 14px;
}
.clear:hover { color: #d64545; border-color: #d64545; }
.body { max-width: 990px; margin: 0 auto; padding: 16px; }

.row {
  display: grid; grid-template-columns: 88px 1fr 130px 90px 60px;
  gap: 14px; align-items: center;
  background: #fff; border-radius: 12px; padding: 14px 18px; margin-bottom: 12px;
  box-shadow: 0 0 0 1px rgba(0,0,0,.04);
}
.row img {
  width: 88px; height: 88px; border-radius: 8px; object-fit: cover; background: #f7f7f7; cursor: pointer;
}
.info { cursor: pointer; display: flex; flex-direction: column; gap: 5px; min-width: 0; }
.info b { font-size: 13.5px; font-weight: 400; line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.info i { font-style: normal; font-size: 11.5px; color: var(--ink-3); }
.info .p { font-style: normal; color: var(--accent); font-weight: 700; font-size: 15px; }
.stepper { display: flex; align-items: center; }
.stepper button {
  width: 28px; height: 28px; font-size: 14px; color: var(--ink-2);
  background: #f7f7f7; border: 1px solid #eee;
}
.stepper button:first-child { border-radius: 4px 0 0 4px; }
.stepper button:last-of-type { border-radius: 0 4px 4px 0; border-left: none; }
.stepper button:disabled { color: #ccc; cursor: not-allowed; }
.stepper b {
  width: 40px; height: 28px; display: flex; align-items: center; justify-content: center;
  font-size: 13px; border-top: 1px solid #eee; border-bottom: 1px solid #eee;
}
.sub { font-style: normal; font-weight: 700; color: var(--ink); font-size: 14px; text-align: right; }
.rm {
  font-size: 12px; color: var(--ink-3); background: #fff;
  border: 1px solid var(--line); border-radius: 8px; padding: 6px 0;
}
.rm:hover { color: #d64545; border-color: #d64545; }

.settle {
  position: sticky; bottom: 12px;
  display: flex; align-items: center; justify-content: space-between;
  background: #fff; border-radius: 12px; padding: 14px 20px;
  box-shadow: 0 6px 18px rgba(0,0,0,.1);
}
.s-left { font-size: 13px; color: var(--ink-2); }
.s-left b { color: var(--brand); }
.s-right { display: flex; align-items: center; gap: 16px; }
.total { font-size: 13.5px; color: var(--ink-2); }
.total b { font-size: 22px; color: var(--accent); }
.pay {
  font-size: 15px; font-weight: 700; color: #fff;
  background: linear-gradient(90deg, #ff7a00, #ff2050);
  border-radius: 999px; padding: 11px 38px;
}
.pay:hover { filter: brightness(1.05); }

.empty { text-align: center; padding: 90px 0; color: var(--ink-3); }
.empty p { margin-bottom: 14px; font-size: 14px; }
@media (max-width: 760px) {
  .row { grid-template-columns: 72px 1fr 110px 70px; }
  .row .rm { display: none; }
}
</style>
