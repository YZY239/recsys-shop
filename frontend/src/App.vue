<script setup>
// 测试辅助浮窗（TEST-ONLY 独立模块：删除本组件引用即不影响任何正式功能）
import TestPanel from './components/TestPanel.vue'
</script>

<template>
  <router-view v-slot="{ Component }">
    <keep-alive include="HomeView">
      <component :is="Component" />
    </keep-alive>
  </router-view>
  <TestPanel />
</template>
