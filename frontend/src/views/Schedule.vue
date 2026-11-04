<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">我的课表</div>
      </template>
      <div style="margin-bottom: 10px">
        <el-date-picker
          v-model="params.date"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="按日期筛选，清空则显示全部"
          style="width: 240px; margin-right: 8px"
          clearable
          @change="handleSearch"
        />
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
      </div>
      <el-table
        v-loading="loading"
        :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#333' }"
        :data="tableData"
        style="width: 100%"
      >
        <el-table-column prop="class_date" label="上课日期" width="140" />
        <el-table-column prop="period" label="节次" width="120" />
        <el-table-column prop="course_name" label="课程" min-width="160" />
        <el-table-column prop="course_code" label="课程代码" width="120" />
        <el-table-column prop="location" label="地点" min-width="160" />
      </el-table>
      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="params.page"
          v-model:page-size="params.pageSize"
          :total="total"
          background
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
defineOptions({ name: 'Schedule' })
import { Search } from '@element-plus/icons-vue'
import { onMounted, reactive, ref } from 'vue'
import { listSchedulesApi } from '@/api/schedule'

const params = reactive({ page: 1, pageSize: 10, date: '' })
const loading = ref(false)
const tableData = ref([])
const total = ref(0)

const load = async () => {
  loading.value = true
  try {
    const res = await listSchedulesApi({
      page: params.page,
      page_size: params.pageSize,
      date: params.date || undefined
    })
    if (res.code === 200) {
      tableData.value = res.data?.list || []
      total.value = res.data?.total || 0
    }
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  params.page = 1
  load()
}

onMounted(() => {
  load()
})
</script>
