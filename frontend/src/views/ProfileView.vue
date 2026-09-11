<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api, getUser, setUser } from '../api'

const router = useRouter()
const user = ref({ ...(getUser() || {}) })
const toast = ref('')
const saving = ref(false)

const TAGS = ['厨房用品', '食品', '装饰品', '家居装饰', '派对用品', '购物袋', '收纳用品', '文具', '玩具', '服饰']
const COLORS = ['#FF5000', '#E8590C', '#0E9F6E', '#7C5CFC', '#2589FF', '#E0399B']

// 表单
const form = ref({
  username: user.value.username || '',
  nickname: user.value.nickname || '',
  color: user.value.color || '#FF5000',
  slogan: user.value.slogan || '',
  interest: [...(user.value.interest || [])]
})
const pwd = ref({ old: '', new1: '', new2: '' })
const fileEl = ref(null)

function showToast(msg) {
  toast.value = msg
  setTimeout(() => (toast.value = ''), 2400)
}

function applyUser(u) {
  user.value = { ...user.value, ...u }
  setUser({ ...getUser(), ...u })
}

async function saveProfile() {
  if (form.value.username.trim().length < 2) { showToast('用户名至少 2 个字符'); return }
  saving.value = true
  const r = await api.profileUpdate({
    username: form.value.username.trim(),
    nickname: form.value.nickname.trim() || form.value.username.trim(),
    color: form.value.color,
    slogan: form.value.slogan,
    interest: form.value.interest
  })
  saving.value = false
  if (r.code === 0) { applyUser(r.user); showToast('资料已保存') }
  else showToast(r.msg || '保存失败')
}

function toggleTag(t) {
  const i = form.value.interest.indexOf(t)
  if (i >= 0) form.value.interest.splice(i, 1)
  else if (form.value.interest.length < 4) form.value.interest.push(t)
  else showToast('最多选择 4 个兴趣标签')
}

async function changePwd() {
  if (pwd.value.new1.length < 6) { showToast('新密码至少 6 位'); return }
  if (pwd.value.new1 !== pwd.value.new2) { showToast('两次输入的新密码不一致'); return }
  const r = await api.passwordChange(pwd.value.old, pwd.value.new1)
  showToast(r.msg || (r.code === 0 ? '密码已修改' : '修改失败'))
  if (r.code === 0) pwd.value = { old: '', new1: '', new2: '' }
}

// 头像：选择图片 → canvas 压缩到 200px → dataURL 上传
function pickAvatar() { fileEl.value.click() }

function onFile(e) {
  const file = e.target.files && e.target.files[0]
  if (!file) return
  if (!file.type.startsWith('image/')) { showToast('请选择图片文件'); return }
  const reader = new FileReader()
  reader.onload = () => {
    const img = new Image()
    img.onload = async () => {
      const canvas = document.createElement('canvas')
      canvas.width = canvas.height = 200
      const ctx = canvas.getContext('2d')
      // 居中裁剪为正方形
      const side = Math.min(img.width, img.height)
      ctx.drawImage(img, (img.width - side) / 2, (img.height - side) / 2, side, side, 0, 0, 200, 200)
      const dataUrl = canvas.toDataURL('image/jpeg', 0.85)
      const r = await api.avatarUpdate(dataUrl)
      if (r.code === 0) { applyUser(r.user); showToast('头像已更新') }
      else showToast(r.msg || '头像上传失败')
    }
    img.src = reader.result
  }
  reader.readAsDataURL(file)
  e.target.value = ''
}

function clearAvatar() {
  api.avatarUpdate('').then((r) => {
    if (r.code === 0) { applyUser(r.user); showToast('已恢复默认头像') }
  })
}

onMounted(() => {
  api.profile().then((r) => {
    if (r.code === 0) {
      applyUser(r.user)
      form.value.username = r.user.username
      form.value.nickname = r.user.nickname
      form.value.color = r.user.color
      form.value.slogan = r.user.slogan
      form.value.interest = [...(r.user.interest || [])]
    }
  })
})
</script>

