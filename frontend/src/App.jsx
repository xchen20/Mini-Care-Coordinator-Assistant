import { useState, useEffect, useRef, useMemo } from 'react'
import axios from 'axios'
import './App.css'
import { marked } from 'marked'

const API_BASE_URL = 'http://localhost:5000'

function WelcomeCard({ onPick }) {
  const examples = [
    'What is the patient’s medical visit history',
    'What insurances PPTH Orthopedics accept ?',
    'What other providers if Dr. House is not available ?',
    'What providers does the patient have ?'
  ]
  return (
    <div className="empty-state">
      <h2>👋 Welcome</h2>
      <p>Ask me anything about scheduling and insurance for the selected patient.</p>
      <div className="chips">
        {examples.map((ex) => (
          <button key={ex} className="chip" onClick={() => onPick(ex)}>{ex}</button>
        ))}
      </div>
      <div className="hint">
        <span className="kbd">↵ Enter</span> to send • <span className="kbd">🎤</span> to dictate
      </div>
    </div>
  )
}

function PatientSnapshot({ patient }) {
  if (!patient) return null
  return (
    <aside className="info-panel">
      <div className="card">
        <div className="avatar">{patient.name?.[0] ?? 'P'}</div>
        <div className="title">{patient.name}</div>
        <div className="meta">
          <div><span>🆔</span> ID: {patient.id}</div>
          {patient.dob && <div><span>🎂</span> DOB: {patient.dob}</div>}
          {patient.pcp && <div><span>👩‍⚕️</span> PCP: {patient.pcp}</div>}
        </div>
      </div>

      <div className="card">
        <div className="card-title">Quick actions</div>
        <div className="actions">
          <button onClick={() => navigator.clipboard?.writeText(patient.name ?? '')}>
            Copy patient name
          </button>
        </div>
      </div>

      <div className="card subtle">
        <div className="card-title">Tips</div>
        <ul className="tips">
          <li>Ask: “What insurances does this patient have?”</li>
          <li>Say: “Book surgery consult.”</li>
          <li>Try: “If Dr. Yang isn’t available, who else is?”</li>
        </ul>
      </div>
    </aside>
  )
}

function App() {
  const [patients, setPatients] = useState([])
  const [selectedPatientId, setSelectedPatientId] = useState('')
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const chatEndRef = useRef(null)
  const currentAudioRef = useRef(null)

  // Load patients on mount
  useEffect(() => {
    axios.get(`${API_BASE_URL}/patients`)
      .then(res => {
        setPatients(res.data)
        if (res.data.length > 0) setSelectedPatientId(res.data[0].id)
      })
      .catch(err => console.error('Error fetching patients:', err))
  }, [])

  const selectedPatient = useMemo(
    () => patients.find(p => p.id === parseInt(selectedPatientId)),
    [patients, selectedPatientId]
  )

  // Reset chat when patient changes
  useEffect(() => {
    if (selectedPatient) {
      setMessages([{ role: 'assistant', content: `Hello! I'm ready to assist with patient **${selectedPatient.name}**. How can I help?` }])
    }
  }, [selectedPatientId, patients]) // keep your original behavior

  // Auto scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const playAudio = async (text) => {
    if (currentAudioRef.current && !currentAudioRef.current.paused) {
      currentAudioRef.current.pause()
      currentAudioRef.current.currentTime = 0
      if (currentAudioRef.current.dataset.text === text) {
        currentAudioRef.current = null
        return
      }
    }

    try {
      const response = await axios.post(`${API_BASE_URL}/synthesize-speech`,
        { text },
        { responseType: 'blob' }
      )
      const audioUrl = URL.createObjectURL(response.data)
      const audio = new Audio(audioUrl)
      audio.dataset.text = text
      currentAudioRef.current = audio
      audio.play()
    } catch (error) {
      console.error('Error playing audio:', error)
    }
  }

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || !selectedPatientId) return
    const newMessages = [...messages, { role: 'user', content: inputMessage }]
    setMessages([...newMessages, { role: 'assistant', content: 'Thinking... 🧠' }])
    setInputMessage('')
    setIsLoading(true)

    try {
      const response = await axios.post(`${API_BASE_URL}/chat`, {
        prompt: inputMessage,
        patient_id: selectedPatientId,
      })
      const assistantResponse = response.data.response
      setMessages([...newMessages, { role: 'assistant', content: assistantResponse }])
    } catch (error) {
      console.error('Error sending message:', error)
      setMessages([...newMessages, { role: 'assistant', content: 'Sorry, I encountered an error.' }])
    }
    setIsLoading(false)
  }

  const handleVoiceClick = async () => {
    if (isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
      return
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    mediaRecorderRef.current = new MediaRecorder(stream)
    audioChunksRef.current = []

    mediaRecorderRef.current.ondataavailable = (e) => {
      audioChunksRef.current.push(e.data)
    }
    mediaRecorderRef.current.onstop = async () => {
      const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' })
      const formData = new FormData()
      formData.append('file', audioBlob, 'recording.wav')
      setIsTranscribing(true)
      try {
        const res = await axios.post(`${API_BASE_URL}/transcribe`, formData)
        setInputMessage(res.data.text)
      } catch (err) {
        console.error('Error transcribing audio:', err)
      } finally {
        setIsTranscribing(false)
      }
    }
    mediaRecorderRef.current.start()
    setIsRecording(true)
  }

  const handleChipPick = (text) => setInputMessage(text)

  const showEmptyState =
    messages.length <= 1 ||
    (messages.length === 1 && messages[0]?.content?.includes("I'm ready to assist"))

  return (
    <div className="app-container">
      <div className="sidebar">
        <h2>Patient Selection</h2>
        <select value={selectedPatientId} onChange={e => setSelectedPatientId(e.target.value)}>
          {patients.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>

      <div className="chat-container">
        <h1>🩺 Mini Care Coordinator Assistant</h1>
        <p>Your intelligent assistant for patient care coordination.</p>

        {showEmptyState ? (
          <WelcomeCard onPick={handleChipPick} />
        ) : (
          <div className="chat-box">
            {messages.map((msg, index) => (
              <div key={index} className={`message-wrapper ${msg.role}`}>
                <div className={`message ${msg.role}`}>
                  <div dangerouslySetInnerHTML={{ __html: marked.parse(msg.content) }} />
                </div>
                {msg.role === 'assistant' && msg.content !== 'Thinking... 🧠' && (
                  <button type="button" className="play-audio-btn" onClick={() => playAudio(msg.content)}>🔊</button>
                )}
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>
        )}

        <div className="input-area">
          <button
            type="button"
            onClick={handleVoiceClick}
            className={`voice-btn ${isRecording ? 'recording' : ''}`}
            disabled={isLoading || isTranscribing}
            title="Hold to record"
          >
            {isRecording ? '🔴' : '🎤'}
          </button>
          <input
            disabled={isLoading || isTranscribing}
            type="text"
            value={inputMessage}
            onChange={e => setInputMessage(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSendMessage()}
            placeholder={isTranscribing ? "Transcribing audio..." : "Type a message or use the microphone..."}
          />
          <button type="button" onClick={handleSendMessage} disabled={isLoading || isTranscribing}>Send</button>
        </div>
      </div>

      <PatientSnapshot patient={selectedPatient} />
    </div>
  )
}

export default App
