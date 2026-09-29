CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    title TEXT,
    url TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('course','project','assignment','track')) DEFAULT 'course',
    language TEXT,
    status TEXT NOT NULL CHECK(status IN ('not_started','in_progress','completed','blocked')) DEFAULT 'not_started',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id),
    chapter_number INTEGER NOT NULL,
    slug TEXT,
    title TEXT,
    status TEXT NOT NULL CHECK(status IN ('not_started','in_progress','completed')) DEFAULT 'not_started',
    UNIQUE(course_id, chapter_number)
);

CREATE TABLE IF NOT EXISTS exercises (
    id INTEGER PRIMARY KEY,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id),
    exercise_number INTEGER NOT NULL,
    dc_exercise_id TEXT,
    url TEXT,
    type TEXT NOT NULL,
    language TEXT,
    instructions TEXT,
    instructions_hash TEXT NOT NULL,
    starter_code TEXT,
    status TEXT NOT NULL CHECK(status IN ('pending','solved','failed','skipped')) DEFAULT 'pending',
    solved_at TEXT,
    UNIQUE(chapter_id, exercise_number)
);
CREATE INDEX IF NOT EXISTS idx_exercises_hash ON exercises(instructions_hash);

CREATE TABLE IF NOT EXISTS solutions (
    id INTEGER PRIMARY KEY,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id),
    instructions_hash TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    source TEXT NOT NULL CHECK(source IN ('deterministic','llm','cache','manual')),
    is_current INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_solutions_exercise ON solutions(exercise_id);
CREATE INDEX IF NOT EXISTS idx_solutions_instructions_hash ON solutions(instructions_hash);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id),
    attempt_number INTEGER NOT NULL,
    solution_id INTEGER REFERENCES solutions(id),
    submitted_content TEXT,
    result TEXT NOT NULL CHECK(result IN ('success','error','wrong_answer','timeout','blocked')),
    error_message TEXT,
    duration_ms INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts_exercise ON attempts(exercise_id);

CREATE TABLE IF NOT EXISTS state (
    course_id INTEGER PRIMARY KEY REFERENCES courses(id),
    current_chapter_id INTEGER REFERENCES chapters(id),
    current_exercise_id INTEGER REFERENCES exercises(id),
    last_url TEXT,
    notes TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS course_memory (
    id INTEGER PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id),
    chapter_id INTEGER REFERENCES chapters(id),
    kind TEXT NOT NULL CHECK(kind IN ('concept','pattern','gotcha')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS token_usage (
    id INTEGER PRIMARY KEY,
    exercise_id INTEGER REFERENCES exercises(id),
    course_id INTEGER REFERENCES courses(id),
    provider TEXT NOT NULL,
    model TEXT,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL,
    purpose TEXT NOT NULL CHECK(purpose IN ('solve','repair','note_generation','classification')),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_token_usage_course ON token_usage(course_id);
