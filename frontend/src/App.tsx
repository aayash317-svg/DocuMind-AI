import React, { useState, useEffect, useRef } from 'react';
import {
  Upload,
  FileText,
  Trash2,
  Send,
  Bot,
  User,
  CheckCircle2,
  AlertCircle,
  Database,
  Cpu,
  BookOpen,
  ChevronDown,
  ChevronUp,
  RefreshCw
} from 'lucide-react';

interface CitationSource {
  document_id: string;
  filename: string;
  page: number;
  chunk_id: string;
  snippet?: string;
}

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  insufficient_evidence?: boolean;
  sources?: CitationSource[];
  timestamp: string;
}

interface DocumentItem {
  document_id: string;
  filename: string;
  total_chunks: number;
  total_pages: number;
}

interface HealthStatus {
  status: string;
  ollama_model: string;
  embedding_model: string;
  indexed_documents_count: number;
}

export default function App() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'assistant',
      text: 'Hello! I am DocuMind AI. Upload your PDF, DOCX, or TXT documents and ask questions. Every answer is strictly grounded in retrieved evidence with verified citations.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [inputQuery, setInputQuery] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [isAnswering, setIsAnswering] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [expandedSources, setExpandedSources] = useState<{ [msgId: string]: boolean }>({});

  const chatEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch health and documents on mount
  useEffect(() => {
    fetchHealth();
    fetchDocuments();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isAnswering]);

  const fetchHealth = async () => {
    try {
      const res = await fetch('/health');
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
      }
    } catch {
      setHealth(null);
    }
  };

  const fetchDocuments = async () => {
    try {
      const res = await fetch('/documents');
      if (res.ok) {
        const data: DocumentItem[] = await res.json();
        setDocuments(data);
      }
    } catch (err) {
      console.error('Failed to load documents:', err);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/documents/upload', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        alert(`Upload error: ${err.detail || 'Failed to upload'}`);
      } else {
        await fetchDocuments();
        await fetchHealth();
      }
    } catch (err) {
      alert(`Network error uploading file: ${err}`);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDeleteDocument = async (docId: string, filename: string) => {
    if (!confirm(`Remove "${filename}" and delete its vector chunks?`)) return;

    try {
      const res = await fetch(`/documents/${docId}`, { method: 'DELETE' });
      if (res.ok) {
        setSelectedDocIds((prev) => prev.filter((id) => id !== docId));
        await fetchDocuments();
        await fetchHealth();
      }
    } catch (err) {
      alert(`Error deleting document: ${err}`);
    }
  };

  const toggleSelectDoc = (docId: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const query = inputQuery.trim();
    if (!query || isAnswering) return;

    const userMsg: ChatMessage = {
      id: `u_${Date.now()}`,
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuery('');
    setIsAnswering(true);

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: query,
          document_ids: selectedDocIds.length > 0 ? selectedDocIds : null,
          top_k: 5,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Chat query failed');
      }

      const data = await res.json();
      const botMsg: ChatMessage = {
        id: `a_${Date.now()}`,
        sender: 'assistant',
        text: data.answer,
        insufficient_evidence: data.insufficient_evidence,
        sources: data.sources || [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err_${Date.now()}`,
          sender: 'assistant',
          text: `Error processing request: ${err.message}`,
          insufficient_evidence: true,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setIsAnswering(false);
    }
  };

  const toggleSourceExpand = (msgId: string) => {
    setExpandedSources((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* Sidebar: Knowledge Base & Uploads */}
      <aside className="w-80 bg-slate-900 border-r border-slate-800 flex flex-col h-full">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="bg-emerald-500/10 p-2 rounded-lg text-emerald-400 border border-emerald-500/20">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h1 className="font-bold text-base tracking-tight text-white">DocuMind AI</h1>
              <p className="text-xs text-slate-400">Grounded RAG Assistant</p>
            </div>
          </div>
          <button
            onClick={() => {
              fetchHealth();
              fetchDocuments();
            }}
            title="Refresh status"
            className="p-1.5 hover:bg-slate-800 rounded-md text-slate-400 hover:text-slate-200 transition"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* Upload Button */}
        <div className="p-4">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".pdf,.docx,.txt"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="w-full flex items-center justify-center space-x-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 text-white text-sm font-medium py-2.5 px-4 rounded-lg transition shadow-sm border border-emerald-500/30"
          >
            {isUploading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Indexing Document...</span>
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                <span>Upload Document</span>
              </>
            )}
          </button>
          <p className="text-[11px] text-slate-500 mt-2 text-center">Supports PDF, DOCX, TXT</p>
        </div>

        {/* Document Library */}
        <div className="flex-1 overflow-y-auto px-4 py-2 space-y-2">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400 pb-1">
            <span>Documents ({documents.length})</span>
            {documents.length > 0 && (
              <span className="text-[11px] text-slate-500 font-normal">
                {selectedDocIds.length > 0 ? `${selectedDocIds.length} scoped` : 'All scoped'}
              </span>
            )}
          </div>

          {documents.length === 0 ? (
            <div className="p-6 text-center border border-dashed border-slate-800 rounded-lg text-slate-500 text-xs mt-2">
              <FileText className="w-8 h-8 mx-auto mb-2 text-slate-600 opacity-60" />
              No documents yet.<br />Upload a file to start searching.
            </div>
          ) : (
            documents.map((doc) => {
              const isSelected = selectedDocIds.includes(doc.document_id);
              return (
                <div
                  key={doc.document_id}
                  onClick={() => toggleSelectDoc(doc.document_id)}
                  className={`group relative flex items-start justify-between p-3 rounded-lg border text-xs cursor-pointer transition ${
                    isSelected
                      ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-100'
                      : 'bg-slate-800/40 border-slate-800 hover:border-slate-700 text-slate-300'
                  }`}
                >
                  <div className="flex items-start space-x-2.5 overflow-hidden pr-2">
                    <FileText className={`w-4 h-4 mt-0.5 shrink-0 ${isSelected ? 'text-emerald-400' : 'text-slate-400'}`} />
                    <div className="overflow-hidden">
                      <p className="font-medium truncate text-white">{doc.filename}</p>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        {doc.total_pages} {doc.total_pages === 1 ? 'page' : 'pages'} · {doc.total_chunks} chunks
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteDocument(doc.document_id, doc.filename);
                    }}
                    title="Delete document"
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-rose-500/20 hover:text-rose-400 rounded text-slate-500 transition shrink-0"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })
          )}
        </div>

        {/* Engine Status Footer */}
        <div className="p-3 border-t border-slate-800 bg-slate-900/80 text-[11px] space-y-1 text-slate-400">
          <div className="flex items-center justify-between">
            <span className="flex items-center space-x-1.5">
              <Cpu className="w-3.5 h-3.5 text-emerald-400" />
              <span>LLM: {health?.ollama_model || 'Connecting...'}</span>
            </span>
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-500"></span>
          </div>
          <div className="flex items-center space-x-1.5">
            <Database className="w-3.5 h-3.5 text-blue-400" />
            <span>Qdrant: {health?.indexed_documents_count ?? 0} docs indexed</span>
          </div>
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col h-full bg-slate-950">
        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex items-start space-x-3.5 ${
                msg.sender === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              {msg.sender === 'assistant' && (
                <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0 mt-0.5">
                  <Bot className="w-4 h-4" />
                </div>
              )}

              <div
                className={`max-w-2xl rounded-xl p-4 text-sm leading-relaxed ${
                  msg.sender === 'user'
                    ? 'bg-emerald-600 text-white rounded-tr-none'
                    : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-none shadow-sm'
                }`}
              >
                <div className="whitespace-pre-wrap">{msg.text}</div>

                {/* Insufficient Evidence Warning Banner */}
                {msg.insufficient_evidence && msg.sender === 'assistant' && msg.id !== 'welcome' && (
                  <div className="mt-3 flex items-center space-x-2 text-xs bg-amber-950/40 border border-amber-600/30 text-amber-200 px-3 py-2 rounded-lg">
                    <AlertCircle className="w-4 h-4 shrink-0 text-amber-400" />
                    <span>The system abstained from guessing because documents lacked sufficient evidence.</span>
                  </div>
                )}

                {/* Evidence Citations */}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-800/80">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center space-x-1">
                        <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                        <span>Verified Sources ({msg.sources.length})</span>
                      </span>
                      <button
                        onClick={() => toggleSourceExpand(msg.id)}
                        className="text-[11px] text-emerald-400 hover:text-emerald-300 flex items-center space-x-0.5"
                      >
                        <span>{expandedSources[msg.id] ? 'Hide Snippets' : 'View Passages'}</span>
                        {expandedSources[msg.id] ? (
                          <ChevronUp className="w-3 h-3" />
                        ) : (
                          <ChevronDown className="w-3 h-3" />
                        )}
                      </button>
                    </div>

                    {/* Source Pills */}
                    <div className="flex flex-wrap gap-1.5">
                      {msg.sources.map((s, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-slate-800 text-emerald-300 border border-slate-700"
                        >
                          {s.filename} · p.{s.page}
                        </span>
                      ))}
                    </div>

                    {/* Expanded Passages */}
                    {expandedSources[msg.id] && (
                      <div className="mt-2 space-y-2">
                        {msg.sources.map((s, idx) => (
                          <div
                            key={idx}
                            className="p-2.5 rounded bg-slate-950/70 border border-slate-800 text-xs text-slate-300"
                          >
                            <div className="font-semibold text-slate-400 text-[10px] uppercase mb-1">
                              Passage {idx + 1} — {s.filename} (Page {s.page})
                            </div>
                            <p className="italic text-slate-300">"{s.snippet}"</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <div className="mt-1 text-[10px] text-right text-slate-500 opacity-80">
                  {msg.timestamp}
                </div>
              </div>

              {msg.sender === 'user' && (
                <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 shrink-0 mt-0.5">
                  <User className="w-4 h-4" />
                </div>
              )}
            </div>
          ))}

          {/* Thinking / Answering Indicator */}
          {isAnswering && (
            <div className="flex items-start space-x-3.5">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0">
                <Bot className="w-4 h-4" />
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl rounded-tl-none p-4 text-xs text-slate-400 flex items-center space-x-2">
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-400" />
                <span>Running hybrid retrieval & generating cited answer...</span>
              </div>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        {/* Query Input Box */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/60">
          <form onSubmit={handleSendMessage} className="max-w-4xl mx-auto flex items-center space-x-2">
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder={
                documents.length === 0
                  ? 'Upload a document or ask general architecture questions...'
                  : selectedDocIds.length > 0
                  ? `Ask a question scoped to ${selectedDocIds.length} selected document(s)...`
                  : 'Ask any question across all uploaded documents...'
              }
              className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition"
            />
            <button
              type="submit"
              disabled={!inputQuery.trim() || isAnswering}
              className="bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-600 text-white px-5 py-3 rounded-lg font-medium text-sm transition flex items-center space-x-1.5 shadow-sm"
            >
              <span>Send</span>
              <Send className="w-4 h-4" />
            </button>
          </form>
          <div className="text-[11px] text-slate-500 text-center mt-2">
            DocuMind AI answers are strictly grounded in retrieved evidence. Passages are cited with source page numbers.
          </div>
        </div>
      </main>
    </div>
  );
}

