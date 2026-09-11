import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from './api'

import LoginView from './views/LoginView.vue'
import HomeView from './views/HomeView.vue'
import DetailView from './views/DetailView.vue'
import FavoritesView from './views/FavoritesView.vue'
import CartView from './views/CartView.vue'
import ProfileView from './views/ProfileView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'login', component: LoginView },
    { path: '/home', name: 'home', component: HomeView },
    { path: '/item/:code', name: 'detail', component: DetailView },
    { path: '/favorites', name: 'favorites', component: FavoritesView },
    { path: '/cart', name: 'cart', component: CartView },
    { path: '/profile', name: 'profile', component: ProfileView },
    { path: '/:pathMatch(.*)*', redirect: '/home' }
  ]
})

// 未登录一律回登录页
router.beforeEach((to) => {
  if (to.name !== 'login' && !getToken()) return { name: 'login' }
  return true
})

export default router
