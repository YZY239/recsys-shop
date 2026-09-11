<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setToken, setUser } from '../api'

const router = useRouter()
const accounts = [
  { username: 'alice', nickname: '小艾', color: '#E8590C', slogan: '烘焙与下午茶爱好者', tags: ['厨房用品', '派对用品'] },
  { username: 'bob', nickname: '小博', color: '#0E9F6E', slogan: '收纳控 · 实用主义', tags: ['购物袋', '收纳用品'] },
  { username: 'carol', nickname: '卡罗', color: '#7C5CFC', slogan: '把家布置成喜欢的样子', tags: ['厨房用品', '收纳用品'] }
]
const active = ref('alice')
const password = ref('123456')
const loading = ref(false)
const errMsg = ref('')

// 注册模式
const mode = ref('login')   // login | register
const regForm = ref({ username: '', nickname: '', password: '', confirm: '' })
const TAGS = ['厨房用品', '食品', '装饰品', '家居装饰', '派对用品', '购物袋', '收纳用品', '文具', '玩具', '服饰']

function switchMode(m) {
  mode.value = m
  errMsg.value = ''
}

async function doLogin(username) {
  loading.value = true; errMsg.value = ''
  const r = await api.login(username, password.value)
  loading.value = false
  if (r.code === 0) {
    setToken(r.token); setUser(r.user)
    router.push('/home')
  } else {
    errMsg.value = r.msg || '登录失败'
  }
}

async function doRegister() {
  const f = regForm.value
  if (f.username.trim().length < 2) { errMsg.value = '用户名至少 2 个字符'; return }
  if (f.password.length < 6) { errMsg.value = '密码至少 6 位'; return }
  if (f.password !== f.confirm) { errMsg.value = '两次输入的密码不一致'; return }
  loading.value = true; errMsg.value = ''
  const r = await api.register(f.username.trim(), f.password, f.nickname.trim(), regTags.value)
  loading.value = false
  if (r.code === 0) {
    setToken(r.token); setUser(r.user)
    router.push('/home')
  } else {
    errMsg.value = r.msg || '注册失败'
  }
}
const regTags = ref([])
</script>

<template>
  <div class="login-wrap">
    <section class="brand">
      <div class="logo">
        <svg viewBox="0 0 64 64" width="46" height="46"><rect width="64" height="64" rx="14" fill="#FF5000"/><path d="M18 44c4-11 8-16 14-16s10 5 14 16" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round"/><circle cx="23" cy="24" r="4.5" fill="#fff"/><circle cx="41" cy="24" r="4.5" fill="#fff"/></svg>
        <span>暖物集</span>
      </div>
      <h1>把喜欢的生活，<br />一件一件带回家</h1>
      <p class="sub">从你的每一次选择里，读懂你喜欢的生活。</p>
      <ul class="feats">
        <li><b>个性化</b> 依据你的历史喜好精挑细选</li>
        <li><b>实时</b> 点击过的商品，相似好物立刻补进推荐流</li>
        <li><b>省心</b> 下拉刷新，更多惊喜持续加载</li>
      </ul>
    </section>

    <section class="panel">
      <div class="mode-tabs">
        <button :class="{ on: mode === 'login' }" @click="switchMode('login')">登录</button>
        <button :class="{ on: mode === 'register' }" @click="switchMode('register')">注册新账号</button>
      </div>

      <template v-if="mode === 'login'">
        <h2>选择体验账号</h2>
        <p class="hint">三个账号，三种不同推荐结果（默认密码 123456）</p>
        <div class="accounts">
          <button v-for="a in accounts" :key="a.username"
                  class="account" :class="{ on: active === a.username }"
                  @click="active = a.username">
            <span class="avatar" :style="{ background: a.color }">{{ a.nickname[0] }}</span>
            <span class="info">
              <b>{{ a.nickname }}</b>
              <i>{{ a.slogan }}</i>
              <em><span v-for="t in a.tags" :key="t">{{ t }}</span></em>
            </span>
            <span class="radio"></span>
          </button>
        </div>
        <label class="pwd">
          <span>登录密码</span>
          <input v-model="password" type="password" placeholder="123456"
                 @keyup.enter="doLogin(active)" />
        </label>
        <p v-if="errMsg" class="err">{{ errMsg }}</p>
        <button class="btn btn-primary go" :disabled="loading" @click="doLogin(active)">
          {{ loading ? '正在登录…' : '开始逛逛' }}
        </button>
      </template>

      <template v-else>
        <h2>创建你的账号</h2>
        <p class="hint">新用户按所选兴趣做冷启动推荐</p>
        <label class="pwd"><span>用户名</span>
          <input v-model="regForm.username" placeholder="2 个字符以上，如 taobao_fan" />
        </label>
        <label class="pwd"><span>昵称（可选）</span>
          <input v-model="regForm.nickname" placeholder="默认同用户名" />
        </label>
        <label class="pwd"><span>密码</span>
          <input v-model="regForm.password" type="password" placeholder="至少 6 位" />
        </label>
        <label class="pwd"><span>确认密码</span>
          <input v-model="regForm.confirm" type="password" placeholder="再输入一次" />
        </label>
        <div class="tag-pick">
          <span class="tp-label">兴趣标签（决定你的首批推荐）</span>
          <div class="tp-list">
            <button v-for="t in TAGS" :key="t" class="tp" :class="{ on: regTags.includes(t) }"
                    @click="regTags.includes(t) ? regTags.splice(regTags.indexOf(t), 1) : regTags.push(t)">
              {{ t }}
            </button>
          </div>
        </div>
        <p v-if="errMsg" class="err">{{ errMsg }}</p>
        <button class="btn btn-primary go" :disabled="loading" @click="doRegister">
          {{ loading ? '正在注册…' : '注册并进入' }}
        </button>
      </template>
    </section>
  </div>
