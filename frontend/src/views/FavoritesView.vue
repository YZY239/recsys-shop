<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ProductCard from '../components/ProductCard.vue'
import { api } from '../api'

const router = useRouter()
const items = ref([])
const loading = ref(true)
const toast = ref('')

function showToast(msg) {
  toast.value = msg
  setTimeout(() => (toast.value = ''), 2200)
}

async function load() {
  loading.value = true
  const r = await api.favorites()
  if (r.code === 0) items.value = r.items || []
  loading.value = false
}

async function removeFav(code) {
  const r = await api.favToggle(code)
  if (r.code === 0) {
    items.value = items.value.filter((i) => i.code !== code)
    showToast(r.msg)
  }
}

function openDetail(it) {
  router.push({ name: 'detail', params: { code: it.code } })
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="topbar">
      <button class="back" @click="router.back()">← 返回</button>
      <h1>我的收藏</h1>
      <span class="cnt" v-if="items.length">{{ items.length }} 件好物</span>
    </div>

    <main class="body">
      <div v-if="loading" class="empty">加载中…</div>
      <div v-else-if="!items.length" class="empty">
        <p>还没有收藏任何商品</p>
        <button class="btn btn-primary" @click="router.push('/home')">去逛逛</button>
      </div>
      <div v-else class="grid">
        <div v-for="it in items" :key="it.code" class="cell">
          <ProductCard :item="it" @click="openDetail(it)" />
          <button class="rm" @click.stop="removeFav(it.code)">取消收藏</button>
        </div>
      </div>
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
.body { max-width: 1190px; margin: 0 auto; padding: 16px; }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.cell { display: flex; flex-direction: column; gap: 6px; }
.rm {
  font-size: 12px; color: var(--ink-3); background: #fff;
  border: 1px solid var(--line); border-radius: 8px; padding: 7px 0;
}
.rm:hover { color: #d64545; border-color: #d64545; }
.empty { text-align: center; padding: 90px 0; color: var(--ink-3); }
.empty p { margin-bottom: 14px; font-size: 14px; }
@media (max-width: 1000px) { .grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 760px) { .grid { grid-template-columns: repeat(2, 1fr); } }
</style>
