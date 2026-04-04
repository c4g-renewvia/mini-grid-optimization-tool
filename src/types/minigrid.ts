// types/minigrid.ts

// ====================== CORE DATA TYPES ======================

export interface MarkerPoint {
  name: string;
  type: 'source' | 'terminal' | 'pole';
  lat: number;
  lng: number;
}

export interface MiniGridEdge {
  start: { lat: number; lng: number };
  end: { lat: number; lng: number };
  lengthMeters: number;
  voltage: 'low' | 'high';
}

export interface MiniGridNode {
  index: number;
  lat: number;
  lng: number;
  name: string;
  type: 'source' | 'terminal' | 'pole';
}

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
  dataPoints: MarkerPoint[];
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
  type?: 'integer' | 'float' | 'number';
  default: number;
  min?: number;
  max?: number;
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
  dataPoints: MarkerPoint[];
  miniGridNodes: MiniGridNode[];
  miniGridEdges: MiniGridEdge[];
  costBreakdown: CostBreakdown;
}
