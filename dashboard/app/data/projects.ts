export type ProjectId = "race_condition" | "memory_leak" | "redos_attack";
export type NodeTone = "module" | "risk" | "test" | "function" | "dependency";

export type GraphPoint = Readonly<{ id: string; label: string; detail: string; tone: NodeTone; x: number; y: number; major?: boolean }>;
export type ProjectView = Readonly<{ id: ProjectId; label: string; shortLabel: string; probe: string; summary: string; nodes: readonly GraphPoint[]; edges: readonly [string, string][] }>;

export const projects: readonly ProjectView[] = [
  {
    id: "race_condition", label: "Race Condition", shortLabel: "RACE", probe: "Concurrent SQLite booking probe", summary: "Atomic inventory update protects the last available ticket.",
    nodes: [
      { id: "main", label: "main.py", detail: "root module", tone: "module", x: 49, y: 47, major: true },
      { id: "db", label: "init_db()", detail: "main.py · L12", tone: "function", x: 40, y: 31 },
      { id: "life", label: "lifespan()", detail: "main.py · L21", tone: "function", x: 37, y: 55 },
      { id: "book", label: "book_ticket()", detail: "main.py · L33 · attacked", tone: "risk", x: 59, y: 48 },
      { id: "health", label: "health()", detail: "main.py · L28", tone: "function", x: 58, y: 31 },
      { id: "test", label: "test_happy_path", detail: "test_main.py · L8", tone: "test", x: 31, y: 69 },
      { id: "fastapi", label: "FastAPI", detail: "framework dependency", tone: "dependency", x: 50, y: 68 },
      { id: "invariant", label: "stock = 1", detail: "booking invariant", tone: "risk", x: 69, y: 64 },
      { id: "sql", label: "SQLite", detail: "persistence dependency", tone: "dependency", x: 33, y: 42 },
    ],
    edges: [["main", "db"], ["main", "life"], ["main", "book"], ["main", "health"], ["main", "fastapi"], ["db", "sql"], ["life", "db"], ["life", "fastapi"], ["book", "sql"], ["book", "fastapi"], ["book", "invariant"], ["test", "book"], ["test", "main"], ["fastapi", "health"]],
  },
  {
    id: "memory_leak", label: "Memory Leak", shortLabel: "MEMORY", probe: "Constrained-memory export probe", summary: "Streaming keeps large exports below the arena memory ceiling.",
    nodes: [
      { id: "main", label: "main.py", detail: "root module", tone: "module", x: 49, y: 47, major: true },
      { id: "app", label: "FastAPI", detail: "framework dependency", tone: "dependency", x: 41, y: 29 },
      { id: "health", label: "health()", detail: "main.py · L6", tone: "function", x: 35, y: 53 },
      { id: "export", label: "export_data()", detail: "main.py · L10 · attacked", tone: "risk", x: 60, y: 47 },
      { id: "buffer", label: "payload buffer", detail: "256 MiB arena policy", tone: "risk", x: 70, y: 62 },
      { id: "stream", label: "StreamingResponse", detail: "safe remediation", tone: "function", x: 61, y: 29 },
      { id: "test", label: "test_small_export", detail: "test_main.py · L9", tone: "test", x: 31, y: 70 },
      { id: "client", label: "HTTP client", detail: "arena probe", tone: "dependency", x: 49, y: 68 },
      { id: "limit", label: "256 MiB", detail: "container limit", tone: "risk", x: 71, y: 39 },
    ],
    edges: [["main", "app"], ["main", "health"], ["main", "export"], ["main", "stream"], ["main", "client"], ["export", "buffer"], ["export", "stream"], ["export", "limit"], ["test", "export"], ["test", "main"], ["client", "export"], ["app", "health"], ["stream", "buffer"]],
  },
  {
    id: "redos_attack", label: "ReDoS Attack", shortLabel: "ReDoS", probe: "Catastrophic-regex timeout probe", summary: "An allow-list parser removes the exponential regex path.",
    nodes: [
      { id: "main", label: "main.py", detail: "root module", tone: "module", x: 49, y: 47, major: true },
      { id: "regex", label: "unsafe regex", detail: "main.py · L8", tone: "risk", x: 40, y: 31 },
      { id: "validate", label: "validate_input()", detail: "main.py · L13 · attacked", tone: "risk", x: 60, y: 48 },
      { id: "payload", label: "adversarial input", detail: "arena probe", tone: "dependency", x: 69, y: 34 },
      { id: "timeout", label: "3 second SLA", detail: "CPU timeout policy", tone: "risk", x: 69, y: 65 },
      { id: "safe", label: "SAFE_INPUT", detail: "linear allow-list", tone: "function", x: 42, y: 65 },
      { id: "test", label: "test_valid_input", detail: "test_main.py · L7", tone: "test", x: 30, y: 69 },
      { id: "api", label: "FastAPI", detail: "framework dependency", tone: "dependency", x: 57, y: 28 },
      { id: "parser", label: "allow-list", detail: "remediation path", tone: "function", x: 53, y: 70 },
    ],
    edges: [["main", "regex"], ["main", "validate"], ["main", "api"], ["main", "safe"], ["regex", "validate"], ["validate", "payload"], ["validate", "timeout"], ["validate", "safe"], ["safe", "parser"], ["test", "validate"], ["test", "main"], ["api", "validate"], ["payload", "timeout"]],
  },
];

export const projectFor = (id: ProjectId) => projects.find((project) => project.id === id) ?? projects[0];
