import request from '@/utils/request'

export function listDocumentsApi() {
  return request({ url: '/api/documents', method: 'get' })
}

export function uploadDocumentsApi(files) {
  const data = new FormData()
  for (const file of files) {
    data.append('files', file)
  }
  // 入库需等待文本解析与 Embedding，关闭本次请求的客户端超时
  return request({ url: '/api/documents', method: 'post', data, timeout: 0 })
}

export function previewDocumentApi(id) {
  return request({ url: `/api/documents/${id}/preview`, method: 'get' })
}

export function reingestDocumentApi(id) {
  return request({ url: `/api/documents/${id}/reingest`, method: 'post', timeout: 0 })
}

export function deleteDocumentApi(id) {
  return request({ url: `/api/documents/${id}`, method: 'delete' })
}
