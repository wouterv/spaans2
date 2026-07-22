CREATE TABLE exercises (
    id INTEGER PRIMARY KEY,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('invullen','vertalen','meerkeuze','herschrijven')),
    instruction TEXT NOT NULL,
    prompt TEXT NOT NULL,
    answer TEXT NOT NULL,
    options TEXT,
    explanation TEXT NOT NULL DEFAULT '',
    disabled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
