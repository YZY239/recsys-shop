<script setup>
import { computed } from 'vue'

const props = defineProps({
  item: { type: Object, required: true },
  live: { type: Boolean, default: false },     // 实时插入标记
  fromName: { type: String, default: '' }      // 来源商品名
})
defineEmits(['click'])

// 淘宝式价格排版：£ + 大号整数 + 小号小数
const price = computed(() => {
  const v = props.item.price
  if (v == null || v === '') return null
  const [int, dec] = String(v).split('.')
  return { int, dec: dec ? '.' + dec : '' }
})

// 由商品编号稳定推导"x人付款"演示数字（同款商品刷新后不变，淘宝卡片同款元素）
const pays = computed(() => {
  let h = 0
  for (const ch of String(props.item.code || '')) h = (h * 31 + ch.charCodeAt(0)) % 997
  return 100 + h
})
</script>

<template>
  <article class="card" :data-code="item.code" @click="$emit('click', item)">
    <div class="thumb">
      <img :src="item.img || '/images/placeholder-other.svg'" :alt="item.cn_name || item.en_name" loading="lazy" />
      <span v-if="live" class="live">实时 · 相似好物</span>
      <span v-else-if="item.from_click" class="from">看过相关 · 为你补充</span>
      <span v-if="item.hot" class="hot">热卖</span>
    </div>
    <div class="body">
      <h3 class="cn">
        <span class="guess-tag">{{ live ? '相似推荐' : (item.cold ? '兴趣精选' : '猜你喜欢') }}</span>{{ item.cn_name || item.en_name }}
      </h3>
      <p v-if="item.reason" class="reason">{{ item.reason }}</p>
      <div class="meta-row">
        <span class="cat">{{ item.category }}</span>
        <span v-if="item.sim != null" class="sim">相似度 {{ item.sim }}%</span>
        <span v-else-if="item.cf" class="sim">为你探索</span>
        <span v-else-if="item.score" class="score">推荐分 {{ item.score }}</span>
      </div>
      <div class="price-row">
        <span v-if="price" class="price"><i>£</i><b>{{ price.int }}</b><i v-if="price.dec">{{ price.dec }}</i></span>
        <span v-else class="price"><b>价格面议</b></span>
        <span v-if="fromName" class="from-note">因为你看过「{{ fromName }}」</span>
      </div>
      <div class="pay-row">
        <span>{{ pays }} 人付款</span>
        <span class="ship">包邮</span>
      </div>
    </div>
  </article>
</template>

<style scoped>
.card {
  background: var(--card); border-radius: 12px; overflow: hidden;
  box-shadow: 0 0 0 1px rgba(0,0,0,.04); cursor: pointer; transition: .2s;
  display: flex; flex-direction: column; position: relative;
}
.card:hover { box-shadow: 0 8px 20px rgba(0,0,0,.1); transform: translateY(-3px); }
.thumb { position: relative; aspect-ratio: 1/1; background: #f7f7f7; overflow: hidden; }
.thumb img { width: 100%; height: 100%; object-fit: cover; transition: .3s; }
.card:hover .thumb img { transform: scale(1.05); }
.live {
  position: absolute; left: 0; top: 10px; color: #fff; font-size: 11px;
  padding: 3px 10px 3px 8px; font-weight: 700;
  background: linear-gradient(90deg, var(--live), #34d399);
  border-radius: 0 999px 999px 0;
}
.from {
  position: absolute; left: 0; top: 10px; color: #fff; font-size: 11px;
  padding: 3px 10px 3px 8px; font-weight: 600;
  background: linear-gradient(90deg, #6366f1, #818cf8);
  border-radius: 0 999px 999px 0;
}
.hot {
  position: absolute; right: 10px; top: 10px; color: #fff; font-size: 11px; font-weight: 700;
  padding: 3px 8px; border-radius: 4px;
  background: linear-gradient(90deg, var(--gold), var(--brand));
}
.body { padding: 10px 12px 12px; display: flex; flex-direction: column; gap: 6px; flex: 1; }
.cn {
  font-size: 14px; font-weight: 400; color: var(--ink); line-height: 1.45; min-height: 40px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.guess-tag {
  display: inline-block; font-size: 11px; font-weight: 700; color: var(--brand);
  border: 1px solid currentColor; border-radius: 3px; padding: 0 4px; margin-right: 6px;
  transform: translateY(-1px);
}
.reason {
  font-size: 11px; color: var(--brand); background: var(--brand-soft);
  border-radius: 3px; padding: 2px 6px; align-self: flex-start;
  max-width: 100%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  margin-top: -2px;
}
.meta-row { display: flex; align-items: center; gap: 8px; }
.cat {
  font-size: 11px; color: var(--ink-2); background: #f5f5f5;
  padding: 2px 8px; border-radius: 3px;
}
.sim { color: var(--brand); font-size: 11.5px; font-weight: 700; }
.score { color: var(--ink-3); font-size: 11px; }
.price-row { margin-top: auto; display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.price { color: var(--accent); font-weight: 700; white-space: nowrap; }
.price i { font-style: normal; font-size: 13px; }
.price b { font-size: 22px; letter-spacing: -.5px; }
.from-note {
  font-size: 11px; color: var(--live); white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;
}
.pay-row {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 11.5px; color: var(--ink-3); margin-top: -2px;
}
.pay-row .ship {
  color: var(--brand); background: var(--brand-soft);
  font-size: 10.5px; padding: 1px 6px; border-radius: 3px;
}
</style>