<template>
  <div class="page">
    <div class="topbar">
      <button class="back" @click="router.back()">← 返回</button>
      <h1>账号设置</h1>
      <span class="cnt">ID {{ user?.customer_id }}</span>
    </div>

    <main class="body">
      <!-- 头像 -->
      <section class="card">
        <h2>头像</h2>
        <div class="avatar-row">
          <span class="avatar big" :style="{ background: user?.color }">
            <img v-if="user?.avatar" :src="user.avatar" alt="" />
            <template v-else>{{ user?.nickname?.[0] }}</template>
          </span>
          <div class="avatar-ops">
            <button class="btn btn-primary sm" @click="pickAvatar">上传新头像</button>
            <button v-if="user?.avatar" class="btn btn-ghost sm" @click="clearAvatar">恢复默认</button>
            <input ref="fileEl" type="file" accept="image/*" hidden @change="onFile" />
            <p class="tip-line">支持 JPG/PNG，自动裁剪为 200×200 圆形展示</p>
          </div>
        </div>
      </section>

      <!-- 基本资料 -->
      <section class="card">
        <h2>基本资料</h2>
        <label class="fld"><span>用户名</span><input v-model="form.username" /></label>
        <label class="fld"><span>昵称</span><input v-model="form.nickname" /></label>
        <label class="fld"><span>个性签名</span><input v-model="form.slogan" maxlength="60" /></label>
        <div class="fld"><span>主题色</span>
          <div class="swatches">
            <button v-for="c in COLORS" :key="c" class="sw" :class="{ on: form.color === c }"
                    :style="{ background: c }" @click="form.color = c"></button>
          </div>
        </div>
        <div class="fld"><span>兴趣标签</span>
          <div class="tags">
            <button v-for="t in TAGS" :key="t" class="tag" :class="{ on: form.interest.includes(t) }" @click="toggleTag(t)">
              {{ t }}
            </button>
          </div>
          <p class="tip-line in-fld">兴趣标签决定新用户/冷启动时的首批推荐（最多 4 个）</p>
        </div>
        <button class="btn btn-primary save" :disabled="saving" @click="saveProfile">
          {{ saving ? '保存中…' : '保存资料' }}
        </button>
      </section>

      <!-- 修改密码 -->
      <section class="card">
        <h2>修改密码</h2>
        <label class="fld"><span>当前密码</span><input v-model="pwd.old" type="password" placeholder="输入当前密码" /></label>
        <label class="fld"><span>新密码</span><input v-model="pwd.new1" type="password" placeholder="至少 6 位" /></label>
        <label class="fld"><span>确认新密码</span><input v-model="pwd.new2" type="password" placeholder="再输入一次" /></label>
        <button class="btn btn-primary save" @click="changePwd">修改密码</button>
      </section>
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
.body { max-width: 760px; margin: 0 auto; padding: 16px; display: flex; flex-direction: column; gap: 14px; }

.card { background: #fff; border-radius: 12px; padding: 20px 24px 24px; box-shadow: 0 0 0 1px rgba(0,0,0,.04); }
.card h2 { font-size: 16px; margin-bottom: 16px; padding-bottom: 10px; border-bottom: 1px solid var(--line); }

.avatar-row { display: flex; align-items: center; gap: 20px; }
.avatar {
  width: 76px; height: 76px; border-radius: 50%; color: #fff; font-weight: 800; font-size: 30px;
  display: flex; align-items: center; justify-content: center; overflow: hidden; flex: none;
}
.avatar img { width: 100%; height: 100%; object-fit: cover; display: block; }
.avatar-ops { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.sm { padding: 8px 18px; font-size: 13px; }
.tip-line { font-size: 11.5px; color: var(--ink-3); margin-top: 8px; }
.tip-line.in-fld { margin-top: 6px; }

.fld { display: flex; align-items: flex-start; gap: 14px; margin-bottom: 14px; }
.fld > span { width: 76px; flex: none; font-size: 13px; color: var(--ink-2); padding-top: 9px; }
.fld input {
  flex: 1; height: 38px; border: 1px solid #e5e5e5; border-radius: 8px;
  padding: 0 12px; font-size: 13.5px; outline: none;
}
.fld input:focus { border-color: var(--brand); }
.swatches { display: flex; gap: 10px; padding-top: 6px; }
.sw { width: 28px; height: 28px; border-radius: 50%; border: 3px solid transparent; }
.sw.on { border-color: var(--ink); }
.tags { display: flex; flex-wrap: wrap; gap: 8px; padding-top: 4px; }
.tag {
  font-size: 12.5px; color: var(--ink-2); background: #f7f7f8;
  border: 1px solid #eee; border-radius: 999px; padding: 6px 14px;
}
.tag.on { color: var(--brand); border-color: var(--brand); background: #fff4ec; font-weight: 600; }
.save { margin-top: 4px; padding: 11px 34px; }
</style>
