<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">课程助手</div>
      </template>

      <div ref="messageBox" class="messages">
        <div v-for="(item, index) in messages" :key="index" class="message-row" :class="item.role">
          <template v-if="item.role === 'user'">
            <div class="bubble user-bubble">{{ item.content }}</div>
          </template>
          <template v-else>
            <div class="bubble assistant-bubble">
              <div v-if="item.process.length" class="process">
                <div v-for="(line, i) in item.process" :key="i" class="process-line">
                  {{ line }}
                </div>
              </div>
              <div v-if="item.content" class="answer" v-html="renderMarkdown(item.content)"></div>
              <div v-else-if="!item.incomplete" class="thinking">正在思考…</div>
              <div v-if="item.incomplete" class="incomplete">本轮未完成，未加入多轮历史</div>
            </div>
          </template>
        </div>
      </div>

      <div class="composer">
        <el-input
          v-model="input"
          type="textarea"
          :rows="3"
          :disabled="thinking"
          placeholder="输入问题，例如：我明天有什么课？实验需要预习吗？帮我生成一份学习计划并保存"
          @keydown.enter.exact.prevent="send"
        />
        <div class="composer-footer">
          <span class="tip">Enter 发送 · Shift + Enter 换行 · 刷新页面会清空对话</span>
          <el-button type="primary" :loading="thinking" @click="send">发送</el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
defineOptions({ name: 'Chat' })
import { nextTick, reactive, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { streamChat } from '@/api/chat'

const toolLabels = {
  get_my_schedules: '查询我的课表',
  search_course_docs: '检索课程资料',
  save_study_plan: '保存学习计划'
}

const intro =
  '你好，我是校园课程助手。你可以查询自己的课表、提问课程资料，也可以让我制定学习计划；' +
  '确认后说"保存"，我才会写入学习计划。'

// messages 用于页面显示；history 只保存成功问答，不含过程区内容
const messages = ref([
  { role: 'assistant', content: intro, process: [], incomplete: false }
])
const history = ref([])
const input = ref('')
const thinking = ref(false)
const messageBox = ref()

const renderMarkdown = (text) => DOMPurify.sanitize(marked.parse(text || ''))

const scrollToBottom = async () => {
  await nextTick()
  if (messageBox.value) messageBox.value.scrollTop = messageBox.value.scrollHeight
}

const send = async () => {
  const question = input.value.trim()
  if (!question || thinking.value) return

  // 发送前先复制历史，本轮问题不会同时进入 question 和 history
  const pendingHistory = [...history.value]
  messages.value.push({ role: 'user', content: question, process: [], incomplete: false })
  // 必须是响应式对象：后续 token / done / error 会直接修改它的字段，
  // 若 push 普通对象再改原对象，页面不会更新
  const answer = reactive({
    role: 'assistant',
    content: '',
    process: [],
    incomplete: false
  })
  messages.value.push(answer)
  input.value = ''
  thinking.value = true
  await scrollToBottom()

  const handleEvent = (event) => {
    switch (event.type) {
      case 'status':
        answer.process.push(event.message)
        break
      case 'tool_start':
        answer.process.push(`开始：${toolLabels[event.name] || event.name}`)
        break
      case 'tool_end':
        answer.process.push(`已返回：${toolLabels[event.name] || event.name}`)
        break
      case 'token':
        answer.content += event.content || ''
        break
      case 'done':
        // 完整答案由 done.answer 确定，覆盖流式片段并加入成功历史
        answer.content = event.answer || answer.content
        history.value = [
          ...pendingHistory,
          { role: 'user', content: question },
          { role: 'assistant', content: answer.content }
        ]
        break
      case 'error':
        answer.incomplete = true
        answer.process.push(`失败：${event.message || '未知错误'}`)
        input.value = question
        break
      default:
        break
    }
    scrollToBottom()
  }

  try {
    await streamChat({ question, history: pendingHistory }, handleEvent)
  } catch (err) {
    // 请求失败或连接中断同样按未完成处理，本轮不加入历史
    answer.incomplete = true
    answer.process.push(`失败：${err?.message || '请求失败'}`)
    input.value = question
    await scrollToBottom()
  } finally {
    thinking.value = false
    await scrollToBottom()
  }
}
</script>

<style scoped>
.messages {
  height: 58vh;
  overflow-y: auto;
  padding: 8px 4px 16px;
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 6px;
}
.message-row {
  display: flex;
  margin: 12px 8px;
}
.message-row.user {
  justify-content: flex-end;
}
.bubble {
  max-width: 78%;
  border-radius: 8px;
  padding: 10px 14px;
  line-height: 1.7;
  word-break: break-word;
}
.user-bubble {
  background: #409eff;
  color: #fff;
  white-space: pre-wrap;
}
.assistant-bubble {
  background: #fff;
  border: 1px solid #e4e7ed;
}
.process {
  border-left: 3px solid #c0c4cc;
  padding-left: 10px;
  margin-bottom: 8px;
  color: #909399;
  font-size: 12px;
}
.process-line {
  margin: 2px 0;
}
.answer :deep(table) {
  border-collapse: collapse;
}
.answer :deep(td),
.answer :deep(th) {
  border: 1px solid #dcdfe6;
  padding: 6px 10px;
}
.answer :deep(pre) {
  background: #f5f7fa;
  padding: 8px;
  overflow-x: auto;
}
.thinking {
  color: #909399;
}
.incomplete {
  margin-top: 8px;
  color: #f56c6c;
  font-size: 12px;
}
.composer {
  margin-top: 12px;
}
.composer-footer {
  margin-top: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.tip {
  color: #909399;
  font-size: 12px;
}
</style>
