// types/minigrid.ts

// ====================== CORE DATA TYPES ======================

export interface MiniGridEdge {
  start: MiniGridNode;
  end: MiniGridNode;
  lengthMeters: number;
  voltage: 'low' | 'high';
}

export interface MiniGridNode {
  index: number;
  name: string;
  lat: number;
  lng: number;
  type: 'source' | 'terminal' | 'pole';
}

// ====================== SERVER / BACKEND CONTRACT TYPES ======================

export type NodeType = 'source' | 'terminal' | 'pole';

export interface LengthConstraintsBase {
  poleToPoleMaxLength: number;
  poleToTerminalMaxLength: number;
  poleToTerminalMinLength: number;
}

export interface LengthConstraints {
  low: LengthConstraintsBase;
  high: LengthConstraintsBase;
}

export interface Costs {
  poleCost: number;
  lowVoltageCostPerMeter: number;
  highVoltageCostPerMeter: number;
}

/**
 * Exact mirror of the Python SolverRequest Pydantic model.
 * Use this type for all API calls to /solve, /local_optimization, etc.
 */
export interface SolverRequest {
  solver: string;
  params: Record<string, any>;           // matches Python Dict[str, Any]
  nodes: MiniGridNode[];                 // reuse your existing type
  edges?: MiniGridEdge[];                // optional, defaults to []
  voltageLevel: 'low' | 'high';
  lengthConstraints: LengthConstraints;
  costs: Costs;
  usePoles?: boolean;                    // defaults to true in Python
  debug?: number;                        // defaults to 0
}

// Optional: If you want a stricter version that matches the defaults
export const defaultSolverRequest = (nodes: MiniGridNode[]): SolverRequest => ({
  solver: 'SimpleMSTSolver',
  params: {},
  nodes,
  edges: [],
  voltageLevel: 'low',
  lengthConstraints: {
    low: {
      poleToPoleMaxLength: 30,
      poleToTerminalMaxLength: 20,
      poleToTerminalMinLength: 5,
    },
    high: {
      poleToPoleMaxLength: 0,
      poleToTerminalMaxLength: 0,
      poleToTerminalMinLength: 0,
    },
  },
  costs: {
    poleCost: 1000,
    lowVoltageCostPerMeter: 20,
    highVoltageCostPerMeter: 0,
  },
  usePoles: true,
  debug: 0,
});

// ====================== COST TYPES ======================

export interface CostBreakdown {
  lowVoltageMeters: number;
  highVoltageMeters: number;
  totalMeters: number;
  lowWireCost: number;
  highWireCost: number;
  wireCost: number;
  poleCount: number;
  poleCost: number;
  pointCount: number;
  grandTotal: number;
  usedPoleCost?: number;
  usedLowCostPerMeter?: number;
  usedHighCostPerMeter?: number;
}

// ====================== SAVED RUNS ======================

export interface MiniGridRun {
  id: string;
  name?: string;
  createdAt: string;
  fileName?: string | null;
  miniGridNodes: MiniGridNode[];
  miniGridEdges: MiniGridEdge[];
  costBreakdown: CostBreakdown;
  poleCost: number;
  lowVoltageCost: number;
  highVoltageCost: number;
}

// ====================== SOLVER TYPES ======================

export interface SolverParam {
  name: string;
  type?: 'int' | 'str' | "bool" | "float";
  default: number | string | boolean;
  min?: number;
  max?: number;
  options?: string[];
  description?: string;
}

export interface Solvers {
  name: string;
  params: SolverParam[];
}

// ====================== HELPER TYPES ======================

export interface ManualPoint {
  name: string;
  lat: string;
  lng: string;
  type: 'source' | 'terminal' | 'pole';
}

export interface PendingPoint {
  lat: number;
  lng: number;
}

export interface NewPointDetails {
  name: string;
  type: 'source' | 'terminal' | 'pole';
}

// ====================== STATE SNAPSHOT FOR HISTORY ======================

export interface MiniGridState {
  miniGridNodes: MiniGridNode[];
  miniGridEdges: MiniGridEdge[];
  costBreakdown: CostBreakdown;
}
