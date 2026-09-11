// api.js —— 后端接口封装（登录 / 推荐 / 详情 / 相似 / 行为上报）
const BASE = '/api'

function getToken() { return sessionStorage.getItem('recsys_token') || '' }
function setToken(t) { sessionStorage.setItem('recsys_token', t) }
function getUser() {
  const s = sessionStorage.getItem('recsys_user')
  return s ? JSON.parse(s) : null
}
function setUser(u) { sessionStorage.setItem('recsys_user', JSON.stringify(u)) }
function clearAuth() { sessionStorage.removeItem('recsys_token'); sessionStorage.removeItem('recsys_user') }

async function request(path, { method = 'GET', body } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = 'Bearer ' + token
  const res = await fetch(BASE + path, {
    method, headers,
    body: body ? JSON.stringify(body) : undefined
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok && data.code === 401) {
    clearAuth()
  }
  return data
}

export const api = {
  // 登录 / 注册 / 登出
  login: (username, password) =>
    request('/auth/login', { method: 'POST', body: { username, password } }),
  register: (username, password, nickname, interest = []) =>
    request('/auth/register', { method: 'POST', body: { username, password, nickname, interest } }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  // 推荐列表接口（分页）
  recommend: (page, pageSize = 8) =>
    request(`/recommend?page=${page}&page_size=${pageSize}`),
  // 商品详情接口
  item: (code) => request(`/items/${code}`),
  // 相似商品接口
  similar: (code, limit = 4) => request(`/items/${code}/similar?limit=${limit}`),
  // 行为上报接口（点击日志 → 返回实时插入候选）
  behavior: (itemCode, action = 'click') =>
    request('/behaviors', { method: 'POST', body: { item_code: itemCode, action } }),
  profile: () => request('/profile'),
  // 账号设置：资料（昵称/用户名/配色/签名/兴趣）、密码、头像
  profileUpdate: (fields) => request('/profile/update', { method: 'POST', body: fields }),
  passwordChange: (oldPassword, newPassword) =>
    request('/profile/password', { method: 'POST', body: { old_password: oldPassword, new_password: newPassword } }),
  avatarUpdate: (avatar) => request('/profile/avatar', { method: 'POST', body: { avatar } }),
  // 我的收藏
  favorites: () => request('/favorites'),
  favToggle: (itemCode) => request('/favorites/toggle', { method: 'POST', body: { item_code: itemCode } }),
  favStatus: (itemCode) => request(`/favorites/status?item_code=${encodeURIComponent(itemCode)}`),
  // 购物车
  cart: () => request('/cart'),
  cartAdd: (itemCode, qty = 1) => request('/cart/add', { method: 'POST', body: { item_code: itemCode, qty } }),
  cartQty: (itemCode, qty) => request('/cart/qty', { method: 'POST', body: { item_code: itemCode, qty } }),
  cartRemove: (itemCode) => request('/cart/remove', { method: 'POST', body: { item_code: itemCode } }),
  // 测试辅助接口（TEST-ONLY：清空行为记录与冷却，测试面板「清理测试数据」使用）
  testClean: () => request('/test/clean', { method: 'POST' })
}

export { getToken, setToken, getUser, setUser, clearAuth }
