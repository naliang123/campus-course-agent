import { getToken, logout } from '@/utils/auth'
import router from '@/router'

/**
 * 以 fetch 读取 SSE 流（EventSource 不能提交 POST JSON 与 Authorization）。
 * 每条消息格式为 `data: {"type": ...}`，以空行结束。
 */
export async function streamChat(body, onEvent) {
  const baseURL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
  const response = await fetch(`${baseURL}/api/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      Authorization: `Bearer ${getToken() || ''}`
    },
    body: JSON.stringify(body)
  })

  // fetch 不经过 axios 拦截器，单独处理鉴权与 HTTP 错误
  if (response.status === 401) {
    logout()
    router.push('/login')
    throw new Error('登录状态已失效，请重新登录')
  }
  if (!response.ok) {
    throw new Error(`请求失败（HTTP ${response.status}）`)
  }
  if (!response.body) {
    throw new Error('当前浏览器不支持流式响应')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let finished = false

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      // stream: true 保留未解码完整的字节；buffer 保留未收齐的事件
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (const part of parts) {
        for (const line of part.split('\n')) {
          if (!line.startsWith('data: ')) continue
          const event = JSON.parse(line.slice(6))
          onEvent(event)
          if (event.type === 'done' || event.type === 'error') finished = true
        }
      }
    }
  } finally {
    reader.releaseLock?.()
  }

  // 未收到终止事件就断开：按未完成处理，本轮不进入成功历史
  if (!finished) {
    onEvent({ type: 'error', message: '连接已中断，本轮回答未完成' })
  }
}
