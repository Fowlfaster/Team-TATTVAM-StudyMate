import axios from 'axios'

export const API_BASE_URL = 'http://localhost:8000'
export const AUTH_TOKEN_KEY = 'studymate_token'
export const DEMO_EMAIL = 'demo@studymate.ai'
export const DEMO_PASSWORD = 'studymate123'

export const getAuthToken = () => window.localStorage.getItem(AUTH_TOKEN_KEY)
export const setAuthToken = (token) => window.localStorage.setItem(AUTH_TOKEN_KEY, token)
export const clearAuthToken = () => window.localStorage.removeItem(AUTH_TOKEN_KEY)

export function getApiErrorMessage(error, fallback = 'Something went wrong. Please try again.') {
  const status = error?.response?.status
  const detail = error?.response?.data?.detail

  if (status === 429) {
    return typeof detail === 'string'
      ? detail
      : 'The AI service is busy right now. Wait a moment, then try again.'
  }
  if (error?.code === 'ECONNABORTED') {
    return 'That request took too long. Please try again.'
  }
  if (!error?.response) {
    return 'StudyMate could not reach the backend. Check that it is running, then try again.'
  }
  if (typeof detail === 'string') {
    if (detail.includes('GROQ_API_KEY is not configured')) {
      return 'AI features are not configured yet. Add a GROQ_API_KEY to backend/.env.'
    }
    return detail
  }
  if (status >= 500) {
    return 'StudyMate hit a temporary server issue. Please try again shortly.'
  }
  return fallback
}

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = getAuthToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      clearAuthToken()
      if (!['/login', '/signup'].includes(window.location.pathname)) {
        window.location.assign('/login')
      }
    }
    return Promise.reject(error)
  },
)

export const signup = (name, email, password) =>
  api.post('/auth/signup', { name, email, password }).then((response) => response.data)

export const login = (email, password) =>
  api.post('/auth/login', { email, password }).then((response) => response.data)

export const getCurrentUser = () => api.get('/auth/me').then((response) => response.data)

export const getSubjects = () => api.get('/subjects').then((response) => response.data)
export const createSubject = (subject) => api.post('/subjects', subject).then((response) => response.data)
export const updateSubject = (subjectId, subject) => api.patch(`/subjects/${subjectId}`, subject).then((response) => response.data)
export const deleteSubject = (subjectId) => api.delete(`/subjects/${subjectId}`).then((response) => response.data)
export const getSources = (subjectId) => api.get('/sources', { params: subjectId ? { subject_id: subjectId } : {} }).then((response) => response.data)
export const deleteSource = (sourceId) => api.delete(`/sources/${sourceId}`).then((response) => response.data)
export const getSourceTopics = (sourceId) =>
  api.get(`/sources/${sourceId}/topics`).then((response) => response.data)
export const explainTopic = (topicId, level) =>
  api.post('/explain', { topic_id: topicId, level }).then((response) => response.data)
export const analyzeSource = (sourceId, level) =>
  api.post('/analyze', { source_id: sourceId, level }).then((response) => response.data)
export const explainSimply = (subjectId, sourceId, topicIds = [], regenerate = false) =>
  api.post('/explain/simple', { subject_id: subjectId, source_id: sourceId || null, topic_ids: topicIds, regenerate }).then((response) => response.data)
export const explainKeyTopics = (subjectId, sourceId, topicIds = [], maxTopics = 5, regenerate = false) =>
  api.post('/explain/key-topics', { subject_id: subjectId, source_id: sourceId || null, topic_ids: topicIds, max_topics: maxTopics, regenerate }).then((response) => response.data)
export const retryKeyTopic = (topic, subjectId, sourceId, topicIds = [], maxTopics = 5) =>
  api.post(`/explain/key-topics/${topic.topic_id}/retry`, {
    subject_id: subjectId,
    source_id: sourceId || null,
    topic_ids: topicIds,
    topic_id: topic.topic_id,
    why_it_matters: topic.why_it_matters,
    max_topics: maxTopics,
  }).then((response) => response.data)
export const startQuizSession = (filters) =>
  api.post('/quiz/start', {
    subject_id: filters.subjectId,
    source_ids: filters.sourceIds ?? [],
    topic_ids: filters.topicIds ?? [],
    num_questions: filters.numQuestions,
  }).then((response) => response.data)
export const createEvaluationQuestion = (topicId) =>
  api.post('/evaluate/question', { topic_id: topicId }).then((response) => response.data)
export const submitEvaluationAnswer = (evaluationId, answer) =>
  api.post('/evaluate/answer', { evaluation_id: evaluationId, answer }).then((response) => response.data)

function selectionQuery({ sourceIds = [], topics = [] } = {}) {
  const params = new URLSearchParams()
  sourceIds.forEach((sourceId) => params.append('source_ids', sourceId))
  topics.forEach((topic) => params.append('topics', topic))
  const query = params.toString()
  return query ? `?${query}` : ''
}

export const uploadFile = (file, subjectId) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('subject_id', subjectId)
  return api.post('/upload', formData).then((response) => response.data)
}

export const uploadYoutube = (url, subjectId) =>
  api.post('/upload/youtube', { url, subject_id: subjectId }).then((response) => response.data)

export const askQuestion = (question, style, filters = {}) =>
  api.post('/ask', {
    question,
    style,
    source_ids: filters.sourceIds ?? [],
    topics: filters.topics ?? [],
    subject_id: filters.subjectId ?? null,
  }).then((response) => response.data)

export const getNextQuiz = (filters = {}) => {
  const params = new URLSearchParams(selectionQuery(filters).slice(1))
  if (filters.sourceId != null) params.set('source_id', filters.sourceId)
  if (filters.topicId != null) params.set('topic_id', filters.topicId)
  if (filters.sessionId) params.set('session_id', filters.sessionId)
  if (filters.subjectId != null) params.set('subject_id', filters.subjectId)
  const query = params.toString()
  return api.get(`/quiz/next${query ? `?${query}` : ''}`).then((response) => response.data)
}

export const submitQuizAnswer = (questionId, selectedIndex) =>
  api.post('/quiz/answer', {
    question_id: questionId,
    selected_index: selectedIndex,
  }).then((response) => response.data)

export const getMastery = (filters = {}) =>
  api.get(`/mastery${selectionQuery(filters)}`).then((response) => response.data)

export const getRanking = (filters = {}) =>
  api.get(`/ranking${selectionQuery(filters)}`, {
    params: filters.subjectId ? { subject_id: filters.subjectId } : {},
  }).then((response) => response.data)
