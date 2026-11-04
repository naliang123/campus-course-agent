<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">学习计划</div>
      </template>
      <el-form @submit.prevent>
        <el-input
          v-model="content"
          type="textarea"
          :rows="3"
          maxlength="2000"
          show-word-limit
          placeholder="写下学习计划；助手生成的计划会在你明确要求「保存」后写入这里"
        />
        <div style="margin-top: 8px; display: flex; justify-content: flex-end">
          <el-button type="primary" :loading="saving" @click="handleSave">保存计划</el-button>
        </div>
      </el-form>
    </el-card>

    <el-card style="margin-top: 12px">
      <template #header>
        <div style="font-size: 16px; font-weight: bold">历史计划</div>
      </template>
      <el-table
        v-loading="loading"
        :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#333' }"
        :data="tableData"
        style="width: 100%"
      >
        <el-table-column label="内容摘要" min-width="280">
          <template #default="{ row }">{{ summary(row.content) }}</template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="180" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" text bg @click="handleView(row)">查看</el-button>
            <el-button type="danger" text bg @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
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

    <el-dialog v-model="detailVisible" title="计划详情" width="640">
      <div class="plan-markdown" v-html="renderedDetail"></div>
    </el-dialog>
  </div>
</template>

<script setup>
defineOptions({ name: 'StudyPlan' })
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { createStudyPlan, deleteStudyPlan, listStudyPlans } from '@/api/studyPlan'

const content = ref('')
const saving = ref(false)
const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const params = reactive({ page: 1, pageSize: 10 })
const detailVisible = ref(false)
const detailText = ref('')

// marked 解析 Markdown，DOMPurify 清理 HTML 防 XSS
const renderedDetail = computed(() =>
  DOMPurify.sanitize(marked.parse(detailText.value || ''))
)

const summary = (text) =>
  (text || '')
    .replace(/[#>*`_\-\[\]()!]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

const load = async () => {
  loading.value = true
  try {
    const res = await listStudyPlans({ page: params.page, page_size: params.pageSize })
    if (res.code === 200) {
      tableData.value = res.data?.list || []
      total.value = res.data?.total || 0
    }
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  if (!content.value.trim()) {
    ElMessage.warning('请输入学习计划内容')
    return
  }
  saving.value = true
  try {
    const res = await createStudyPlan(content.value)
    if (res.code === 200) {
      content.value = ''
      ElMessage.success('已保存')
      params.page = 1
      load()
    }
  } finally {
    saving.value = false
  }
}

const handleView = (row) => {
  detailText.value = row.content
  detailVisible.value = true
}

const handleDelete = (row) => {
  ElMessageBox.confirm('确认删除这条学习计划？', '确认删除', { type: 'warning' }).then(
    async () => {
      const res = await deleteStudyPlan(row.id)
      if (res.code === 200) {
        ElMessage.success('已删除')
        load()
      }
    }
  )
}

onMounted(() => {
  load()
})
</script>

<style scoped>
.plan-markdown {
  line-height: 1.7;
  white-space: normal;
}
.plan-markdown :deep(table) {
  border-collapse: collapse;
}
.plan-markdown :deep(td),
.plan-markdown :deep(th) {
  border: 1px solid #dcdfe6;
  padding: 6px 10px;
}
</style>
