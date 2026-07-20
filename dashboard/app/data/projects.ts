export type ProjectId = "race_condition" | "memory_leak" | "redos_attack";
export type ProjectCatalogItem = Readonly<{ id: ProjectId; label: string }>;

// Labels only. The dashboard never supplies project findings, graph nodes, or metrics.
export const projectCatalog: readonly ProjectCatalogItem[] = [
  { id: "race_condition", label: "Race Condition" },
  { id: "memory_leak", label: "Memory Leak" },
  { id: "redos_attack", label: "ReDoS Attack" },
];
