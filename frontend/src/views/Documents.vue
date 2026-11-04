<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">文档管理</div>
      </template>

      <el-alert
        v-if="!isAdmin"
        title="仅管理员可以管理课程资料，请切换账号"
        type="warning"
        :closable="false"
        show-icon
      />

      <template v-else>
        <div style="margin-bottom: 12px">
          <el-upload
            ref="uploadRef"
            v-model:file-list="fileList"
            :auto-upload="false"
            :disabled="uploadLoading"
            multiple
            accept=".txt,.md,.pdf,.docx"
          >
            <el-button type="primary">选择文件</el-button>
          </el-upload>
          <el-button
            type="success"
            style="margin-top: 8px"
            :loading="uploadLoading"
            @click="handleUpload"
          >
            上传并入库
          </el-button>
          <div style="margin-top: 6px; color: #909399; font-size: 12px">
            支持 .txt / .md / .pdf / .docx，单个文件不超过 100 MiB。同名不可重复；扫描版 PDF
            可能抽不出文字。同一批中任一上传或入库失败，整批撤销。
          </div>
        </div>

        <el-table
          v-loading="loading"
          :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#333' }"
          :data="pagedData"
          style="width: 100%"
        >
          <el-table-column prop="original_name" label="文件名" min-width="220" show-overflow-tooltip />
          <el-table-column label="大小" width="110">
            <template #default="{ row }">{{ formatSize(row.size) }}</template>
          </el-table-column>
          <el-table-column prop="ext" label="类型" width="90" />
          <el-table-column label="已入库" width="90">
            <template #default="{ row }">
              <el-tag :type="row.ingested ? 'success' : 'info'" size="small">
                {{ row.ingested ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="create_time" label="创建时间" width="180" />
          <el-table-column label="操作" width="230" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" text bg size="small" @click="handlePreview(row)">
                预览
              </el-button>
              <el-button
                type="primary"
                text
                bg
                size="small"
                :loading="reingestLoadingId === row.id"
                @click="handleReingest(row)"
              >
                重新入库
              </el-button>
              <el-button type="danger" text bg size="small" @click="handleDelete(row)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div style="margin-top: 10px; display: flex; justify-content: flex-end">
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="allData.length"
            background
            layout="total, prev, pager, next"
            @current-change="() => {}"
          />
        </div>
      </template>
    </el-card>

    <el-dialog
      v-model="previewVisible"
      :title="previewTitle"
      width="720"
      top="6vh"
    >
      <div v-loading="previewLoading" style="min-height: 160px">
        <div v-if="previewError" style="color: #f56c6c">{{ previewError }}</div>
        <pre v-else class="preview-text">{{ previewText }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
defineOptions({ name: 'Documents' })
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUser } from '@/utils/user'
import {
  deleteDocumentApi,
  listDocumentsApi,
  previewDocumentApi,
  reingestDocumentApi,
  uploadDocumentsApi
} from '@/api/document'

const { userInfo } = useUser()
const isAdmin = computed(() => userInfo.value?.role === 'admin')

const allData = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const pagedData = computed(() =>
  allData.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value)
)

const uploadRef = ref()
const fileList = ref([])
const uploadLoading = ref(false)
const reingestLoadingId = ref(null)

const previewVisible = ref(false)
const previewTitle = ref('')
const previewText = ref('')
const previewError = ref('')
const previewLoading = ref(false)
let previewRequestId = 0

const formatSize = (size) => {
  if (size == null) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

const load = async () => {
  if (!isAdmin.value) return
  loading.value = true
  try {
    const res = await listDocumentsApi()
    if (res.code === 200) {
      allData.value = res.data || []
      const maxPage = Math.max(1, Math.ceil(allData.value.length / pageSize.value))
      if (page.value > maxPage) page.value = maxPage
    }
  } finally {
    loading.value = false
  }
}

const handleUpload = async () => {
  const files = fileList.value.map((item) => item.raw).filter(Boolean)
  if (!files.length) {
    ElMessage.warning('请先选择文件')
    return
  }
  uploadLoading.value = true
  try {
    const res = await uploadDocumentsApi(files)
    if (res.code === 200) {
      ElMessage.success(`已上传并入库 ${res.data?.length || files.length} 份资料`)
      uploadRef.value?.clearFiles()
      fileList.value = []
      await load()
    }
  } catch {
    // 请求拦截器已提示；失败时保留所选文件，便于修正后重试
  } finally {
    uploadLoading.value = false
  }
}

const handlePreview = async (row) => {
  const requestId = ++previewRequestId
  previewVisible.value = true
  previewTitle.value = `预览：${row.original_name}`
  previewText.value = ''
  previewError.value = ''
  previewLoading.value = true
  try {
    const res = await previewDocumentApi(row.id)
    if (requestId !== previewRequestId) return
    if (res.code === 200) {
      previewText.value = res.data?.text || ''
    } else {
      previewError.value = res.message || '预览失败'
    }
  } catch {
    if (requestId === previewRequestId) previewError.value = '预览请求失败'
  } finally {
    if (requestId === previewRequestId) previewLoading.value = false
  }
}

const handleReingest = async (row) => {
  if (reingestLoadingId.value !== null) return
  reingestLoadingId.value = row.id
  try {
    const res = await reingestDocumentApi(row.id)
    if (res.code === 200) ElMessage.success(`「${row.original_name}」已重新入库`)
  } catch {
    // 请求拦截器已提示
  } finally {
    reingestLoadingId.value = null
    // 失败时状态可能由「是」变成「否」，也要刷新列表
    await load()
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确认删除文档「${row.original_name}」及其原文件和向量片段？`,
      '确认删除',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    const res = await deleteDocumentApi(row.id)
    if (res.code === 200) ElMessage.success('已删除')
  } catch {
    // 错误已由请求拦截器提示
  } finally {
    await load()
  }
}

onMounted(() => {
  load()
})
</script>

<style scoped>
.preview-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
  max-height: 60vh;
  overflow: auto;
}
</style>
