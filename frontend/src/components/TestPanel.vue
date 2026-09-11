<script setup>
/* ============================================================
   TestPanel.vue —— 测试辅助浮窗（TEST-ONLY，独立模块）
   · 用途：验证「猜你喜欢」推荐流的商品重复问题
   · 删除方式：删除本文件 + 移除 App.vue 中的 <TestPanel/> 引用
              + 删除 api.js 的 testClean 与后端 /api/test/clean 接口，
              不影响任何正式功能
   · 测试项（下拉菜单选择，可逐步增加）：
     1. 点击即推荐 · 商品重复测试 —— 自动模拟「点击商品→详情→返回→下拉分页」，
        检测：插入商品是否与前面看过的重复；后续下拉加载是否与上方（含插入）重复
   ============================================================ */
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'

const testId = ref('dup')
const log = ref([])
const running = ref(false)
const collapsed = ref(true)   // 默认收起，不遮挡页面
const clickedInTest = ref([])
const route = useRoute()

const wait = (ms) => new Promise((r) => setTimeout(r, ms))

function L(msg, ok) {
  log.value.push((ok === true ? '✅ ' : ok === false ? '❌ ' : '· ') + msg)
}

// 扫描当前推荐流卡片（code 来自 ProductCard 的 data-code）
function collect() {
  const cards = [...document.querySelectorAll('.grid .card')]
  const list = cards.map((el) => ({
    code: el.dataset.code || '',
    name: (el.querySelector('.cn')?.textContent || '').slice(0, 16),
    live: !!el.querySelector('.live'),
    el,
  }))
  const seen = new Set()
  const dupCodes = []
  for (const it of list) {
    if (seen.has(it.code)) dupCodes.push(it.code)
    else seen.add(it.code)
  }
  return { list, codes: list.map((x) => x.code), dupCodes, set: seen }
}

function namesOf(codes) {
  const byCode = {}
  for (const c of collect().list) byCode[c.code] = c.name
  return [...new Set(codes)].map((c) => byCode[c] || c).join('、')
}

async function waitFor(fn, timeout, desc) {
  const t0 = Date.now()
  while (!fn()) {
    if (Date.now() - t0 > timeout) throw new Error('等待超时: ' + desc)
    await wait(300)
  }
}

async function run() {
  if (running.value) return
  log.value = []
  clickedInTest.value = []
  running.value = true
  try {
    if (route.name !== 'home') {
      L('请先回到「猜你喜欢」首页再运行本测试', false)
      return
    }
    if (testId.value === 'dup') await runDupTest()
    else L('测试项未实现', false)
  } catch (e) {
    L('测试异常: ' + e.message, false)
  } finally {
    running.value = false
  }
}

// ---------- 测试项：点击即推荐 · 商品重复测试 ----------
async function runDupTest() {
  L('===== 点击即推荐 · 商品重复测试 =====')
  L('检测点：① 插入商品不与前面看过的重复；② 下拉新增不与上方（含插入）重复')

  // ① 初始快照（= 前面看过的基准）
  let cur = collect()
  if (!cur.codes.length) { L('页面暂无商品，请先加载首页', false); return }
  if (cur.dupCodes.length) { L('初始页面已存在重复: ' + namesOf(cur.dupCodes), false); return }
  L(`① 初始页面 ${cur.codes.length} 个商品，无重复`)
  L(`   将模拟点击第 1 个商品「${cur.list[0].name}」`)

  const base = new Set(cur.codes)

  // ② 模拟点击 → 详情 → 返回
  L('② 点击商品 → 进入详情页 → 返回首页...')
  sessionStorage.removeItem('recsys_inserted')
  cur.list[0].el.click()
  clickedInTest.value.push(cur.codes[0])
  try {
    await waitFor(() => location.pathname.includes('/item/'), 6000, '进入详情页')
  } catch {
    L('未进入详情页（点击上报可能失败，token 可能失效），请刷新重新登录', false)
    return
  }
  L('   已进入详情页')
  const back = document.querySelector('.back')
  if (back) back.click()
  else history.back()
  await waitFor(() => location.pathname.endsWith('/home'), 6000, '返回首页')
  await wait(900) // 等 mergeInserted 完成

  // ③ 返回后扫描：页面重复 + 插入商品与前文对比
  const after = collect()
  L(`③ 返回后共 ${after.codes.length} 个商品（净增 ${after.codes.length - cur.codes.length} 个）`)
  if (after.dupCodes.length) L('页面存在重复: ' + namesOf(after.dupCodes), false)
  else L('   返回后整页无重复', true)

  const inserted = after.list.filter((x) => x.live && !base.has(x.code))
  const insertDup = inserted.filter((x) => base.has(x.code))
  if (insertDup.length) {
    L(`❌ 插入商品与前面看过的重复: ${namesOf(insertDup.map((x) => x.code))}`, false)
  } else if (inserted.length) {
    L(`插入商品 ${inserted.length} 个（${namesOf(inserted.map((x) => x.code))}），与前面看过的零重复`, true)
  } else {
    L('本次没有可插入的新商品（相似品均已看过），零重复', true)
  }

  // ④ 自动下拉分页：每页新增与上方（原有+插入）对比
  L('④ 自动下拉加载后续页，逐页检查与上方重复...')
  const baseAfter = new Set(after.codes)
  let prevSet = baseAfter
  let prevCount = after.codes.length
  let checked = 0, fail = 0
  for (let i = 0; i < 8; i++) {
    window.scrollTo(0, document.body.scrollHeight)
    window.dispatchEvent(new Event('scroll'))
    await wait(1500)
    const c = collect()
    if (c.codes.length === prevCount) {
      const sent = document.getElementById('sentinel')?.innerText || ''
      if (sent.includes('已经到底')) { L('   已滑到底部，共 ' + prevCount + ' 个商品'); break }
      continue
    }
    const newCodes = c.codes.filter((code) => !prevSet.has(code))
    const overBase = newCodes.filter((code) => baseAfter.has(code))
    checked++
    if (c.dupCodes.length) {
      fail++
      L(`   第 ${checked} 页: 整页出现重复 → ${namesOf(c.dupCodes)}`, false)
    } else if (overBase.length) {
      fail++
      L(`   第 ${checked} 页: 新增 ${newCodes.length} 个，其中 ${overBase.length} 个与上方重复 → ${namesOf(overBase)}`, false)
    } else {
      L(`   第 ${checked} 页: 新增 ${newCodes.length} 个，与上方（原有+插入）零重复`, true)
    }
    prevSet = new Set(c.codes)
    prevCount = c.codes.length
  }

  // ⑤ 汇总
  if (fail === 0 && checked > 0) L('结论：通过 —— 插入与下拉均未与已出现商品重复', true)
  else if (checked === 0) L('结论：未能加载到后续分页（候选池可能已滑完）')
  else L(`结论：发现 ${fail} 处重复，请检查去重链路`, false)
  L(`（本次测试模拟点击 ${clickedInTest.value.length} 个商品，已计入永久冷却；点「清理测试数据」可恢复）`)
}

