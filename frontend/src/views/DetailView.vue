<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, getUser, setUser } from '../api'

const route = useRoute()
const router = useRouter()

const item = ref(null)
const sims = ref([])
const loading = ref(true)
const toast = ref('')

// SKU / 数量 / 收藏（收藏为真实存储，购物车为真实存储）
const qty = ref(1)
const skuList = ['标准装', '礼盒装', '促销特价']
const activeSku = ref(0)
const faved = ref(false)

function showToast(msg) {
  toast.value = msg
  setTimeout(() => (toast.value = ''), 2400)
}

// 淘宝式价格排版：整数大、小数小
const price = computed(() => {
  const v = item.value?.price
  if (v == null || v === '') return null
  const [int, dec] = String(v).split('.')
  return { int, dec: dec ? '.' + dec : '' }
})

// 由商品编号稳定推导"已售/评价"演示数字（同一商品刷新后不变）
const sold = computed(() => {
  if (!item.value?.code) return null
  let h = 0
  for (const ch of String(item.value.code)) h = (h * 31 + ch.charCodeAt(0)) % 9973
  return 600 + h % 9400
})
const rating = computed(() => '4.' + (6 + (Number(String(item.value?.code || '0').replace(/\D/g, '').slice(-1) || '0')) % 4))

async function load(code) {
  loading.value = true
  const [d, s, f] = await Promise.all([
    api.item(code),
    api.similar(code, 4),
    api.favStatus(code).catch(() => null)
  ])
  if (d.code === 0) item.value = d.item
  if (s.code === 0) sims.value = (s.items || []).map((x) => ({ ...x, img: x.img }))
  if (f && f.code === 0) faved.value = !!f.favorited
  loading.value = false
}

// 收藏（真实落库）
async function toggleFav() {
  const r = await api.favToggle(item.value.code)
  if (r.code === 0) {
    faved.value = r.favorited
    showToast(r.msg)
  } else {
    showToast(r.msg || '操作失败')
  }
}

// 加入购物车（真实落库）
async function addCart() {
  const r = await api.cartAdd(item.value.code, qty.value)
  if (r.code === 0) {
    showToast(`已加入购物车：${item.value.cn_name} × ${qty.value}（共 ${r.count} 件）`)
  } else {
    showToast(r.msg || '加购失败')
  }
}

async function onSimClick(sim) {
  try {
    const r = await api.behavior(sim.code)
    if (r.code === 0 && r.inserted && r.inserted.length) {
      sessionStorage.setItem('recsys_inserted', JSON.stringify({
        from: sim.cn_name, items: r.inserted
      }))
    }
  } catch (e) { /* ignore */ }
  // 跳转到该相似商品详情（复用详情页）
  router.push({ name: 'detail', params: { code: sim.code } })
}

function goBack() {
  // 优先浏览器返回：回到进入详情页前的位置（滚动位置由首页 keep-alive 保持）
  if (window.history.state && window.history.state.back) {
    router.back()
  } else {
    router.push({ name: 'home' })
  }
}

function buy() {
  showToast(`演示环境：已模拟下单（${skuList[activeSku.value]} × ${qty.value}）`)
}

// 详情页被复用（点击相似商品跳转）时重新加载
watch(() => route.params.code, (code) => { if (code && route.name === 'detail') load(code) })

onMounted(async () => {
  await load(route.params.code)
})
</script>

