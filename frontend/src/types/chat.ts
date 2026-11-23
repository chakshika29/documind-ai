export interface Citation {
  document_id: string;
  document_name: string;
  page: number;
  chunk_id: number;
  excerpt: string;
}

export interface ChatReply {
  answer: string;
  conversation_id: string;
  message_id: string;
  citations: Citation[];
  elapsed_ms: number;
  model: string;
  insufficient_evidence: boolean;
}

export interface Conversation {
  id: string;
  title: string;
  updated_at: string | null;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  document_ids: string[];
  citations: Citation[];
  model: string | null;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}
