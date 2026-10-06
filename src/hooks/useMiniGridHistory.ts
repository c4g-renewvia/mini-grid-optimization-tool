import { useState, useCallback } from 'react';

import {
  CostBreakdown,
  MiniGridNode,
  MiniGridEdge,
} from '@/types/minigrid';

export interface HistoryState {
  miniGridNodes: MiniGridNode[];
  miniGridEdges: MiniGridEdge[];
  costBreakdown: CostBreakdown;
  solverOriginalCost: number;
  mapView?: {
    center: { lat: number; lng: number };
    zoom: number;
    tilt: number;
    heading: number;
  };
  workspace?: {
    originalMiniGridNodes: MiniGridNode[];
    originalFileName: string | null;
    fileName: string | null;
    error: string | null;
    calcError: string | null;
    solverElapsedSeconds: number | null;
    solverElapsedDisplaySeconds: number;
  };
}

export function useMiniGridHistory(
  initialState: HistoryState,
  maxHistory = 20
) {
  const [history, setHistory] = useState<HistoryState[]>([initialState]);
  const [index, setIndex] = useState(0);

  const saveState = useCallback(
    (newState: HistoryState, currentState?: HistoryState) => {
      setHistory((prev) => {
        // 1. Truncate any redo-stack if we perform a new action while in the past
        const currentTimeline = prev.slice(0, index + 1);

        // Capture live state before destructive actions, including unsaved metadata.
        if (currentState) {
          currentTimeline[index] = JSON.parse(JSON.stringify(currentState));
        }

        // 2. Create a deep copy to prevent reference sharing bugs
        const stateToSave = JSON.parse(JSON.stringify(newState));
        const updatedHistory = [...currentTimeline, stateToSave];

        if (updatedHistory.length > maxHistory) {
          return updatedHistory.slice(1);
        }
        return updatedHistory;
      });

      setIndex((prev) => {
        const nextIdx = prev + 1;
        return Math.min(nextIdx, maxHistory - 1);
      });
    },
    [index, maxHistory]
  );

  const undo = useCallback(() => {
    if (index > 0) {
      const prevIndex = index - 1;
      setIndex(prevIndex);
      return history[prevIndex];
    }
    return null;
  }, [index, history]);

  const redo = useCallback(() => {
    if (index < history.length - 1) {
      const nextIndex = index + 1;
      setIndex(nextIndex);
      return history[nextIndex];
    }
    return null;
  }, [index, history]);

  return {
    saveState,
    undo,
    redo,
    canUndo: index > 0,
    canRedo: index < history.length - 1,
  };
}