<template>
  <div class="detail">
    <!-- 顶部导航（淘宝式：左 Logo + 面包屑 + 右搜索框） -->
    <div class="d-mast">
      <div class="d-mast-inner">
        <span class="d-logo">暖物集<small>nuanwuji.com</small></span>
        <span class="d-crumb">商品详情</span>
        <button class="d-back" @click="goBack">← 返回首页</button>
      </div>
    </div>

    <main class="d-page">
      <section v-if="item" class="main">
        <!-- 左：缩略图列 + 商品大图（淘宝式竖排缩略图） -->
        <div class="gallery">
          <div class="thumbs">
            <button class="thumb on"><img :src="item.img" alt="" /></button>
            <button class="thumb more" @click="showToast('演示商品：仅一张主图')">+{{ (sold || 0) % 4 + 2 }}</button>
          </div>
          <div class="photo">
            <img :src="item.img" :alt="item.cn_name" />
            <div class="photo-ops"><span>图集</span><span>参数</span></div>
          </div>
        </div>

        <!-- 右：购买信息区（淘宝详情版式） -->
        <div class="info">
          <!-- 店铺信息条 -->
          <div class="shop-row">
            <span class="shop-name">暖物集自营旗舰店</span>
            <span class="shop-meta">★★★★{{ rating.slice(-1) }} {{ rating }} 好评率99%</span>
            <span class="shop-btns"><a @click="showToast('演示入口：客服')">💬 客服</a><a @click="goBack">🏪 进店</a></span>
          </div>

          <h1 class="title">{{ item.cn_name }}</h1>
          <p class="subtitle">{{ item.category || '家居好物' }} · 已售 {{ sold }}+ · 回头客 700+ 人</p>

          <!-- 促销价块（红色渐变，淘宝"店铺优惠后"版式） -->
          <div class="promo-box">
            <div class="price-line">
              <span class="p-label">店铺优惠后</span>
              <span v-if="price" class="price"><i>£</i><b>{{ price.int }}</b><i v-if="price.dec">{{ price.dec }}</i></span>
              <span v-else class="price"><b>价格面议</b></span>
              <span class="p-tag">超级立减 · 全场立减</span>
            </div>
            <div class="promo-sub">
              <span>已领优惠 · 立减 £{{ (Number(item.price || 0) * 0.05).toFixed(2) }}</span>
              <span>可再享 · 满2件9.5折</span>
            </div>
          </div>

          <!-- 配送 / 服务信息行 -->
          <div class="kv"><span class="k">配送</span><em>预计明天发货 · 承诺48小时内发货 · 快速退货</em></div>
          <div class="kv"><span class="k">保障</span><em>退货宝 · 7天无理由退换 · 极速退款</em></div>

          <!-- SKU：规格分类（淘宝"颜色分类"版式） -->
          <div class="kv sku-kv">
            <span class="k">规格分类</span>
            <div class="skus">
              <button v-for="(s, i) in skuList" :key="s" class="sku" :class="{ on: activeSku === i }" @click="activeSku = i">
                【{{ s }}】 {{ item.category }}
              </button>
            </div>
          </div>

          <!-- 数量步进器 -->
          <div class="kv">
            <span class="k">数量</span>
            <div class="stepper">
              <button :disabled="qty <= 1" @click="qty--">−</button>
              <b>{{ qty }}</b>
              <button @click="qty++">＋</button>
              <span class="stock">有货</span>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="actions">
            <button class="buy" @click="buy">立即购买</button>
            <button class="cart" @click="addCart">加入购物车</button>
          </div>

          <!-- 服务保障 -->
          <div class="services">
            <span>✓ 正品保障</span><span>✓ 极速退款</span><span>✓ 七天无理由</span><span>✓ 免费退货</span>
          </div>
        </div>
      </section>

      <!-- 相似商品推荐（对应淘宝"看了又看 / 本店推荐"） -->
      <section v-if="sims.length" class="sim-sec">
        <div class="sim-head">
          <h2><span class="heart">♥</span>相似商品推荐</h2>
          <p>与「{{ item?.cn_name }}」相似的好物 · 点击后返回首页会随机混入你的推荐流</p>
        </div>
        <div class="sim-grid">
          <button v-for="s in sims" :key="s.code" class="sim-card" @click="onSimClick(s)">
            <img :src="s.img" :alt="s.cn_name" />
            <div class="sim-body">
              <b>{{ s.cn_name }}</b>
              <em><span class="p">£{{ s.price != null && s.price !== '' ? s.price : '—' }}</span><span class="s">相似 {{ s.sim }}%</span></em>
            </div>
          </button>
        </div>
      </section>

      <div v-if="loading" class="loading">加载中…</div>

      <!-- 底部固定购买栏（淘宝式：页签 + 领券购买） -->
      <div v-if="item" class="buy-bar">
        <div class="bb-tabs">
          <a class="on">用户评价</a>
          <a>参数信息</a>
          <a>图文详情</a>
          <a @click="showToast('「本店推荐」即下方相似商品推荐')">本店推荐</a>
          <a @click="showToast('「看了又看」即下方相似商品推荐')">看了又看</a>
        </div>
        <div class="bb-acts">
          <button class="bb-fav" :class="{ on: faved }" @click="toggleFav">
            {{ faved ? '★' : '☆' }}<i>收藏</i>
          </button>
          <button class="bb-cart" @click="addCart">🛒 加入购物车</button>
          <button class="bb-buy" @click="buy">领券购买</button>
        </div>
      </div>

      <div v-if="toast" class="toast">{{ toast }}</div>
    </main>
  </div>
</template>