// 清理测试产生的行为记录（调后端 TEST-ONLY 接口）
async function clean() {
  try {
    const r = await api.testClean()
    L('测试数据已清理（行为记录清空、冷却重置）；建议刷新页面重新登录', r.code === 0)
    clickedInTest.value = []
  } catch (e) {
    L('清理失败: ' + e.message, false)
  }
}
</script>

<template>
  <aside class="test-panel" :class="{ collapsed }">
    <div class="tp-head" @click="collapsed = !collapsed">
      <span class="tp-title">测试面板</span>
      <span class="tp-toggle">{{ collapsed ? '展开' : '收起' }}</span>
    </div>
    <div v-show="!collapsed" class="tp-body">
      <select v-model="testId">
        <option value="dup">点击即推荐 · 商品重复测试</option>
      </select>
      <div class="tp-actions">
        <button class="run" :disabled="running" @click="run">
          {{ running ? '测试中…' : '运行测试' }}
        </button>
        <button class="clean" :disabled="running" @click="clean">清理测试数据</button>
      </div>
      <pre class="tp-log">{{ log.join('\n') || '选择测试项后点击「运行测试」' }}</pre>
      <p class="tp-note">测试项说明：自动模拟「点击→详情→返回→下拉」，检测整页商品重复（含原有与新插入的推荐商品）。测试会写入点击记录，可用「清理测试数据」一键恢复。</p>
    </div>
  </aside>
</template>

<style scoped>
.test-panel {
  position: fixed; left: 16px; bottom: 16px; z-index: 9999;
  width: 330px; background: #fff; border: 1px solid #e5dfd6; border-radius: 14px;
  box-shadow: 0 10px 32px rgba(120, 90, 60, .16); font-size: 12px; overflow: hidden;
  color: #3d372f; font-family: inherit;
}
.tp-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 9px 14px; cursor: pointer; background: #f6f2ea; user-select: none;
}
.tp-title { font-weight: 800; font-size: 13px; color: #8a5a2b; }
.tp-toggle { font-size: 11px; color: #a08b74; }
.tp-body { padding: 12px 14px 14px; }
.tp-body select {
  width: 100%; padding: 7px 8px; margin-bottom: 10px; border: 1px solid #ddd6cb;
  border-radius: 9px; background: #fff; font-size: 12.5px; color: inherit; cursor: pointer;
}
.tp-actions { display: flex; gap: 8px; margin-bottom: 10px; }
.tp-actions button {
  flex: 1; padding: 8px 0; border: none; border-radius: 9px; cursor: pointer;
  font-weight: 700; font-size: 12.5px;
}
.tp-actions .run { background: #4F6EF7; color: #fff; }
.tp-actions .run:disabled { opacity: .6; cursor: wait; }
.tp-actions .clean { background: #efe9e0; color: #7a6a55; }
.tp-log {
  max-height: 230px; overflow: auto; background: #fbf9f5; border: 1px dashed #e2d9cc;
  border-radius: 9px; padding: 9px 10px; white-space: pre-wrap; word-break: break-all;
  line-height: 1.65; margin: 0 0 8px;
}
.tp-note { margin: 0; font-size: 11px; color: #a4947e; line-height: 1.6; }
</style>
