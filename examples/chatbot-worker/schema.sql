-- Chat Worker D1 Schema (extends ai-tracker database)

CREATE TABLE IF NOT EXISTS chat_knowledge (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  brand TEXT NOT NULL,
  category TEXT NOT NULL,
  question TEXT,
  answer TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chat_knowledge_brand ON chat_knowledge(brand);

CREATE TABLE IF NOT EXISTS chat_conversations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  brand TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
  message TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chat_conv_session ON chat_conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_conv_brand ON chat_conversations(brand);