<style scoped>
/* ---------- 顶部导航 ---------- */
.d-mast { background: #fff; border-bottom: 2px solid var(--brand); }
.d-mast-inner {
  max-width: 1190px; margin: 0 auto; padding: 14px 16px;
  display: flex; align-items: center; gap: 18px;
}
.d-logo { font-size: 24px; font-weight: 800; color: var(--brand); line-height: 1; }
.d-logo small { display: block; font-size: 10px; font-weight: 400; color: var(--ink-3); margin-top: 3px; letter-spacing: 1px; }
.d-crumb { font-size: 15px; color: var(--ink-2); }
.d-back {
  margin-left: auto; font-size: 13px; color: var(--ink-2);
  padding: 7px 16px; border-radius: 999px; border: 1px solid #ddd; background: #fff;
}
.d-back:hover { color: var(--brand); border-color: var(--brand); }

.d-page { max-width: 1190px; margin: 0 auto; padding: 16px 16px 96px; }

/* ---------- 商品主区 ---------- */
.main {
  display: grid; grid-template-columns: 460px 1fr; gap: 26px;
  background: #fff; border-radius: 12px; padding: 24px;
  box-shadow: 0 0 0 1px rgba(0,0,0,.04);
}
/* 左：竖排缩略图 + 大图 */
.gallery { display: grid; grid-template-columns: 56px 1fr; gap: 12px; align-items: start; }
.thumbs { display: flex; flex-direction: column; gap: 8px; }
.thumb {
  width: 56px; height: 56px; border-radius: 6px; overflow: hidden; padding: 0;
  border: 2px solid transparent; background: #f7f7f7; cursor: pointer;
}
.thumb img { width: 100%; height: 100%; object-fit: cover; }
.thumb.on { border-color: var(--brand); }
.thumb.more {
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700; color: var(--ink-3); background: #f7f7f7;
}
.photo { position: relative; border-radius: 8px; overflow: hidden; aspect-ratio: 1/1; background: #f7f7f7; border: 1px solid #f0f0f0; }
.photo img { width: 100%; height: 100%; object-fit: cover; }
.photo-ops {
  position: absolute; left: 50%; bottom: 12px; transform: translateX(-50%);
  display: flex; gap: 8px;
}
.photo-ops span {
  font-size: 12px; color: var(--ink-2); background: rgba(255,255,255,.92);
  border-radius: 999px; padding: 4px 16px; box-shadow: var(--shadow-sm);
}

/* 右：信息区 */
.info { display: flex; flex-direction: column; gap: 13px; padding-top: 2px; }
.shop-row { display: flex; align-items: center; gap: 12px; font-size: 12.5px; }
.shop-name { font-weight: 700; color: var(--ink); }
.shop-meta { color: var(--gold); }
.shop-btns { margin-left: auto; display: flex; gap: 8px; }
.shop-btns a {
  font-size: 12px; color: var(--ink-2); border: 1px solid #ddd;
  border-radius: 999px; padding: 4px 12px; cursor: pointer;
}
.shop-btns a:hover { color: var(--brand); border-color: var(--brand); }

.title { font-size: 17px; font-weight: 700; line-height: 1.5; color: var(--ink); }
.subtitle { color: var(--ink-3); font-size: 12.5px; }

/* 促销价块（红色渐变，淘宝"店铺优惠后"） */
.promo-box {
  background: linear-gradient(100deg, #ff2050 0%, #ff4d2e 100%);
  border-radius: 8px; padding: 14px 18px; color: #fff;
}
.price-line { display: flex; align-items: baseline; gap: 10px; }
.p-label { font-size: 12px; opacity: .9; }
.price { font-weight: 700; }
.price i { font-style: normal; font-size: 15px; }
.price b { font-size: 32px; letter-spacing: -.5px; }
.p-tag {
  margin-left: auto; font-size: 12px; font-weight: 700;
  background: rgba(255,255,255,.2); border: 1px solid rgba(255,255,255,.55);
  border-radius: 4px; padding: 3px 10px;
}
.promo-sub { margin-top: 8px; display: flex; gap: 18px; font-size: 12px; opacity: .95; }

/* 信息行 */
.kv { display: flex; align-items: baseline; gap: 16px; font-size: 13px; padding: 2px 0; }
.kv .k { color: var(--ink-3); flex: none; width: 56px; }
.kv em { font-style: normal; color: var(--ink); }

/* SKU 选择 */
.sku-kv { align-items: flex-start; }
.skus { display: flex; flex-wrap: wrap; gap: 8px; }
.sku {
  font-size: 12.5px; color: var(--ink-2); background: #f7f7f7;
  border: 1px solid #eee; border-radius: 4px; padding: 6px 12px; transition: .15s;
}
.sku:hover { border-color: var(--brand); color: var(--brand); }
.sku.on { color: var(--brand); border-color: var(--brand); background: var(--brand-soft); font-weight: 600; }

/* 数量步进器 */
.stepper { display: flex; align-items: center; gap: 0; }
.stepper button {
  width: 30px; height: 30px; font-size: 15px; color: var(--ink-2);
  background: #f7f7f7; border: 1px solid #eee;
}
.stepper button:first-child { border-radius: 4px 0 0 4px; }
.stepper button:last-of-type { border-radius: 0 4px 4px 0; border-left: none; }
.stepper button:disabled { color: #ccc; cursor: not-allowed; }
.stepper b {
  width: 46px; height: 30px; display: flex; align-items: center; justify-content: center;
  font-size: 13.5px; border-top: 1px solid #eee; border-bottom: 1px solid #eee;
}
.stock { margin-left: 12px; font-size: 12px; color: var(--ink-3); }

/* 操作按钮 */
.actions { display: flex; gap: 12px; margin-top: 6px; }
.buy, .cart {
  flex: none; min-width: 170px; padding: 13px 30px; font-size: 15px; font-weight: 700;
  border-radius: 999px; color: #fff; transition: .18s;
}
.buy { background: linear-gradient(90deg, #ff6000, #ff2050); }
.cart { background: linear-gradient(90deg, var(--gold), #ffb422); }
.buy:hover, .cart:hover { filter: brightness(1.06); transform: translateY(-1px); }

.services {
  display: flex; gap: 18px; font-size: 12px; color: var(--ink-3);
  border-top: 1px dashed var(--line); padding-top: 12px; margin-top: 4px;
}

/* ---------- 相似商品推荐 ---------- */
.sim-sec { margin-top: 16px; background: #fff; border-radius: 12px; padding: 20px 24px 24px; box-shadow: 0 0 0 1px rgba(0,0,0,.04); }
.sim-head h2 { font-size: 18px; }
.heart { color: var(--brand); }
.sim-head p { color: var(--ink-3); font-size: 12.5px; margin: 6px 0 16px; }
.sim-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.sim-card {
  text-align: left; background: #fff; border-radius: 10px; overflow: hidden;
  box-shadow: 0 0 0 1px rgba(0,0,0,.05); transition: .2s; padding: 0;
}
.sim-card:hover { transform: translateY(-3px); box-shadow: 0 8px 18px rgba(0,0,0,.1); }
.sim-card img { width: 100%; aspect-ratio: 1/1; object-fit: cover; background: #f7f7f7; }
.sim-body { padding: 10px 12px 12px; display: flex; flex-direction: column; gap: 6px; }
.sim-body b { font-size: 13px; font-weight: 400; line-height: 1.45; color: var(--ink); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.sim-body em { font-style: normal; display: flex; justify-content: space-between; align-items: center; }
.sim-body .p { color: var(--accent); font-weight: 700; font-size: 16px; }
.sim-body .s { color: var(--ink-3); font-size: 11.5px; }
.loading { text-align: center; color: var(--ink-3); padding: 40px; }

/* ---------- 底部固定购买栏 ---------- */
.buy-bar {
  position: fixed; left: 0; right: 0; bottom: 0; z-index: 50;
  background: #fff; border-top: 1px solid var(--line); box-shadow: 0 -4px 16px rgba(0,0,0,.06);
}
.bb-tabs, .bb-acts { max-width: 1190px; margin: 0 auto; padding: 0 16px; }
.bb-tabs { display: flex; gap: 28px; align-items: center; height: 42px; border-bottom: 1px solid var(--line); overflow-x: auto; }
.bb-tabs a { font-size: 13px; color: var(--ink-2); cursor: pointer; white-space: nowrap; height: 100%; display: inline-flex; align-items: center; border-bottom: 2px solid transparent; }
.bb-tabs a.on { color: var(--brand); font-weight: 700; border-bottom-color: var(--brand); }
.bb-tabs a:hover { color: var(--brand); }
.bb-acts { display: flex; align-items: center; gap: 14px; padding-top: 10px; padding-bottom: 12px; }
.bb-fav {
  display: flex; flex-direction: column; align-items: center; gap: 1px;
  font-size: 17px; color: var(--ink-3); line-height: 1;
}
.bb-fav i { font-style: normal; font-size: 11px; }
.bb-fav.on { color: var(--brand); }
.bb-cart {
  font-size: 14px; font-weight: 700; color: var(--ink);
  background: linear-gradient(90deg, #ffd76e, var(--gold));
  border-radius: 999px 0 0 999px; padding: 13px 34px;
}
.bb-buy {
  font-size: 15px; font-weight: 700; color: #fff;
  background: linear-gradient(90deg, #ff7a00, #ff2050);
  border-radius: 0 999px 999px 0; padding: 13px 44px; margin-left: -12px;
}
.bb-cart:hover, .bb-buy:hover { filter: brightness(1.05); }

@media (max-width: 900px) {
  .main { grid-template-columns: 1fr; padding: 16px; gap: 18px; }
  .sim-grid { grid-template-columns: repeat(2, 1fr); }
  .buy, .cart { min-width: 0; flex: 1; }
  .gallery { grid-template-columns: 1fr; }
  .thumbs { flex-direction: row; }
  .bb-cart, .bb-buy { padding: 12px 20px; }
}
</style>
