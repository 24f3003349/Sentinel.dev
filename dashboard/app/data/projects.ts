export type ProjectId = "race_condition" | "memory_leak" | "redos_attack";
export type NodeTone = "module" | "risk" | "test" | "function" | "dependency";

export type GraphPoint = Readonly<{
  id: string;
  label: string;
  detail: string;
  tone: NodeTone;
  x: number;
  y: number;
}>;

export type ProjectView = Readonly<{
  id: ProjectId;
  label: string;
  shortLabel: string;
  probe: string;
  summary: string;
  nodes: readonly GraphPoint[];
  edges: readonly [string, string][];
}>;

export const projects: readonly ProjectView[] = [
  {
    id: "race_condition", label: "Race Condition", shortLabel: "RACE", probe: "Concurrent SQLite booking probe", summary: "Atomic inventory update protects the last available ticket.",
    nodes: [
      { id: "main", label: "main.py", detail: "module", tone: "module", x: 18, y: 24 },
      { id: "db", label: "init_db()", detail: "main.py · L12", tone: "function", x: 40, y: 16 },
      { id: "life", label: "lifespan()", detail: "main.py · L21", tone: "function", x: 33, y: 45 },
      { id: "book", label: "book_ticket()", detail: "main.py · L33 · attacked", tone: "risk", x: 64, y: 50 },
      { id: "health", label: "health()", detail: "main.py · L28", tone: "function", x: 75, y: 21 },
      { id: "test", label: "test_happy_path", detail: "test_main.py · L8", tone: "test", x: 20, y: 76 },
      { id: "fastapi", label: "FastAPI", detail: "dependency", tone: "dependency", x: 53, y: 78 },
      { id: "invariant", label: "stock = 1", detail: "booking invariant", tone: "risk", x: 82, y: 76 },
    ],
    edges: [["main", "db"], ["main", "life"], ["main", "book"], ["main", "health"], ["life", "db"], ["book", "fastapi"], ["book", "invariant"], ["test", "book"], ["fastapi", "health"]],
  },
  {
    id: "memory_leak", label: "Memory Leak", shortLabel: "MEMORY", probe: "Constrained-memory export probe", summary: "Streaming keeps large exports below the arena memory ceiling.",
    nodes: [
      { id: "main", label: "main.py", detail: "module", tone: "module", x: 15, y: 35 },
      { id: "app", label: "FastAPI", detail: "dependency", tone: "dependency", x: 35, y: 17 },
      { id: "health", label: "health()", detail: "main.py · L6", tone: "function", x: 43, y: 55 },
      { id: "export", label: "export_data()", detail: "main.py · L10 · attacked", tone: "risk", x: 65, y: 42 },
      { id: "buffer", label: "payload buffer", detail: "256 MiB arena policy", tone: "risk", x: 83, y: 70 },
      { id: "stream", label: "StreamingResponse", detail: "safe remediation", tone: "function", x: 68, y: 18 },
      { id: "test", label: "test_small_export", detail: "test_main.py · L9", tone: "test", x: 21, y: 78 },
      { id: "client", label: "HTTP client", detail: "arena probe", tone: "dependency", x: 47, y: 84 },
    ],
    edges: [["main", "app"], ["main", "health"], ["main", "export"], ["export", "buffer"], ["export", "stream"], ["test", "export"], ["client", "export"], ["app", "health"]],
  },
  {
    id: "redos_attack", label: "ReDoS Attack", shortLabel: "ReDoS", probe: "Catastrophic-regex timeout probe", summary: "An allow-list parser removes the exponential regex path.",
    nodes: [
      { id: "main", label: "main.py", detail: "module", tone: "module", x: 17, y: 18 },
      { id: "regex", label: "unsafe regex", detail: "main.py · L8", tone: "risk", x: 45, y: 26 },
      { id: "validate", label: "validate_input()", detail: "main.py · L13 · attacked", tone: "risk", x: 65, y: 52 },
      { id: "payload", label: "adversarial input", detail: "arena probe", tone: "dependency", x: 84, y: 30 },
      { id: "timeout", label: "3 second SLA", detail: "CPU timeout policy", tone: "risk", x: 86, y: 77 },
      { id: "safe", label: "SAFE_INPUT", detail: "linear allow-list", tone: "function", x: 38, y: 68 },
      { id: "test", label: "test_valid_input", detail: "test_main.py · L7", tone: "test", x: 17, y: 79 },
      { id: "api", label: "FastAPI", detail: "dependency", tone: "dependency", x: 57, y: 13 },
    ],
    edges: [["main", "regex"], ["main", "validate"], ["validate", "payload"], ["payload", "timeout"], ["regex", "validate"], ["safe", "validate"], ["test", "validate"], ["api", "validate"]],
  },
];

export const projectFor = (id: ProjectId) => projects.find((project) => project.id === id) ?? projects[0];
