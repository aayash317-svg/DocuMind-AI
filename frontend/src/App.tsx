import React, { useState, useEffect, useRef } from 'react';
import {
  Upload,
  FileText,
  Trash2,
  Send,
  Bot,
  User as UserIcon,
  CheckCircle2,
  AlertCircle,
  Database,
  Cpu,
  BookOpen,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  MessageSquare,
  Plus,
  Edit2,
  Check,
  X,
  LogIn,
  LogOut,
  Info,
  ShieldAlert,
  Key
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

interface DocumentLimitations {
  format_name: string;
  limitations: string[];
  detected_risks: string[];
  querying_advice: string[];
}

interface DocumentItem {
  document_id: string;
  filename: string;
  file_type?: string;
  total_chunks: number;
  total_pages: number;
  limitations?: DocumentLimitations;
}

interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message?: string;
}

interface UserProfile {
  id: string;
  email: string;
  full_name?: string;
}

interface HealthStatus {
  status: string;
  ollama_model: string;
  embedding_model: string;
  indexed_documents_count: number;
}

export default function App() {
  // Auth state
  const [user, setUser] = useState<UserProfile | null>(() => {
    const saved = localStorage.getItem('documind_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [authToken, setAuthToken] = useState<string | null>(() => {
    return localStorage.getItem('documind_token') || null;
  });
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authMode, setAuthMode] = useState<'login' | 'signup' | 'reset'>('login');
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authFullName, setAuthFullName] = useState('');
  const [authError, setAuthError] = useState('');
  const [authSuccess, setAuthSuccess] = useState('');

  // Conversations & History
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [editingConvId, setEditingConvId] = useState<string | null>(null);
  const [editTitleInput, setEditTitleInput] = useState('');

  // Documents & Retrieval
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [selectedDocForModal, setSelectedDocForModal] = useState<DocumentItem | null>(null);
  const [showGlobalLimitationsModal, setShowGlobalLimitationsModal] = useState(false);

  // Chat messages & Input
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

  // Helper for authenticated requests
  const authHeaders = (): Record<string, string> => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    }
    return headers;
  };

  useEffect(() => {
    fetchHealth();
    fetchDocuments();
    if (authToken) {
      fetchConversations();
    }
  }, [authToken]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isAnswering]);

  const fetchHealth = async () => {
    try {
      const res = await fetch('/health');
      if (res.ok) setHealth(await res.json());
    } catch {
      setHealth(null);
    }
  };

  const fetchDocuments = async () => {
    try {
      const res = await fetch('/documents', { headers: authHeaders() });
      if (res.ok) {
        const data: DocumentItem[] = await res.json();
        setDocuments(data);
      }
    } catch (err) {
      console.error('Failed to load documents:', err);
    }
  };

  const fetchConversations = async () => {
    if (!authToken) return;
    try {
      const res = await fetch('/conversations', { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setConversations(data);
      }
    } catch (err) {
      console.error('Failed to load conversations:', err);
    }
  };

  // Auth Handlers
  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');
    setAuthSuccess('');

    try {
      if (authMode === 'signup') {
        const res = await fetch('/auth/signup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: authEmail, password: authPassword, full_name: authFullName }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Signup failed');

        setAuthToken(data.token);
        setUser(data.user);
        localStorage.setItem('documind_token', data.token);
        localStorage.setItem('documind_user', JSON.stringify(data.user));
        setShowAuthModal(false);
      } else if (authMode === 'login') {
        const res = await fetch('/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: authEmail, password: authPassword }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Login failed');

        setAuthToken(data.token);
        setUser(data.user);
        localStorage.setItem('documind_token', data.token);
        localStorage.setItem('documind_user', JSON.stringify(data.user));
        setShowAuthModal(false);
      } else if (authMode === 'reset') {
        const res = await fetch('/auth/reset-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: authEmail, new_password: authPassword }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Password reset failed');

        setAuthSuccess(data.message || 'Password reset successfully! Please sign in.');
        setAuthMode('login');
      }
    } catch (err: any) {
      setAuthError(err.message);
    }
  };

  const handleLogout = async () => {
    try {
      await fetch('/auth/logout', { method: 'POST', headers: authHeaders() });
    } catch {
      // ignore
    }
    setAuthToken(null);
    setUser(null);
    localStorage.removeItem('documind_token');
    localStorage.removeItem('documind_user');
    setConversations([]);
    handleStartNewChat();
  };

  // Conversation Management
  const handleStartNewChat = () => {
    setActiveConvId(null);
    setMessages([
      {
        id: 'welcome',
        sender: 'assistant',
        text: 'Started a new session. Upload files or ask questions grounded in your document library.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  };

  const handleSelectConversation = async (convId: string) => {
    try {
      const res = await fetch(`/conversations/${convId}`, { headers: authHeaders() });
      if (!res.ok) return;

      const data = await res.json();
      setActiveConvId(data.id);

      if (data.messages && data.messages.length > 0) {
        setMessages(
          data.messages.map((m: any) => ({
            id: m.id,
            sender: m.sender,
            text: m.text,
            insufficient_evidence: m.insufficient_evidence,
            sources: m.sources || [],
            timestamp: new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          }))
        );
      } else {
        setMessages([
          {
            id: 'empty',
            sender: 'assistant',
            text: `Reopened "${data.title}". Continue asking questions.`,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      }
    } catch (err) {
      console.error('Failed to load conversation details:', err);
    }
  };

  const handleRenameConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!editTitleInput.trim()) return;

    try {
      const res = await fetch(`/conversations/${convId}`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({ title: editTitleInput.trim() }),
      });
      if (res.ok) {
        setEditingConvId(null);
        fetchConversations();
      }
    } catch (err) {
      alert(`Failed to rename: ${err}`);
    }
  };

  const handleDeleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this chat history?')) return;

    try {
      const res = await fetch(`/conversations/${convId}`, {
        method: 'DELETE',
        headers: authHeaders(),
      });
      if (res.ok) {
        if (activeConvId === convId) handleStartNewChat();
        fetchConversations();
      }
    } catch (err) {
      alert(`Failed to delete chat: ${err}`);
    }
  };

  // Upload & File handling
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const headers: Record<string, string> = {};
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

      const res = await fetch('/documents/upload', {
        method: 'POST',
        headers,
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        alert(`Upload error: ${err.detail || 'Failed to upload'}`);
      } else {
        const uploadedMeta = await res.json();
        await fetchDocuments();
        await fetchHealth();

        // Automatically open the limitations dialog for the uploaded document
        setSelectedDocForModal(uploadedMeta);
      }
    } catch (err) {
      alert(`Network error uploading file: ${err}`);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDeleteDocument = async (docId: string, filename: string) => {
    if (!confirm(`Remove "${filename}" and delete its vector chunks?`)) return;

    try {
      const res = await fetch(`/documents/${docId}`, {
        method: 'DELETE',
        headers: authHeaders(),
      });
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

  // Chat message send
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
        headers: authHeaders(),
        body: JSON.stringify({
          question: query,
          conversation_id: activeConvId,
          document_ids: selectedDocIds.length > 0 ? selectedDocIds : null,
          top_k: 5,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Chat query failed');
      }

      const data = await res.json();
      if (!activeConvId && data.conversation_id) {
        setActiveConvId(data.conversation_id);
      }

      const botMsg: ChatMessage = {
        id: `a_${Date.now()}`,
        sender: 'assistant',
        text: data.answer,
        insufficient_evidence: data.insufficient_evidence,
        sources: data.sources || [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, botMsg]);
      fetchConversations();
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
      {/* Sidebar: Navigation, Recent Chats & Document Library */}
      <aside className="w-84 bg-slate-900 border-r border-slate-800 flex flex-col h-full shrink-0">
        {/* Brand & New Chat Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="bg-emerald-500/10 p-2 rounded-lg text-emerald-400 border border-emerald-500/20">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h1 className="font-bold text-base tracking-tight text-white flex items-center space-x-1.5">
                <span>DocuMind AI</span>
                <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                  v2.0
                </span>
              </h1>
              <p className="text-xs text-slate-400">Grounded Knowledge Assistant</p>
            </div>
          </div>
          <button
            onClick={() => {
              fetchHealth();
              fetchDocuments();
              fetchConversations();
            }}
            title="Refresh"
            className="p-1.5 hover:bg-slate-800 rounded-md text-slate-400 hover:text-slate-200 transition"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* Start New Chat Action */}
        <div className="px-4 pt-3 pb-2">
          <button
            onClick={handleStartNewChat}
            className="w-full flex items-center justify-center space-x-2 bg-slate-800/80 hover:bg-slate-800 text-slate-200 hover:text-white border border-slate-700/80 rounded-lg py-2 px-3 text-xs font-medium transition shadow-sm"
          >
            <Plus className="w-4 h-4 text-emerald-400" />
            <span>New Chat Thread</span>
          </button>
        </div>

        {/* Sidebar Scrollable Sections */}
        <div className="flex-1 overflow-y-auto px-4 py-2 space-y-5">
          {/* Recent Chats Section */}
          <div>
            <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400 pb-1.5 border-b border-slate-800/60 mb-2">
              <span className="flex items-center space-x-1.5">
                <MessageSquare className="w-3.5 h-3.5 text-blue-400" />
                <span>Recent Chats ({conversations.length})</span>
              </span>
            </div>

            {conversations.length === 0 ? (
              <p className="text-[11px] text-slate-500 italic py-1">No saved conversations yet.</p>
            ) : (
              <div className="space-y-1">
                {conversations.map((c) => {
                  const isActive = activeConvId === c.id;
                  const isEditing = editingConvId === c.id;

                  return (
                    <div
                      key={c.id}
                      onClick={() => handleSelectConversation(c.id)}
                      className={`group flex items-center justify-between px-2.5 py-2 rounded-lg text-xs cursor-pointer transition ${
                        isActive
                          ? 'bg-blue-950/40 border border-blue-500/40 text-blue-100'
                          : 'hover:bg-slate-800/60 text-slate-300'
                      }`}
                    >
                      {isEditing ? (
                        <div className="flex items-center space-x-1.5 flex-1 mr-1" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="text"
                            value={editTitleInput}
                            onChange={(e) => setEditTitleInput(e.target.value)}
                            className="bg-slate-950 border border-blue-500 text-xs rounded px-1.5 py-0.5 text-white w-full focus:outline-none"
                            autoFocus
                          />
                          <button
                            onClick={(e) => handleRenameConversation(c.id, e)}
                            className="p-1 text-emerald-400 hover:bg-slate-800 rounded"
                          >
                            <Check className="w-3 h-3" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingConvId(null);
                            }}
                            className="p-1 text-slate-400 hover:bg-slate-800 rounded"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center space-x-2 truncate flex-1 pr-1">
                          <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-blue-400' : 'text-slate-500'}`} />
                          <span className="truncate font-medium">{c.title}</span>
                        </div>
                      )}

                      {!isEditing && (
                        <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition shrink-0">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingConvId(c.id);
                              setEditTitleInput(c.title);
                            }}
                            title="Rename chat"
                            className="p-1 hover:bg-slate-700/60 rounded text-slate-400 hover:text-white"
                          >
                            <Edit2 className="w-3 h-3" />
                          </button>
                          <button
                            onClick={(e) => handleDeleteConversation(c.id, e)}
                            title="Delete chat"
                            className="p-1 hover:bg-rose-500/20 rounded text-slate-400 hover:text-rose-400"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Document Knowledge Base Section */}
          <div>
            <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400 pb-1.5 border-b border-slate-800/60 mb-2">
              <span className="flex items-center space-x-1.5">
                <FileText className="w-3.5 h-3.5 text-emerald-400" />
                <span>Documents ({documents.length})</span>
              </span>
              <button
                onClick={() => setShowGlobalLimitationsModal(true)}
                title="View document format limitations"
                className="text-[10px] text-amber-400 hover:text-amber-300 flex items-center space-x-0.5 lowercase font-normal"
              >
                <AlertCircle className="w-3 h-3" />
                <span>limitations</span>
              </button>
            </div>

            {/* Upload Button */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".pdf,.docx,.txt,.md"
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="w-full flex items-center justify-center space-x-2 bg-emerald-600/90 hover:bg-emerald-500 disabled:bg-slate-800 text-white text-xs font-medium py-2 px-3 rounded-lg transition border border-emerald-500/30 mb-2"
            >
              {isUploading ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Extracting & Indexing...</span>
                </>
              ) : (
                <>
                  <Upload className="w-3.5 h-3.5" />
                  <span>Upload Document</span>
                </>
              )}
            </button>

            {/* Document List */}
            {documents.length === 0 ? (
              <div className="p-4 text-center border border-dashed border-slate-800 rounded-lg text-slate-500 text-xs">
                No documents uploaded.<br />Add PDF, DOCX, TXT, or MD.
              </div>
            ) : (
              <div className="space-y-1.5">
                {documents.map((doc) => {
                  const isSelected = selectedDocIds.includes(doc.document_id);
                  const hasRisks = doc.limitations?.detected_risks && doc.limitations.detected_risks.length > 0;

                  return (
                    <div
                      key={doc.document_id}
                      onClick={() => toggleSelectDoc(doc.document_id)}
                      className={`group relative flex items-start justify-between p-2.5 rounded-lg border text-xs cursor-pointer transition ${
                        isSelected
                          ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-100'
                          : 'bg-slate-800/40 border-slate-800 hover:border-slate-700 text-slate-300'
                      }`}
                    >
                      <div className="flex items-start space-x-2 overflow-hidden pr-1.5">
                        <FileText className={`w-4 h-4 mt-0.5 shrink-0 ${isSelected ? 'text-emerald-400' : 'text-slate-400'}`} />
                        <div className="overflow-hidden">
                          <p className="font-medium truncate text-white leading-snug">{doc.filename}</p>
                          <p className="text-[11px] text-slate-400 mt-0.5">
                            {doc.total_pages} {doc.total_pages === 1 ? 'page' : 'pages'} · {doc.total_chunks} chunks
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center space-x-1 shrink-0">
                        {/* Info / Limitations Icon */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedDocForModal(doc);
                          }}
                          title="View Extraction Insights & Limitations"
                          className={`p-1 rounded transition ${hasRisks ? 'text-amber-400 hover:bg-amber-500/20' : 'text-slate-400 hover:bg-slate-700/60'}`}
                        >
                          {hasRisks ? <AlertCircle className="w-3.5 h-3.5" /> : <Info className="w-3.5 h-3.5" />}
                        </button>

                        {/* Delete Button */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteDocument(doc.document_id, doc.filename);
                          }}
                          title="Delete document"
                          className="opacity-0 group-hover:opacity-100 p-1 hover:bg-rose-500/20 hover:text-rose-400 rounded text-slate-500 transition"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* User Account & System Status Footer */}
        <div className="p-3 border-t border-slate-800 bg-slate-900/90 text-xs space-y-2">
          {user ? (
            <div className="flex items-center justify-between bg-slate-800/60 p-2 rounded-lg border border-slate-700/60">
              <div className="overflow-hidden pr-2">
                <p className="text-white font-medium truncate text-xs">{user.full_name || 'User'}</p>
                <p className="text-slate-400 text-[11px] truncate">{user.email}</p>
              </div>
              <button
                onClick={handleLogout}
                title="Log out"
                className="p-1.5 hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 rounded transition shrink-0"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <button
              onClick={() => {
                setAuthMode('login');
                setShowAuthModal(true);
              }}
              className="w-full flex items-center justify-center space-x-2 bg-blue-600/80 hover:bg-blue-500 text-white py-1.5 px-3 rounded-lg font-medium transition"
            >
              <LogIn className="w-3.5 h-3.5" />
              <span>Sign In / Create Account</span>
            </button>
          )}

          <div className="text-[11px] space-y-0.5 text-slate-500">
            <div className="flex items-center justify-between">
              <span className="flex items-center space-x-1">
                <Cpu className="w-3 h-3 text-emerald-400" />
                <span>LLM: {health?.ollama_model || 'Connecting...'}</span>
              </span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            </div>
            <div className="flex items-center space-x-1">
              <Database className="w-3 h-3 text-blue-400" />
              <span>Qdrant: {health?.indexed_documents_count ?? 0} docs indexed</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Chat Interface */}
      <main className="flex-1 flex flex-col h-full bg-slate-950">
        {/* Top Navbar */}
        <header className="h-14 border-b border-slate-800 px-6 flex items-center justify-between bg-slate-900/40 backdrop-blur">
          <div className="flex items-center space-x-3">
            <span className="font-medium text-sm text-white">
              {activeConvId
                ? conversations.find((c) => c.id === activeConvId)?.title || 'Active Chat'
                : 'Default Chat Workspace'}
            </span>
            {selectedDocIds.length > 0 && (
              <span className="text-xs bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                Scoped to {selectedDocIds.length} document{selectedDocIds.length > 1 ? 's' : ''}
              </span>
            )}
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowGlobalLimitationsModal(true)}
              className="flex items-center space-x-1.5 text-xs text-amber-300 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 px-3 py-1.5 rounded-lg transition"
            >
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>Document Extraction Limitations</span>
            </button>
          </div>
        </header>

        {/* Message Thread */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex items-start space-x-3.5 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
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
                        <span>Verified Citations ({msg.sources.length})</span>
                      </span>
                      <button
                        onClick={() => toggleSourceExpand(msg.id)}
                        className="text-[11px] text-emerald-400 hover:text-emerald-300 flex items-center space-x-0.5"
                      >
                        <span>{expandedSources[msg.id] ? 'Hide Passages' : 'View Passages'}</span>
                        {expandedSources[msg.id] ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
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

                <div className="mt-1 text-[10px] text-right text-slate-500 opacity-80">{msg.timestamp}</div>
              </div>

              {msg.sender === 'user' && (
                <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 shrink-0 mt-0.5">
                  <UserIcon className="w-4 h-4" />
                </div>
              )}
            </div>
          ))}

          {isAnswering && (
            <div className="flex items-start space-x-3.5">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0">
                <Bot className="w-4 h-4" />
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl rounded-tl-none p-4 text-xs text-slate-400 flex items-center space-x-2">
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-400" />
                <span>Retrieving evidence & generating grounded answer...</span>
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
                  ? 'Upload documents or ask questions...'
                  : selectedDocIds.length > 0
                  ? `Ask a question scoped to ${selectedDocIds.length} selected document(s)...`
                  : 'Ask any question across all indexed documents (e.g., "What does page 4 discuss?")...'
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
            Answers are strictly grounded in retrieved evidence. Passages and page numbers are verified before display.
          </div>
        </div>
      </main>

      {/* MODAL 1: Authentication (Login / Signup / Reset) */}
      {showAuthModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 shadow-2xl relative">
            <button
              onClick={() => setShowAuthModal(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center space-x-2 mb-4">
              <div className="bg-blue-500/10 p-2 rounded-lg text-blue-400 border border-blue-500/20">
                <Key className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-base text-white">
                  {authMode === 'login' ? 'Sign In to DocuMind AI' : authMode === 'signup' ? 'Create an Account' : 'Reset Password'}
                </h3>
                <p className="text-xs text-slate-400">Keep your documents and chat history private.</p>
              </div>
            </div>

            {/* Mode Switcher */}
            <div className="flex border-b border-slate-800 mb-4 text-xs font-medium">
              <button
                onClick={() => {
                  setAuthMode('login');
                  setAuthError('');
                }}
                className={`flex-1 py-2 border-b-2 text-center transition ${authMode === 'login' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
              >
                Sign In
              </button>
              <button
                onClick={() => {
                  setAuthMode('signup');
                  setAuthError('');
                }}
                className={`flex-1 py-2 border-b-2 text-center transition ${authMode === 'signup' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
              >
                Sign Up
              </button>
              <button
                onClick={() => {
                  setAuthMode('reset');
                  setAuthError('');
                }}
                className={`flex-1 py-2 border-b-2 text-center transition ${authMode === 'reset' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
              >
                Reset
              </button>
            </div>

            {authError && (
              <div className="mb-4 p-3 rounded-lg bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs">
                {authError}
              </div>
            )}
            {authSuccess && (
              <div className="mb-4 p-3 rounded-lg bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 text-xs">
                {authSuccess}
              </div>
            )}

            <form onSubmit={handleAuthSubmit} className="space-y-3">
              {authMode === 'signup' && (
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Full Name</label>
                  <input
                    type="text"
                    required
                    value={authFullName}
                    onChange={(e) => setAuthFullName(e.target.value)}
                    placeholder="Jane Doe"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Email Address</label>
                <input
                  type="email"
                  required
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  {authMode === 'reset' ? 'New Password' : 'Password'}
                </label>
                <input
                  type="password"
                  required
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
                />
              </div>

              <button
                type="submit"
                className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-2 px-4 rounded-lg text-xs transition mt-2"
              >
                {authMode === 'login' ? 'Sign In' : authMode === 'signup' ? 'Create Account' : 'Update Password'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Document Extraction Insights & Limitations for Selected Document */}
      {selectedDocForModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-xl p-6 shadow-2xl relative max-h-[85vh] overflow-y-auto">
            <button
              onClick={() => setSelectedDocForModal(null)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center space-x-2.5 mb-4">
              <div className="bg-amber-500/10 p-2 rounded-lg text-amber-400 border border-amber-500/20">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-base text-white truncate max-w-md">
                  Extraction Insights & Limitations
                </h3>
                <p className="text-xs text-slate-400 font-mono">{selectedDocForModal.filename}</p>
              </div>
            </div>

            {/* Detected Extraction Risks */}
            <div className="space-y-4 text-xs">
              {selectedDocForModal.limitations?.detected_risks && selectedDocForModal.limitations.detected_risks.length > 0 ? (
                <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-500/30 text-amber-200 space-y-1.5">
                  <p className="font-semibold flex items-center space-x-1.5 text-amber-400">
                    <AlertCircle className="w-4 h-4" />
                    <span>Potential Extraction Warnings Detected:</span>
                  </p>
                  <ul className="list-disc pl-5 space-y-1 text-slate-300">
                    {selectedDocForModal.limitations.detected_risks.map((risk, idx) => (
                      <li key={idx}>{risk}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span>Text extraction succeeded with healthy character density and clean page flow.</span>
                </div>
              )}

              {/* Format-Specific Limitations */}
              <div>
                <h4 className="font-semibold text-slate-200 mb-1.5 uppercase text-[11px] tracking-wider">
                  Format Caveats ({selectedDocForModal.limitations?.format_name || selectedDocForModal.file_type?.toUpperCase()}):
                </h4>
                <ul className="list-disc pl-5 space-y-1 text-slate-400">
                  {selectedDocForModal.limitations?.limitations?.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>

              {/* Querying Advice */}
              <div>
                <h4 className="font-semibold text-slate-200 mb-1.5 uppercase text-[11px] tracking-wider">
                  Best Practices for Asking Questions:
                </h4>
                <ul className="list-disc pl-5 space-y-1 text-slate-400">
                  {selectedDocForModal.limitations?.querying_advice?.map((adv, idx) => (
                    <li key={idx}>{adv}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setSelectedDocForModal(null)}
                className="bg-slate-800 hover:bg-slate-700 text-white font-medium py-2 px-4 rounded-lg text-xs transition"
              >
                Close & Continue
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: Global Document Limitations & Disadvantages Guide */}
      {showGlobalLimitationsModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl p-6 shadow-2xl relative max-h-[85vh] overflow-y-auto">
            <button
              onClick={() => setShowGlobalLimitationsModal(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center space-x-2.5 mb-4">
              <div className="bg-amber-500/10 p-2 rounded-lg text-amber-400 border border-amber-500/20">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-base text-white">Disadvantages & Limitations of DOC/PDF Files</h3>
                <p className="text-xs text-slate-400">
                  How document structure affects text extraction, retrieval, and answering.
                </p>
              </div>
            </div>

            <div className="space-y-4 text-xs text-slate-300">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                  <p className="font-semibold text-white flex items-center space-x-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                    <span>1. Scanned PDFs</span>
                  </p>
                  <p className="text-slate-400 leading-relaxed">
                    Image-based PDFs require optical character recognition (OCR). Poor resolution, handwritten notes, or skewed pages cause extraction errors.
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                  <p className="font-semibold text-white flex items-center space-x-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                    <span>2. Complex Tables</span>
                  </p>
                  <p className="text-slate-400 leading-relaxed">
                    Nested rows, column spans, and financial matrices lose their 2D spatial alignment when parsed into plain sequential text.
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                  <p className="font-semibold text-white flex items-center space-x-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                    <span>3. Images & Diagrams</span>
                  </p>
                  <p className="text-slate-400 leading-relaxed">
                    Charts, architectural diagrams, and schematics cannot be interpreted unless explicit textual descriptions exist in the surrounding paragraphs.
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                  <p className="font-semibold text-white flex items-center space-x-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                    <span>4. Word DOC/DOCX Artifacts</span>
                  </p>
                  <p className="text-slate-400 leading-relaxed">
                    Floating textboxes, headers, footers, and sidebars may be extracted out of logical reading order.
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                  <p className="font-semibold text-white flex items-center space-x-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                    <span>5. Large Documents</span>
                  </p>
                  <p className="text-slate-400 leading-relaxed">
                    Dense documents with hundreds of pages require higher top-k search depth and may exhibit longer retrieval latency.
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                  <p className="font-semibold text-white flex items-center space-x-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                    <span>6. Corrupted or Encrypted Files</span>
                  </p>
                  <p className="text-slate-400 leading-relaxed">
                    Password-protected, encrypted, or malformed files will be rejected at ingestion to protect database integrity.
                  </p>
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-emerald-950/30 border border-emerald-500/30 text-emerald-200">
                <p className="font-semibold text-emerald-300 flex items-center space-x-1.5 mb-1">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>7. Missing Information Guardrails</span>
                </p>
                <p className="text-slate-300 leading-relaxed">
                  DocuMind AI strictly enforces evidence grounding: when a document does not contain the answer, the model explicitly abstains rather than hallucinating unsupported claims.
                </p>
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setShowGlobalLimitationsModal(false)}
                className="bg-slate-800 hover:bg-slate-700 text-white font-medium py-2 px-4 rounded-lg text-xs transition"
              >
                Close Guide
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