</template>

<style scoped>
.login-wrap {
  min-height: 100vh; display: grid; grid-template-columns: 1.05fr 1fr; gap: 0;
  background:
    radial-gradient(1200px 600px at 15% -10%, #eef1fe 0%, transparent 60%),
    radial-gradient(900px 500px at 100% 110%, #fdeee3 0%, transparent 55%),
    var(--bg);
}
.brand { padding: 48px 56px; display: flex; flex-direction: column; justify-content: flex-start; min-height: 100%; overflow: visible; }
.logo { display: flex; align-items: center; gap: 12px; font-size: 22px; font-weight: 800; margin-bottom: 40px; }
.brand h1 { font-size: 40px; line-height: 1.25; letter-spacing: 1px; }
.sub { color: var(--ink-2); margin: 18px 0 34px; font-size: 15px; }
.feats { list-style: none; display: flex; flex-direction: column; gap: 12px; }
.feats li { font-size: 14px; color: var(--ink-2); padding-left: 26px; position: relative; }
.feats li::before {
  content: ""; position: absolute; left: 0; top: 4px; width: 16px; height: 16px;
  border-radius: 50%; background: var(--brand-soft);
  border: 2px solid var(--brand);
}
.feats b { color: var(--ink); margin-right: 8px; }

.panel {
  align-self: center; background: var(--card); border-radius: 24px; padding: 40px 36px;
  margin: 40px 56px 40px 20px; box-shadow: var(--shadow);
}
.panel h2 { font-size: 22px; }
.hint { color: var(--ink-3); font-size: 13px; margin: 6px 0 20px; }
.accounts { display: flex; flex-direction: column; gap: 10px; }
.account {
  display: flex; align-items: center; gap: 14px; padding: 12px 14px;
  border: 2px solid var(--line); border-radius: var(--radius-sm);
  text-align: left; transition: .18s; background: var(--bg-soft);
}
.account:hover { border-color: #cfc8bc; }
.account.on { border-color: var(--brand); background: var(--brand-soft); }
.avatar {
  width: 44px; height: 44px; border-radius: 14px; color: #fff; font-size: 18px; font-weight: 800;
  display: flex; align-items: center; justify-content: center; flex: none;
}
.info { flex: 1; display: flex; flex-direction: column; gap: 3px; }
.info b { font-size: 15px; }
.info i { font-style: normal; font-size: 12px; color: var(--ink-2); }
.info em { display: flex; gap: 6px; margin-top: 2px; }
.info em span { font-style: normal; font-size: 11px; color: var(--brand); background: #fff; border: 1px solid #d5dcfb; padding: 1px 8px; border-radius: 999px; }
.radio {
  width: 18px; height: 18px; border-radius: 50%; border: 2px solid #cfc8bc; flex: none;
  transition: .18s;
}
.account.on .radio { border-color: var(--brand); box-shadow: inset 0 0 0 4px var(--brand); }
.pwd { display: flex; flex-direction: column; gap: 6px; margin: 20px 0 6px; font-size: 13px; color: var(--ink-2); }
.pwd input {
  padding: 11px 14px; border: 2px solid var(--line); border-radius: var(--radius-sm);
  font-size: 14px; outline: none; transition: .18s; background: #fff;
}
.pwd input:focus { border-color: var(--brand); }
.err { color: #d64545; font-size: 12.5px; margin: 8px 0 0; }
.go { width: 100%; margin-top: 16px; padding: 13px; font-size: 15px; }
.tip { text-align: center; color: var(--ink-3); font-size: 12px; margin-top: 12px; }

/* ---------- 登录/注册切换 ---------- */
.mode-tabs {
  display: flex; background: #f2f3f5; border-radius: 999px; padding: 4px; margin-bottom: 18px;
}
.mode-tabs button {
  flex: 1; padding: 9px 0; font-size: 14px; font-weight: 600; color: var(--ink-2);
  border-radius: 999px; transition: .18s;
}
.mode-tabs button.on { background: #fff; color: var(--brand); box-shadow: 0 2px 8px rgba(0,0,0,.08); }

/* ---------- 注册表单 ---------- */
.tag-pick { margin-top: 14px; }
.tp-label { font-size: 12px; color: var(--ink-3); display: block; margin-bottom: 8px; }
.tp-list { display: flex; flex-wrap: wrap; gap: 8px; }
.tp {
  font-size: 12.5px; color: var(--ink-2); background: #f7f7f8;
  border: 1px solid #eee; border-radius: 999px; padding: 6px 14px; transition: .15s;
}
.tp:hover { border-color: var(--brand); color: var(--brand); }
.tp.on { color: var(--brand); border-color: var(--brand); background: #fff4ec; font-weight: 600; }

@media (max-width: 900px) {
  .login-wrap { grid-template-columns: 1fr; }
  .brand { padding: 40px 24px 16px; }
  .brand h1 { font-size: 30px; }
  .logo { margin-bottom: 24px; }
  .panel { margin: 16px 16px 48px; padding: 28px 20px; }
}
</style>
