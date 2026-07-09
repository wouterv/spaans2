CREATE TABLE chapters (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE words (
    id INTEGER PRIMARY KEY,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    spanish TEXT NOT NULL,
    dutch TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE verbs (
    id INTEGER PRIMARY KEY,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    infinitive_es TEXT NOT NULL,
    translation_nl TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE conjugations (
    id INTEGER PRIMARY KEY,
    verb_id INTEGER NOT NULL REFERENCES verbs(id) ON DELETE CASCADE,
    tense TEXT NOT NULL DEFAULT 'presente',
    person TEXT NOT NULL CHECK (person IN ('yo','tu','el','nosotros','vosotros','ellos')),
    form TEXT NOT NULL,
    UNIQUE (verb_id, tense, person)
);

CREATE TABLE grammar_rules (
    id INTEGER PRIMARY KEY,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    explanation TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE grammar_examples (
    id INTEGER PRIMARY KEY,
    rule_id INTEGER NOT NULL REFERENCES grammar_rules(id) ON DELETE CASCADE,
    spanish TEXT NOT NULL,
    dutch TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE practice_stats (
    item_type TEXT NOT NULL,
    item_id INTEGER NOT NULL,
    direction TEXT NOT NULL,
    correct INTEGER NOT NULL DEFAULT 0,
    wrong INTEGER NOT NULL DEFAULT 0,
    last_practiced_at TEXT,
    PRIMARY KEY (item_type, item_id, direction)
);
