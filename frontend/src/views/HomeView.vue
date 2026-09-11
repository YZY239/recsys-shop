<script setup>
import { ref, computed, onMounted, onActivated, onDeactivated, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import ProductCard from '../components/ProductCard.vue'
import { api, getUser, clearAuth } from '../api'

defineOptions({ name: 'HomeView' })

const router = useRouter()
const user = getUser()

const items = ref([])          // 推荐流（含随机混入的"点击即推荐"商品）
const page = ref(1)
const hasMore = ref(true)
const loading = ref(false)
const refreshing = ref(false)
const toast = ref('')
const showTop = ref(false)     // 是否显示"回顶部"悬浮按钮
let observer = null

// 类目导航（淘宝首页左侧栏风格）：点击可筛选当前已加载的推荐流
const CATS = ['厨房用品', '食品', '装饰品', '家居装饰', '派对用品', '购物袋', '收纳用品', '文具', '玩具', '服饰', '未分类']
const activeCat = ref('')
const kwInput = ref('')
const kw = ref('')

// 横幅轮播（淘宝首页中央大促横幅风格）
const BANNERS = [
  { t: '猜你喜欢 · 全新升级', s: 'ItemCF 扩展候选，推的都是没买过但可能喜欢的', g: ['#ff4d6a', '#ff7a45'] },
  { t: '点击即推荐', s: '点击任意商品，相似好物立即混入你的推荐流', g: ['#ff6000', '#ff9500'] },
  { t: '无限下滑', s: '每个好物只出现一次，绝不重复；换一批开启全新排列' , g: ['#f4350c', '#ff6000'] }
]
const bannerIdx = ref(0)
let bannerTimer = null
onMounted(() => {
  bannerTimer = setInterval(() => { bannerIdx.value = (bannerIdx.value + 1) % BANNERS.length }, 4000)
})
onUnmounted(() => { if (bannerTimer) clearInterval(bannerTimer) })

const visibleItems = computed(() => {
  let list = items.value
  if (activeCat.value) list = list.filter((i) => i.category === activeCat.value)
  if (kw.value) {
    const k = kw.value.toLowerCase()
    list = list.filter((i) =>
      (i.cn_name || '').toLowerCase().includes(k) ||
      (i.en_name || '').toLowerCase().includes(k) ||
      (i.category || '').includes(k))
  }
  return list
})
function setCat(c) { activeCat.value = activeCat.value === c ? '' : c }
function doSearch() { kw.value = kwInput.value.trim() }

// 频道导航（淘宝搜索框下方一排彩色频道入口的简化版）：点击即触发对应行为
const CHANNELS = [
  { name: '猜你喜欢', color: '#ff5000', act: () => { goTop() } },
  { name: '实时推荐', color: '#0e9f6e', act: () => { goTop(); showToast('点击任意商品，相似好物会立即混入推荐流') } },
  { name: '换一批', color: '#6366f1', act: () => refresh() },
  { name: '热门好物', color: '#ff9500', act: () => { activeCat.value = ''; kw.value = ''; kwInput.value = ''; goTop() } },
  { name: '会员频道', color: '#e0399b', act: () => showToast('演示频道：会员权益建设中') },
  { name: '全部类目', color: '#2589ff', act: () => { activeCat.value = ''; goTop() } }
]
function goTop() {
  document.querySelector('.sec-head')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// 会话级"已出现商品"记录（sessionStorage 持久，跨轮次有效）：
// 点击即推荐插入的新商品 / 轮转轮次新增的商品 都以此双重去重（code + 展示名）——
// 绝不能和用户本会话已见过的任何商品重复（目录存在同名不同码商品，名称也要查重）
const EVER_KEY = 'recsys_ever_seen'
const EVER_NAME_KEY = 'recsys_ever_names'
const everSeen = ref(readSet(EVER_KEY))
const everNames = ref(readSet(EVER_NAME_KEY))
function nameOf(it) {
  return ((it.cn_name || it.en_name || '') + '').trim().toLowerCase()
}
function readSet(key) {
  try {
    const raw = sessionStorage.getItem(key)
    return raw ? new Set(JSON.parse(raw)) : new Set()
  } catch { return new Set() }
}
function persistSets() {
  sessionStorage.setItem(EVER_KEY, JSON.stringify([...everSeen.value]))
  sessionStorage.setItem(EVER_NAME_KEY, JSON.stringify([...everNames.value]))
}
function recordSeen(list) {
  for (const it of list) {
    everSeen.value.add(it.code)
    const nm = nameOf(it)
    if (nm) everNames.value.add(nm)
  }
  persistSets()
}
function resetSeen(list) {
  everSeen.value = new Set()
  everNames.value = new Set()
  recordSeen(list)
}
// 双重去重：候选列表中剔除 code 或名称 已出现过的商品
function dedup(list) {
  const seenCodes = new Set(items.value.map((i) => i.code))
  const out = []
  for (const it of list) {
    const nm = nameOf(it)
    if (!it.code || seenCodes.has(it.code) || everSeen.value.has(it.code)) continue
    if (!nm || everNames.value.has(nm)) continue
    seenCodes.add(it.code)
    out.push(it)
  }
  return out
}

function showToast(msg) {
  toast.value = msg
  setTimeout(() => (toast.value = ''), 2600)
}

// 收藏 / 购物车角标（进入首页与从其它页面返回时刷新）
const favCount = ref(0)
const cartCount = ref(0)
async function loadCounts() {
  const [f, ct] = await Promise.all([api.favorites(), api.cart()])
  if (f.code === 0) favCount.value = f.count || 0
  if (ct.code === 0) cartCount.value = ct.count || 0
}

// 头像：用户上传的 avatar（dataURL）优先，否则昵称首字 + 主题色
const avatarUrl = computed(() => user?.avatar || '')

function fmt(v) {
  return { ...v, img: v.img || '/images/placeholder.svg' }
}

async function load(p, append = true) {
  if (loading.value) return
  loading.value = true
  try {
    const r = await api.recommend(p)
    if (r.code === 0) {
      const list = (r.list || []).map(fmt)
      if (append) {
        // 统一口径（所有轮次一致）：code + 名称双重去重后追加；
        // 轮转轮次返回的重复商品被静默过滤，一页拉回全是已见商品 → 推荐流覆盖完毕，到底
        const fresh = dedup(list)
        items.value = items.value.concat(fresh)
        recordSeen(fresh)
        hasMore.value = fresh.length > 0
      } else {
        // 刷新：重置加载状态，开启新一轮浏览；已见记录同步重置为本轮流
        items.value = list
        resetSeen(list)
        hasMore.value = r.has_more
      }
      page.value = p
    }
  } finally {
    loading.value = false
  }
}

// 点击即推荐：返回首页时，把点击过的商品的相似商品随机混入被点击商品之后的卡片流（不再置顶展示）
async function mergeInserted() {
  const raw = sessionStorage.getItem('recsys_inserted')
  if (!raw) return
  sessionStorage.removeItem('recsys_inserted')
  try {
    const { from, fromCode, items: list } = JSON.parse(raw)
    if (!Array.isArray(list) || !list.length) return
    // 找到被点击商品在流中的位置；找不到则退回到"视口以下"的插入起点
    const clickedIdx = fromCode ? items.value.findIndex((i) => i.code === fromCode) : -1
    // 会话级双重去重（code + 名称）：本会话已出现过的商品（含此前轮次、此前插入、点击过的）
    // 一律不重复插入；插入候选之间也互相去重
    const fresh = dedup(list)
      .filter((i) => (i.cn_name || i.en_name))
      .map((i) => ({ ...fmt(i), live: true, fromName: from }))
    if (!fresh.length) return
    recordSeen(fresh)
    const lo = clickedIdx >= 0
      ? clickedIdx + 1                                    // 严格在被点击商品之后
      : Math.min(countCardsAboveViewport(), items.value.length)
    for (const it of fresh) {
      const hi = items.value.length
      const pos = hi === 0 ? 0 : Math.min(lo, hi) + Math.floor(Math.random() * (hi - Math.min(lo, hi) + 1))
      items.value.splice(pos, 0, it)
    }
    showToast(`因为你看过「${from}」，相似好物已混入下方推荐`)
  } catch (e) { /* 忽略损坏的缓存 */ }
}

// 统计当前视口以上（已滚出屏幕顶部）的卡片数量 = 可插入的起始下标
function countCardsAboveViewport() {
  const cards = document.querySelectorAll('.grid .card')
  let idx = 0
  for (const el of cards) {
    if (el.getBoundingClientRect().top < 0) idx++
    else break
  }
  return idx
}

// 离开首页（进详情页）时记住滚动位置；返回时恢复
function saveScroll() {
  sessionStorage.setItem('recsys_scroll', String(window.scrollY || 0))
}

async function restoreScroll() {
  const raw = sessionStorage.getItem('recsys_scroll')
  if (raw == null) return
  sessionStorage.removeItem('recsys_scroll')
  const y = parseInt(raw, 10) || 0
  await nextTick()
  window.scrollTo(0, y)
}

// 下拉刷新后短暂抑制触底加载（回顶动画会经过哨兵，避免误触发）
let suppressUntil = 0

async function refresh() {
  refreshing.value = true
  sessionStorage.removeItem('recsys_inserted')
  await load(1, false)
  window.scrollTo({ top: 0, behavior: 'smooth' })  // 回到顶部，开启新一轮浏览
  suppressUntil = Date.now() + 1500
  refreshing.value = false
  showToast('推荐流已刷新')
}

// 滚动触底 → 分页加载（IntersectionObserver + 滚动兜底，双保险）
function setupObserver() {
  observer = new IntersectionObserver(async (entries) => {
    if (entries[0].isIntersecting && hasMore.value && !loading.value && Date.now() > suppressUntil) {
      await load(page.value + 1, true)
    }
  }, { rootMargin: '300px' })
  const el = document.getElementById('sentinel')
  if (el) observer.observe(el)
}

function onScrollNearBottom() {
  showTop.value = (window.scrollY || 0) > 600  // 滑过一屏后显示"回顶部"
  const el = document.getElementById('sentinel')
  if (!el) return
  const rect = el.getBoundingClientRect()
  if (rect.top <= window.innerHeight + 300 && hasMore.value && !loading.value && Date.now() > suppressUntil) {
    load(page.value + 1, true)
  }
}

function backTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function onCardClick(item) {
  // 点击行为上报 → 返回实时插入候选 → 存入缓存（含被点击商品 code） → 跳详情
  try {
    const r = await api.behavior(item.code)
    if (r.code === 0 && r.inserted && r.inserted.length) {
      sessionStorage.setItem('recsys_inserted', JSON.stringify({
        from: item.cn_name, fromCode: item.code, items: r.inserted
      }))
    }
  } catch (e) { /* 上报失败不阻断浏览 */ }
  router.push({ name: 'detail', params: { code: item.code } })
}

function logout() {
  // 先吊销服务端 token（失败不阻断本地清理）
  api.logout().catch(() => {})
  clearAuth()
  sessionStorage.removeItem('recsys_inserted')
  sessionStorage.removeItem('recsys_scroll')
  sessionStorage.removeItem('recsys_ever_seen')
  sessionStorage.removeItem('recsys_ever_names')
  router.push({ name: 'login' })
}

onMounted(async () => {
  await load(1, false)
  setupObserver()
  loadCounts()
  window.addEventListener('scroll', onScrollNearBottom, { passive: true })
})

// 从详情页返回时（keep-alive 激活）：恢复原滚动位置 + 随机混入点击即推荐商品
onActivated(async () => {
  await restoreScroll()
  await mergeInserted()
  loadCounts()
})

onDeactivated(saveScroll)
onUnmounted(() => {
  if (observer) observer.disconnect()
  window.removeEventListener('scroll', onScrollNearBottom)
})
</script>

<template>
  <div class="home">
    <!-- 顶部工具条 -->
    <div class="util-bar">
      <div class="util-inner">
        <span class="util-left">暖物集 · 个性化推荐系统演示</span>
        <div class="util-right">
          <span>你好，{{ user?.nickname }}（{{ user?.customer_id }}）</span>
          <i class="sep"></i>
          <a @click="router.push('/profile')">账号设置</a>
          <i class="sep"></i>
          <a @click="router.push('/favorites')">我的收藏<b v-if="favCount" class="mini-badge">{{ favCount }}</b></a>
          <i class="sep"></i>
          <a @click="router.push('/cart')">购物车<b v-if="cartCount" class="mini-badge">{{ cartCount }} 件</b><span v-else>0 件</span></a>
          <i class="sep"></i>
          <a class="quit" @click="logout">退出登录</a>
        </div>
      </div>
    </div>

    <!-- 主头部：Logo + 搜索框 -->
    <header class="masthead">
      <div class="mast-inner">
        <div class="logo" @click="refresh">
          <svg viewBox="0 0 64 64" width="38" height="38"><rect width="64" height="64" rx="14" fill="#FF5000"/><path d="M18 44c4-11 8-16 14-16s10 5 14 16" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round"/><circle cx="23" cy="24" r="4.5" fill="#fff"/><circle cx="41" cy="24" r="4.5" fill="#fff"/></svg>
          <span class="logo-txt">暖物集<small>nuanwuji.com</small></span>
        </div>
        <div class="search">
          <div class="search-pill">
            <svg class="s-ico" viewBox="0 0 24 24" width="16" height="16"><path d="M10 4a6 6 0 104.47 10.03l4.25 4.25 1.41-1.41-4.25-4.25A6 6 0 0010 4zm0 2a4 4 0 110 8 4 4 0 010-8z" fill="#999"/></svg>
            <input v-model="kwInput" placeholder="搜索猜你喜欢里的好物（如：杯子 / 蛋糕）" @keyup.enter="doSearch" />
            <button class="s-btn" @click="doSearch">搜 索</button>
          </div>
          <div class="hot-words">
            <a v-for="w in ['马克杯', '蛋糕', '购物袋', '收纳', '圣诞']" :key="w" @click="kwInput = w; doSearch()">{{ w }}</a>
          </div>
        </div>
        <div class="mast-right">
          <span class="avatar" :style="{ background: user?.color }">
            <img v-if="avatarUrl" :src="avatarUrl" alt="" />
            <template v-else>{{ user?.nickname?.[0] }}</template>
          </span>
          <div class="who">
            <b>{{ user?.nickname }}</b>
            <i>{{ (user?.interest || []).join(' · ') || '个性化推荐' }}</i>
          </div>
        </div>
      </div>
    </header>

    <!-- 频道导航（淘宝搜索框下彩色频道行） -->
    <nav class="channel-bar">
      <div class="ch-inner">
        <a v-for="ch in CHANNELS" :key="ch.name" class="ch" @click="ch.act">
          <i class="ch-dot" :style="{ background: ch.color }"></i>{{ ch.name }}
        </a>
      </div>
    </nav>

    <!-- 促销横幅 -->
    <div class="promo-strip">
      <div class="promo-inner">
        <b class="p-badge">超级推荐</b>
        <span class="p-txt">ItemCF 个性化推荐已上线！点击任意商品，相似好物立即混入你的推荐流</span>
        <button class="p-btn" :disabled="refreshing" @click="refresh">{{ refreshing ? '刷新中…' : '立即刷新' }}</button>
      </div>
    </div>

    <main class="page">
      <div class="layout">
        <!-- 左侧类目导航 -->
        <aside class="side">
          <div class="side-card">
            <h3 class="side-title">商品类目</h3>
            <ul class="cat-list">
              <li :class="{ on: !activeCat }" @click="setCat('')">全部好物</li>
              <li v-for="c in CATS" :key="c" :class="{ on: activeCat === c }" @click="setCat(c)">{{ c }}</li>
            </ul>
          </div>
        </aside>

        <!-- 中间主区：横幅轮播 + 运营小卡 + 推荐流 -->
        <section class="main-col">
          <!-- 大促横幅（自动轮播） -->
          <div class="banner" :style="{ background: `linear-gradient(100deg, ${BANNERS[bannerIdx].g[0]}, ${BANNERS[bannerIdx].g[1]})` }" @click="BANNERS[bannerIdx].act ? null : goTop()">
            <div class="banner-txt">
              <transition name="fade" mode="out-in">
                <div :key="bannerIdx">
                  <h2>{{ BANNERS[bannerIdx].t }}</h2>
                  <p>{{ BANNERS[bannerIdx].s }}</p>
                </div>
              </transition>
            </div>
            <div class="banner-deco">88</div>
            <div class="banner-dots">
              <i v-for="(b, i) in BANNERS" :key="i" :class="{ on: i === bannerIdx }" @click.stop="bannerIdx = i"></i>
            </div>
          </div>

          <!-- 运营小卡（淘宝"百亿补贴/领券中心"一排的简化版） -->
          <div class="ops-row">
            <div class="op" @click="refresh()"><b class="op-t" style="color:#ff5000">换一批</b><span>推荐流立刻刷新</span></div>
            <div class="op" @click="showToast('新人礼包：已到账（演示）')"><b class="op-t" style="color:#e0399b">新人礼包</b><span>专享首单礼金</span></div>
            <div class="op" @click="showToast('演示入口：领券中心建设中')"><b class="op-t" style="color:#2589ff">领券中心</b><span>天天领补贴</span></div>
            <div class="op" @click="activeCat = ''; goTop()"><b class="op-t" style="color:#0e9f6e">全类目</b><span>好物任你逛</span></div>
          </div>

          <div class="sec-head">
            <h2><span class="heart">♥</span>猜你喜欢<small>为你探索 · 没买过但可能喜欢</small></h2>
            <div class="tools">
              <span v-if="activeCat" class="filter-chip" @click="setCat('')">类目：{{ activeCat }} ✕</span>
              <span v-if="kw" class="filter-chip kw" @click="kw = ''; kwInput = ''">搜索：{{ kw }} ✕</span>
              <button class="btn btn-ghost" :disabled="refreshing" @click="refresh">
                {{ refreshing ? '刷新中…' : '换一批' }}
              </button>
            </div>
          </div>

          <!-- 推荐流（点击即推荐的商品会随机混入其中） -->
          <div class="grid">
            <ProductCard v-for="it in visibleItems" :key="it.code" :item="it"
                         :live="!!it.live" :from-name="it.fromName || ''" @click="onCardClick" />
          </div>

          <div v-if="!visibleItems.length && !loading" class="empty">
            <p>没有找到符合条件的好物</p>
            <button class="btn btn-ghost" @click="activeCat = ''; kw = ''; kwInput = ''">清除筛选</button>
          </div>

          <div id="sentinel" class="sentinel">
            <span v-if="loading">正在加载更多…</span>
            <span v-else-if="!hasMore">— 已经到底啦，点"换一批"看看新推荐 —</span>
          </div>
        </section>

        <!-- 右侧用户面板（淘宝首页右栏账号卡风格） -->
        <aside class="rpanel">
          <div class="rp-card user">
            <div class="rp-head">
              <span class="avatar big" :style="{ background: user?.color }">
                <img v-if="avatarUrl" :src="avatarUrl" alt="" />
                <template v-else>{{ user?.nickname?.[0] }}</template>
              </span>
              <div class="who">
                <b>{{ user?.nickname }}</b>
                <i>ID {{ user?.customer_id }}</i>
              </div>
            </div>
            <div class="rp-stats">
              <div><b>{{ visibleItems.length }}</b><i>在屏好物</i></div>
              <div><b>{{ favCount }}</b><i>我的收藏</i></div>
              <div><b>{{ cartCount }}</b><i>购物车</i></div>
            </div>
            <div class="rp-links">
              <a @click="router.push('/profile')">⚙️ 账号设置</a>
              <a @click="router.push('/favorites')">⭐ 我的收藏</a>
              <a @click="router.push('/cart')">🛒 购物车</a>
              <a @click="showToast('演示入口：足迹建设中')">👣 足迹</a>
              <a class="quit" @click="logout">↩ 退出登录</a>
            </div>
          </div>
          <div class="rp-card notice">
            <h3>推荐说明</h3>
            <p>依据你的历史喜好（ItemCF 扩展候选）精选，<b>点击过的商品不再出现</b>；同款绝不重复，滑到底点"换一批"开启新排列。</p>
          </div>
          <div class="rp-card report">
            <h3>举报反馈</h3>
            <p>推荐不合心意？<a @click="refresh(); showToast('已为你换一批推荐')">换一批试试</a></p>
          </div>
        </aside>
      </div>
    </main>

    <div v-if="toast" class="toast">{{ toast }}</div>

    <!-- 右侧悬浮"回顶部"（淘宝侧边工具条风格，滑过一屏出现） -->
    <transition name="fade-slide">
      <button v-if="showTop" class="back-top" @click="backTop" title="回到顶部">
        <span class="bt-icon">⌃</span>
        <span class="bt-text">回顶部</span>
      </button>
    </transition>
  </div>
</template>

<style scoped>
/* ---------- 顶部工具条 ---------- */
.util-bar { background: #fff; border-bottom: 1px solid #f0f0f0; }
.util-inner {
  max-width: var(--page-w); margin: 0 auto; padding: 0 16px; height: 32px;
  display: flex; align-items: center; justify-content: space-between;
  font-size: 12px; color: var(--ink-2);
}
.util-right { display: flex; align-items: center; gap: 10px; }
.util-right a { cursor: pointer; }
.util-right a:hover, .util-left:hover { color: var(--brand); }
.sep { width: 1px; height: 10px; background: #ddd; }
.quit:hover { color: var(--brand); }
.mini-badge {
  display: inline-block; margin-left: 4px; padding: 0 6px; font-size: 10.5px; font-weight: 700;
  color: #fff; background: var(--brand); border-radius: 999px; line-height: 16px; vertical-align: 1px;
}
.avatar img { width: 100%; height: 100%; object-fit: cover; border-radius: 50%; display: block; }

/* ---------- 主头部 ---------- */
.masthead { background: #fff; }
.mast-inner {
  max-width: var(--page-w); margin: 0 auto; padding: 18px 16px;
  display: flex; align-items: center; justify-content: space-between; gap: 32px;
}
.logo { display: flex; align-items: center; gap: 10px; cursor: pointer; flex: none; }
.logo-txt { font-size: 26px; font-weight: 800; color: var(--brand); line-height: 1; }
.logo-txt small { display: block; font-size: 11px; font-weight: 400; color: var(--ink-3); margin-top: 4px; }

.search { flex: 1; max-width: 560px; }
.search-pill {
  display: flex; align-items: center; gap: 8px;
  border: 2px solid var(--brand); border-radius: 999px; padding: 3px 4px 3px 14px;
  background: #fff;
}
.s-ico { flex: none; }
.search-pill input {
  flex: 1; border: none; outline: none; font-size: 13.5px; height: 30px; background: transparent;
}
.s-btn {
  flex: none; color: #fff; font-size: 15px; font-weight: 700; letter-spacing: 2px;
  padding: 8px 26px; border-radius: 999px;
  background: linear-gradient(90deg, var(--brand), var(--brand-deep));
}
.s-btn:hover { filter: brightness(1.06); }
.hot-words { display: flex; gap: 14px; margin: 8px 0 0 16px; }
.hot-words a { font-size: 12px; color: var(--ink-2); cursor: pointer; }
.hot-words a:hover { color: var(--brand); }

.mast-right { display: flex; align-items: center; gap: 10px; flex: none; }
.avatar {
  width: 38px; height: 38px; border-radius: 50%; color: #fff; font-weight: 800;
  display: flex; align-items: center; justify-content: center; font-size: 16px;
}
.who { display: flex; flex-direction: column; gap: 2px; }
.who b { font-size: 13.5px; }
.who i { font-style: normal; font-size: 11px; color: var(--ink-3); max-width: 180px;
         white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* ---------- 频道导航 ---------- */
.channel-bar { background: #fff; border-top: 1px solid #f5f5f5; }
.ch-inner {
  max-width: var(--page-w); margin: 0 auto; padding: 8px 16px;
  display: flex; align-items: center; justify-content: center; gap: 34px;
}
.ch { display: inline-flex; align-items: center; gap: 6px; font-size: 13.5px; font-weight: 600; color: var(--ink-2); cursor: pointer; }
.ch:hover { color: var(--brand); }
.ch-dot { width: 8px; height: 8px; border-radius: 50%; }

/* ---------- 促销横幅 ---------- */
.promo-strip {
  background: linear-gradient(90deg, #ff6000, var(--brand-deep));
  color: #fff;
}
.promo-inner {
  max-width: var(--page-w); margin: 0 auto; padding: 10px 16px;
  display: flex; align-items: center; gap: 14px;
}
.p-badge {
  font-size: 13px; padding: 3px 10px; border-radius: 4px;
  background: rgba(255, 255, 255, .18); border: 1px solid rgba(255, 255, 255, .5);
}
.p-txt { font-size: 14px; font-weight: 600; flex: 1; }
.p-btn {
  flex: none; font-size: 12.5px; font-weight: 700; color: var(--brand-deep);
  background: #fff; border-radius: 999px; padding: 6px 18px;
}
.p-btn:hover { transform: translateY(-1px); }

/* ---------- 布局（三栏：类目 / 主区 / 用户面板） ---------- */
.layout { display: grid; grid-template-columns: 185px 1fr 235px; gap: 14px; margin-top: 14px; align-items: start; }
.side { position: sticky; top: 12px; display: flex; flex-direction: column; gap: 12px; }
.side-card { background: #fff; border-radius: 12px; padding: 14px 0 8px; box-shadow: 0 0 0 1px rgba(0,0,0,.04); }
.side-title { font-size: 14px; padding: 0 16px 8px; border-bottom: 1px solid var(--line); }
.cat-list { list-style: none; padding: 6px 0; }
.cat-list li {
  padding: 8px 16px; font-size: 13px; color: var(--ink-2); cursor: pointer;
  border-left: 3px solid transparent; transition: .15s;
}
.cat-list li:hover { color: var(--brand); background: var(--brand-soft); }
.cat-list li.on { color: var(--brand); font-weight: 700; border-left-color: var(--brand); background: var(--brand-soft); }

/* ---------- 横幅轮播 ---------- */
.banner {
  position: relative; border-radius: 12px; overflow: hidden; cursor: pointer;
  height: 150px; color: #fff; box-shadow: var(--shadow-sm);
}
.banner-txt { position: absolute; left: 28px; top: 50%; transform: translateY(-50%); z-index: 2; }
.banner-txt h2 { font-size: 26px; font-weight: 800; letter-spacing: 1px; text-shadow: 0 2px 8px rgba(0,0,0,.15); }
.banner-txt p { margin-top: 8px; font-size: 13.5px; opacity: .95; }
.banner-deco {
  position: absolute; right: 34px; top: 50%; transform: translateY(-50%) rotate(-8deg);
  font-size: 84px; font-weight: 900; font-style: italic; opacity: .22; letter-spacing: -4px;
}
.banner-dots { position: absolute; right: 16px; bottom: 12px; display: flex; gap: 6px; z-index: 2; }
.banner-dots i { width: 16px; height: 4px; border-radius: 2px; background: rgba(255,255,255,.45); cursor: pointer; }
.banner-dots i.on { background: #fff; }
.fade-enter-active, .fade-leave-active { transition: opacity .35s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* ---------- 运营小卡 ---------- */
.ops-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 14px 0 4px; }
.op {
  background: #fff; border-radius: 10px; padding: 12px 14px; cursor: pointer;
  display: flex; flex-direction: column; gap: 3px; box-shadow: 0 0 0 1px rgba(0,0,0,.04); transition: .18s;
}
.op:hover { transform: translateY(-2px); box-shadow: 0 6px 14px rgba(0,0,0,.08); }
.op-t { font-size: 14px; font-weight: 800; }
.op span { font-size: 11.5px; color: var(--ink-3); }

/* ---------- 猜你喜欢区 ---------- */
.sec-head { display: flex; align-items: center; justify-content: space-between; margin: 12px 0 12px; }
.sec-head h2 { font-size: 20px; display: flex; align-items: baseline; gap: 10px; }
.heart { color: var(--brand); font-size: 18px; }
.sec-head h2 small { font-size: 12px; font-weight: 400; color: var(--ink-3); }
.tools { display: flex; align-items: center; gap: 8px; }
.filter-chip {
  font-size: 12px; color: var(--brand); background: var(--brand-soft);
  border-radius: 999px; padding: 4px 12px; cursor: pointer;
}
.filter-chip.kw { color: var(--live); background: var(--live-soft); }

.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 8px; }
.sentinel { text-align: center; color: var(--ink-3); font-size: 13px; padding: 26px 0 10px; }
.empty {
  text-align: center; padding: 70px 0; color: var(--ink-3); font-size: 14px;
  background: #fff; border-radius: 12px;
}
.empty p { margin-bottom: 14px; }

/* ---------- 右侧用户面板 ---------- */
.rpanel { position: sticky; top: 12px; display: flex; flex-direction: column; gap: 12px; }
.rp-card { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 0 0 1px rgba(0,0,0,.04); }
.rp-head { display: flex; align-items: center; gap: 12px; }
.avatar.big { width: 46px; height: 46px; font-size: 20px; }
.rp-head .who { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.rp-head .who b { font-size: 15px; }
.rp-head .who i { font-style: normal; font-size: 11.5px; color: var(--ink-3); }
.rp-stats { display: grid; grid-template-columns: repeat(3, 1fr); text-align: center; margin: 14px 0; padding: 10px 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.rp-stats b { display: block; font-size: 14px; color: var(--brand); font-weight: 800; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rp-stats i { font-style: normal; font-size: 11px; color: var(--ink-3); }
.rp-links { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 12px; }
.rp-links a { font-size: 12.5px; color: var(--ink-2); cursor: pointer; white-space: nowrap; }
.rp-links a:hover { color: var(--brand); }
.rp-links .quit { color: var(--ink-3); }
.rp-card h3 { font-size: 13.5px; margin-bottom: 8px; }
.rp-card.notice p, .rp-card.report p { font-size: 12px; color: var(--ink-3); line-height: 1.7; }
.rp-card.notice b { color: var(--brand); }
.rp-card.report a { color: var(--brand); font-weight: 600; cursor: pointer; }

/* ---------- 响应式 ---------- */
@media (max-width: 1200px) {
  .layout { grid-template-columns: 185px 1fr; }
  .rpanel { display: none; }
}
@media (max-width: 1000px) {
  .grid { grid-template-columns: repeat(2, 1fr); }
  .mast-inner { gap: 16px; }
  .ch-inner { flex-wrap: wrap; gap: 12px 22px; }
  .ops-row { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 760px) {
  .layout { grid-template-columns: 1fr; }
  .side { position: static; flex-direction: row; overflow-x: auto; }
  .side-card { min-width: 210px; }
  .grid { grid-template-columns: repeat(2, 1fr); gap: 10px; }
  .mast-right, .hot-words { display: none; }
  .p-txt { font-size: 12px; }
  .banner { height: 120px; }
  .banner-txt h2 { font-size: 20px; }
  .banner-deco { display: none; }
}

/* ---------- 右侧悬浮"回顶部"（淘宝工具条风格） ---------- */
.back-top {
  position: fixed;
  right: calc(50% - var(--page-w) / 2 - 64px);  /* 贴在主容器右侧外沿，窄屏时退到右边缘 */
  bottom: 120px;
  z-index: 90;
  width: 52px;
  padding: 10px 0 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  background: #fff;
  border: 1px solid #f0f0f0;
  border-radius: 10px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  color: var(--ink-2);
  transition: transform 0.15s, color 0.15s, box-shadow 0.15s;
}
.back-top:hover {
  color: var(--brand);
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.12);
}
.back-top .bt-icon { font-size: 18px; line-height: 1; font-weight: 700; }
.back-top .bt-text { font-size: 12px; }
.fade-slide-enter-active, .fade-slide-leave-active { transition: opacity 0.2s, transform 0.2s; }
.fade-slide-enter-from, .fade-slide-leave-to { opacity: 0; transform: translateY(12px); }
@media (max-width: 1520px) {
  .back-top { right: 18px; }
}
</style>
