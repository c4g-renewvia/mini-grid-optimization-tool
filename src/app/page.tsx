'use client';

import React, {
  ChangeEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import Script from 'next/script';
import Papa from 'papaparse';
import { useSession } from 'next-auth/react';

import { useMiniGridHistory } from '@/hooks/useMiniGridHistory';

import AddPointDialog from '@/components/minigrid-tool/define-markers/AddPointDialog';
import DefineMarkersSection from '@/components/minigrid-tool/define-markers/DefineMarkersSection';

import CostsSection from '@/components/minigrid-tool/costs-solver/CostsSection';
import SolverSection from '@/components/minigrid-tool/costs-solver/SolverSection';

import ExportAndSummarySection from '@/components/minigrid-tool/export-summary/ExportAndSummarySection';

import SavedGridsSection from '@/components/minigrid-tool/SavedGridsSection';

import MapControls from '@/components/minigrid-tool/MapControls';

import type {
  CostBreakdown,
  MiniGridEdge,
  MiniGridNode,
  MiniGridRun,
  Solvers,
} from '@/types/minigrid';
import { SidebarUserMenu } from '@/components/minigrid-tool/SidebarUserMenu';

const GOOGLE_MAPS_API_KEY =
  process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || 'YOUR_GOOGLE_MAPS_API_KEY';

function toLiteral(
  pos: google.maps.marker.AdvancedMarkerElement['position']
): google.maps.LatLngLiteral | null {
  if (!pos) return null;
  if (typeof pos.lat === 'function' && typeof pos.lng === 'function') {
    return { lat: pos.lat(), lng: pos.lng() };
  }
  return { lat: pos.lat as number, lng: pos.lng as number };
}

const haversineDistance = (
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
) => {
  const R = 6371e3;
  const deg2rad = (deg: number) => deg * (Math.PI / 180);
  const dLat = deg2rad(lat2 - lat1);
  const dLon = deg2rad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(deg2rad(lat1)) *
      Math.cos(deg2rad(lat2)) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
};

const formatMeters = (m: number) =>
  m.toLocaleString(undefined, { maximumFractionDigits: 0 });

const highVoltageColor = '#8B5CF6';
const lowVoltageColor = '#3B82F6';

// ==================== MAIN COMPONENT ====================
export default function MiniGridToolPage() {
  const mapRef = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<google.maps.Map | null>(null);
  const polylinesRef = useRef<google.maps.Polyline[]>([]);
  const markersRef = useRef<google.maps.marker.AdvancedMarkerElement[]>([]);
  const markerDragRef = useRef<string | null>(null);

  const [miniGridEdges, setMiniGridEdges] = useState<MiniGridEdge[]>([]);
  const [miniGridNodes, setMiniGridNodes] = useState<MiniGridNode[]>([]);
  const [originalMiniGridNodes, setOriginalMiniGridNodes] = useState<
    MiniGridNode[]
  >([]);
  const [originalFileName, setOriginalFileName] = useState<string | null>(null);

  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [computingMiniGrid, setComputingMiniGrid] = useState(false);

  const [poleCost, setPoleCost] = useState<number>(1000);
  const [lowVoltageCost, setLowVoltageCost] = useState<number>(20);
  const [highVoltageCost, setHighVoltageCost] = useState<number>(0);

  const [
    lowVoltagePoleToPoleLengthConstraint,
    setLowVoltagePoleToPoleLengthConstraint,
  ] = useState<number>(30);
  const [
    lowVoltagePoleToTerminalLengthConstraint,
    setLowVoltagePoleToTerminalLengthConstraint,
  ] = useState<number>(20);

  const [
    lowVoltagePoleToTerminalMinimumLength,
    setLowVoltagePoleToTerminalMinimumLength,
  ] = useState<number>(5);

  const [
    highVoltagePoleToPoleLengthConstraint,
    setHighVoltagePoleToPoleLengthConstraint,
  ] = useState<number>(0);
  const [
    highVoltagePoleToTerminalLengthConstraint,
    setHighVoltagePoleToTerminalLengthConstraint,
  ] = useState<number>(0);

  const [
    highVoltagePoleToTerminalMinimumLength,
    setHighVoltagePoleToTerminalMinimumLength,
  ] = useState<number>(0);

  const [costBreakdown, setCostBreakdown] = useState<CostBreakdown>({
    lowVoltageMeters: 0,
    highVoltageMeters: 0,
    totalMeters: 0,
    lowWireCost: 0,
    highWireCost: 0,
    wireCost: 0,
    poleCount: 0,
    poleCost: 0,
    pointCount: 0,
    grandTotal: 0,
  });

  const poleCount = miniGridNodes.filter((n) => n.type === 'pole').length;
  const hasPoles = poleCount > 0;

  const [solverOriginalCost, setSolverOriginalCost] = useState<number>(0);

  const [selectedCount, setSelectedCount] = useState<number>(10);
  const [isDragOver, setIsDragOver] = useState(false);
  const [allowDragTerminals, setAllowDragTerminals] = useState(true);
  const allowDragTerminalsRef = useRef(true); // Add this line
  const [showEdgeLengths, setShowEdgeLengths] = useState(true); // ← NEW

  const [expandedSections, setExpandedSections] = useState<
    Record<string, boolean>
  >({
    markers: false,
    costs: false, // ← default open
    solver: false, // ← new
    export: false,
    savedGrids: false,
  });

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const [isAddPointDialogOpen, setIsAddPointDialogOpen] = useState(false);
  const [pendingPoint, setPendingPoint] = useState<{
    lat: number;
    lng: number;
  } | null>(null);
  const [newPointDetails, setNewPointDetails] = useState({
    name: '',
    type: 'terminal' as 'source' | 'terminal' | 'pole',
  });

  const [solvers, setSolvers] = useState<Solvers[]>([]);
  const [selectedSolverName, setSelectedSolverName] = useState<string>(
    'DiskBasedSteinerSolver'
  );

  const selectedSolver = solvers.find((s) => s.name === selectedSolverName);
  const [paramValues, setParamValues] = useState<Record<string, any>>({});
  const [useExistingPoles, setUseExistingPoles] = useState(false);

  const [calcError, setCalcError] = useState<string | null>(null);

  const [manualPoint, setManualPoint] = useState({
    name: '',
    lat: '',
    lng: '',
    type: 'terminal' as 'source' | 'terminal' | 'pole',
  });

  const lengthLabelsRef = useRef<google.maps.marker.AdvancedMarkerElement[]>(
    []
  );

  const [savedRuns, setSavedRuns] = useState<MiniGridRun[]>([]);
  const [loadingSaved, setLoadingSaved] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const { saveState, undo, redo, canUndo, canRedo } = useMiniGridHistory({
    miniGridNodes: [],
    miniGridEdges: [],
    costBreakdown: {
      lowVoltageMeters: 0,
      highVoltageMeters: 0,
      totalMeters: 0,
      lowWireCost: 0,
      highWireCost: 0,
      wireCost: 0,
      poleCount: 0,
      poleCost: 0,
      pointCount: 0,
      grandTotal: 0,
    },
    solverOriginalCost: 0,
  });

  // 1. Add this near your other refs
  const stateRef = useRef({
    miniGridNodes,
    miniGridEdges,
    costBreakdown,
    solverOriginalCost,
    lowVoltageCost,
    highVoltageCost,
    saveState,
  });

  // 2. Add this effect to sync it automatically
  useEffect(() => {
    stateRef.current = {
      miniGridNodes,
      miniGridEdges,
      costBreakdown,
      solverOriginalCost, // ← NEW
      lowVoltageCost,
      highVoltageCost,
      saveState,
    };
  }, [
    miniGridNodes,
    miniGridEdges,
    costBreakdown,
    solverOriginalCost, // ← NEW
    lowVoltageCost,
    highVoltageCost,
    saveState,
  ]);

  // Helper to bundle current state for the hook
  const captureState = (overrides = {}) => ({
    miniGridNodes,
    miniGridEdges,
    costBreakdown,
    solverOriginalCost, // ← NEW
    ...overrides,
  });

  // ==================== KEYBOARD SHORTCUTS ====================
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // 1. Guard: Do not trigger if the user is typing inside an input box
      const target = e.target as HTMLElement;
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) {
        return;
      }

      // 2. Detect Ctrl (Windows/Linux) or Cmd (Mac)
      const isModifierPressed = e.metaKey || e.ctrlKey;

      if (isModifierPressed && e.key.toLowerCase() === 'z') {
        e.preventDefault(); // Stop the browser's default text undo behavior

        if (e.shiftKey) {
          // REDO: Cmd/Ctrl + Shift + Z
          if (canRedo) {
            const s = redo();
            if (s) {
              setMiniGridNodes(s.miniGridNodes);
              setMiniGridEdges(s.miniGridEdges);
              setCostBreakdown(s.costBreakdown);
              setSolverOriginalCost(s.solverOriginalCost ?? 0);
            }
          }
        } else {
          // UNDO: Cmd/Ctrl + Z
          if (canUndo) {
            const s = undo();
            if (s) {
              setMiniGridNodes(s.miniGridNodes);
              setMiniGridEdges(s.miniGridEdges);
              setCostBreakdown(s.costBreakdown);
              setSolverOriginalCost(s.solverOriginalCost ?? 0);
            }
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    // Cleanup the event listener when the component unmounts or state changes
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [canUndo, canRedo, undo, redo]); // Keep dependencies updated

  const { data: session } = useSession();

  useEffect(() => {
    allowDragTerminalsRef.current = allowDragTerminals;
  }, [allowDragTerminals]);

  useEffect(() => {
    lengthLabelsRef.current.forEach((label) => {
      if (label) {
        label.map = showEdgeLengths ? map : null;
      }
    });
  }, [showEdgeLengths, map, miniGridEdges]);

  // ==================== MAP CLICK TO ADD MARKER ====================
  useEffect(() => {
    if (!map) return;

    const clickListener = map.addListener(
      'click',
      (e: google.maps.MapMouseEvent) => {
        if (!e.latLng) return;

        const lat = e.latLng.lat();
        const lng = e.latLng.lng();

        // Optional: ignore clicks that are very close to existing markers
        const tooClose = miniGridNodes.some(
          (n) => haversineDistance(n.lat, n.lng, lat, lng) < 5
        );

        if (tooClose) return;

        setPendingPoint({ lat, lng });
        setIsAddPointDialogOpen(true);
      }
    );

    // Cleanup
    return () => {
      google.maps.event.removeListener(clickListener);
    };
  }, [map, miniGridNodes]); // Re-attach if points change (optional)

  const handleRemovePoint = useCallback(
    (pointName: string) => {
      // 1. Get the latest state from the Ref to avoid stale closures
      const current = stateRef.current;

      console.log('number of nodes before deletion', miniGridNodes.length);
      console.log('number of edges before deletion', miniGridEdges.length);

      // 2. Filter out the point and its node
      const updatedNodes = current.miniGridNodes.filter(
        (n) => n.name !== pointName
      );

      // 3. Critically: Remove any edges connected to this specific point
      // We check if both the start and end of an edge still exist in the new points list
      const updatedEdges = current.miniGridEdges.filter((edge) => {
        const startExists = updatedNodes.some(
          (n) => n.name === edge.start.name
        );
        const endExists = updatedNodes.some((n) => n.name === edge.end.name);
        return startExists && endExists;
      });

      // 4. Update React State
      setMiniGridNodes(updatedNodes);
      setMiniGridEdges(updatedEdges);

      console.log('number of nodes before deletion', updatedNodes.length);
      console.log('number of edges before deletion', updatedEdges.length);

      // 5. Push to History
      current.saveState({
        miniGridNodes: updatedNodes,
        miniGridEdges: updatedEdges,
        costBreakdown: current.costBreakdown, // You may want to trigger a cost recalc here
        solverOriginalCost: current.solverOriginalCost,
      });
    },
    [saveState] // ← important
  );

  const handleDeleteEdge = useCallback((clickedEdge: MiniGridEdge) => {
    const current = stateRef.current;

    if (
      !window.confirm(
        `Delete this ${clickedEdge.voltage.toUpperCase()} edge (${formatMeters(
          clickedEdge.lengthMeters
        )} m)?`
      )
    ) {
      return;
    }

    // Remove the edge (handles both forward and reverse direction)
    const updatedEdges = current.miniGridEdges.filter((e) => {
      const sameForward =
        e.start.name === clickedEdge.start.name &&
        e.end.name === clickedEdge.end.name;

      const sameReverse =
        e.start.name === clickedEdge.end.name &&
        e.end.name === clickedEdge.start.name;

      return !(sameForward || sameReverse);
    });

    // Calculate cost delta
    const isLow = clickedEdge.voltage === 'low';
    const deltaMeters = clickedEdge.lengthMeters;
    const deltaWire =
      deltaMeters * (isLow ? current.lowVoltageCost : current.highVoltageCost);

    const newCostBreakdown: CostBreakdown = {
      ...current.costBreakdown,
      lowVoltageMeters:
        current.costBreakdown.lowVoltageMeters - (isLow ? deltaMeters : 0),
      highVoltageMeters:
        current.costBreakdown.highVoltageMeters - (isLow ? 0 : deltaMeters),
      totalMeters: current.costBreakdown.totalMeters - deltaMeters,
      lowWireCost: current.costBreakdown.lowWireCost - (isLow ? deltaWire : 0),
      highWireCost:
        current.costBreakdown.highWireCost - (isLow ? 0 : deltaWire),
      wireCost: current.costBreakdown.wireCost - deltaWire,
      grandTotal: current.costBreakdown.grandTotal - deltaWire,
    };

    // Update React state
    setMiniGridEdges(updatedEdges);
    setCostBreakdown(newCostBreakdown);

    // Save to history
    current.saveState({
      miniGridNodes: current.miniGridNodes,
      miniGridEdges: updatedEdges,
      costBreakdown: newCostBreakdown,
      solverOriginalCost: current.solverOriginalCost,
    });
  }, []); // no extra deps needed — everything comes from the live ref

  const createMarker = useCallback(
    (
      point: {
        lat: number;
        lng: number;
        name: string;
        type?: 'source' | 'terminal' | 'pole';
      },
      map: google.maps.Map
    ) => {
      const type = point.type || 'terminal';

      let displayTitle = point.name;
      if (point.type && !point.name.toLowerCase().includes(`(${point.type}`)) {
        displayTitle = `${point.name} (${point.type})`;
      }

      let iconUrl = 'http://maps.google.com/mapfiles/ms/icons/';
      let labelColor = 'white';
      let scaledSize = new google.maps.Size(36, 36);
      let fontSize = '13px';

      switch (type) {
        case 'source':
          iconUrl += 'green-dot.png';
          labelColor = '#00ff00';
          scaledSize = new google.maps.Size(44, 44);
          break;
        case 'terminal':
          iconUrl += 'blue-dot.png';
          labelColor = 'white';
          scaledSize = new google.maps.Size(20, 20);
          fontSize = '8';
          break;
        case 'pole':
          iconUrl += 'yellow-dot.png';
          scaledSize = new google.maps.Size(28, 28);
          fontSize = '11px';
          labelColor = '#ffff99';
          break;
        default:
          iconUrl += 'red-dot.png';
      }

      // === Build custom content properly ===
      const content = document.createElement('div');
      content.style.display = 'flex';
      content.style.flexDirection = 'column';
      content.style.alignItems = 'center';
      content.style.position = 'relative';
      content.style.pointerEvents = 'auto'; // Important for clicks

      // Icon wrapper with delete button
      const iconWrapper = document.createElement('div');
      iconWrapper.style.position = 'relative';
      iconWrapper.style.width = '44px';
      iconWrapper.style.height = '44px';
      iconWrapper.style.display = 'flex';
      iconWrapper.style.alignItems = 'center';
      iconWrapper.style.justifyContent = 'center';

      const iconImg = document.createElement('img');
      iconImg.src = iconUrl;
      iconImg.style.width = `${scaledSize.width}px`;
      iconImg.style.height = `${scaledSize.height}px`;
      iconImg.style.pointerEvents = 'none'; // Let wrapper handle events

      iconWrapper.appendChild(iconImg);

      // ==================== DELETE BUTTON (HOVER ONLY) ====================
      const deleteBtn = document.createElement('button');
      deleteBtn.textContent = '×';
      deleteBtn.style.position = 'absolute';
      deleteBtn.style.top = '-4px';
      deleteBtn.style.right = '-4px';
      deleteBtn.style.background = '#ef4444';
      deleteBtn.style.color = 'white';
      deleteBtn.style.border = 'none';
      deleteBtn.style.borderRadius = '9999px';
      deleteBtn.style.width = '18px';
      deleteBtn.style.height = '18px';
      deleteBtn.style.fontSize = '14px';
      deleteBtn.style.lineHeight = '1';
      deleteBtn.style.cursor = 'pointer';
      deleteBtn.style.boxShadow = '0 2px 6px rgba(0,0,0,0.4)';
      deleteBtn.style.zIndex = '100';
      deleteBtn.style.pointerEvents = 'auto';
      deleteBtn.style.opacity = '0'; // ← Hidden by default
      deleteBtn.style.transition = 'opacity 0.2s ease-in-out';

      // Show on hover (works over icon AND label)
      content.addEventListener('mouseenter', () => {
        deleteBtn.style.opacity = '1';
      });

      content.addEventListener('mouseleave', () => {
        deleteBtn.style.opacity = '0';
      });

      deleteBtn.addEventListener('click', (e) => {
        e.stopImmediatePropagation();
        e.preventDefault();

        if (window.confirm(`Delete ${point.name}?`)) {
          handleRemovePoint(point.name);
        }
      });

      iconWrapper.appendChild(deleteBtn);
      // =================================================================

      // Label below the icon
      const labelSpan = document.createElement('span');
      labelSpan.textContent = point.name;
      labelSpan.style.color = labelColor;
      labelSpan.style.fontSize = fontSize;
      labelSpan.style.fontWeight = 'bold';
      labelSpan.style.textShadow = '0 0 3px black';
      labelSpan.style.marginTop = '3px';
      labelSpan.style.pointerEvents = 'none';

      // Assemble in correct order
      content.appendChild(iconWrapper);
      content.appendChild(labelSpan);

      content.style.position = 'relative';
      content.style.transform = 'translate(0%, 25%)';

      const marker = new google.maps.marker.AdvancedMarkerElement({
        position: { lat: point.lat, lng: point.lng },
        map,
        content,
        title: displayTitle,
        gmpDraggable: true,
      });

      // === Drag logic remains mostly the same ===
      // (your existing dragstart, drag, dragend listeners go here)

      marker.addListener('dragstart', () => {
        const literal = toLiteral(marker.position);
        if (literal) {
          markerDragRef.current = `${literal.lat},${literal.lng}`;
        }
      });

      marker.addListener('drag', () => {
        const currentPos = toLiteral(marker.position);
        const prevStr = markerDragRef.current;
        if (!currentPos || !prevStr) return;

        const [prevLat, prevLng] = prevStr.split(',').map(Number);
        const isPole = point.type === 'pole';

        // 1. RULE: Terminals can only move if allowDragTerminals is true
        // We use the Ref version of the state if you have one, or ensure this
        // function is recreated when allowDragTerminals changes.
        if (!isPole && !allowDragTerminalsRef.current) {
          marker.position = { lat: prevLat, lng: prevLng };
          return;
        }

        let exceedsLimit = false;
        const targetLat = currentPos.lat;
        const targetLng = currentPos.lng;

        // 2. RULE: No edge can exceed 30m
        // We check every polyline connected to this specific marker
        polylinesRef.current.forEach((line) => {
          const path = line.getPath();
          if (path.getLength() !== 2) return;

          const start = path.getAt(0);
          const end = path.getAt(1);

          // NEW: Get the full edge data we attached when creating the polyline
          // (now contains complete MiniGridNode objects for start and end)
          const edgeData = line.get('edgeData') as MiniGridEdge | undefined;
          if (!edgeData) return;

          // Identify if this line is attached to the marker we are dragging
          const isStart = edgeData.start.name === point.name;
          const isEnd = edgeData.end.name === point.name;

          if (isStart || isEnd) {
            const otherNode = isStart ? end : start;
            const distance = haversineDistance(
              targetLat,
              targetLng,
              otherNode.lat(),
              otherNode.lng()
            );

            const isHighVoltage = line.get('strokeColor') === highVoltageColor;

            // Simplified — we can now read the type directly from the full nodes!
            const isPoleToPole =
              edgeData.start.type === 'pole' && edgeData.end.type === 'pole';

            let maxAllowedMeters: number;

            if (isPoleToPole) {
              maxAllowedMeters = isHighVoltage
                ? highVoltagePoleToPoleLengthConstraint
                : lowVoltagePoleToPoleLengthConstraint;
            } else {
              // Pole to Terminal (or Terminal to Pole)
              maxAllowedMeters = isHighVoltage
                ? highVoltagePoleToTerminalLengthConstraint
                : lowVoltagePoleToTerminalLengthConstraint;
            }

            if (distance > maxAllowedMeters) {
              exceedsLimit = true;
            }
          }
        });

        // 3. ENFORCEMENT: If any rule is broken, snap back and EXIT
        if (exceedsLimit) {
          marker.position = { lat: prevLat, lng: prevLng };
          return;
        }

        // 4. UPDATE VISUALS: If rules are passed, move the lines and update solver
        const costDiff = { low: 0, high: 0 };

        polylinesRef.current.forEach((line) => {
          const path = line.getPath();
          const start = path.getAt(0);
          const end = path.getAt(1);
          const lineType =
            line.get('strokeColor') === lowVoltageColor ? 'low' : 'high';

          let isMatched = false;
          const oldDist = haversineDistance(
            start.lat(),
            start.lng(),
            end.lat(),
            end.lng()
          );

          if (
            Math.abs(start.lat() - prevLat) < 1e-9 &&
            Math.abs(start.lng() - prevLng) < 1e-9
          ) {
            line.setPath([{ lat: targetLat, lng: targetLng }, end]);
            isMatched = true;
          } else if (
            Math.abs(end.lat() - prevLat) < 1e-9 &&
            Math.abs(end.lng() - prevLng) < 1e-9
          ) {
            line.setPath([start, { lat: targetLat, lng: targetLng }]);
            isMatched = true;
          }

          if (isMatched) {
            const newDist = haversineDistance(
              line.getPath().getAt(0).lat(),
              line.getPath().getAt(0).lng(),
              line.getPath().getAt(1).lat(),
              line.getPath().getAt(1).lng()
            );
            costDiff[lineType] += newDist - oldDist;
          }
        });

        // 5. UPDATE STATE: Apply cost changes to the UI
        setCostBreakdown((prev) => {
          const addedWireCost =
            costDiff.low * lowVoltageCost + costDiff.high * highVoltageCost;
          return {
            ...prev,
            lowVoltageMeters: prev.lowVoltageMeters + costDiff.low,
            highVoltageMeters: prev.highVoltageMeters + costDiff.high,
            totalMeters: prev.totalMeters + costDiff.low + costDiff.high,
            wireCost: prev.wireCost + addedWireCost,
            grandTotal: prev.grandTotal + addedWireCost,
          };
        });

        // Update the reference for the next 'drag' tick
        markerDragRef.current = `${targetLat},${targetLng}`;
      });

      // 5. Enforce final snap back when the user lets go of the mouse
      marker.addListener('dragend', () => {
        const prevStr = markerDragRef.current;

        // 1. GUARD: Prevent phantom events from destroying the undo stack
        // If there is no active drag reference, this is a phantom event from unmounting.
        if (!prevStr) return;

        // The prevStr holds the final valid position from the last 'drag' tick
        const [finalLat, finalLng] = prevStr.split(',').map(Number);

        // Snap the visual marker to ensure it rests exactly on the valid coords
        marker.position = { lat: finalLat, lng: finalLng };

        // 2. Grab the absolute latest state to avoid stale closures
        const current = stateRef.current;

        // 2. Calculate newly updated arrays synchronously
        const updatedNodes = current.miniGridNodes.map((n) =>
          n.name === point.name ? { ...n, lat: finalLat, lng: finalLng } : n
        );

        const updatedEdges = current.miniGridEdges.map((edge) => {
          if (edge.start.name === point.name) {
            return {
              ...edge,
              start: { ...edge.start, lat: finalLat, lng: finalLng },
              lengthMeters: haversineDistance(
                finalLat,
                finalLng,
                edge.end.lat,
                edge.end.lng
              ),
            };
          }
          if (edge.end.name === point.name) {
            return {
              ...edge,
              end: { ...edge.end, lat: finalLat, lng: finalLng },
              lengthMeters: haversineDistance(
                edge.start.lat,
                edge.start.lng,
                finalLat,
                finalLng
              ),
            };
          }
          return edge;
        });

        // 3. Update React State with the newly calculated arrays
        setMiniGridNodes(updatedNodes);
        setMiniGridEdges(updatedEdges);

        // 4. Save to History EXACTLY the fresh state you just calculated
        current.saveState({
          miniGridNodes: updatedNodes,
          miniGridEdges: updatedEdges,
          costBreakdown: current.costBreakdown,
          solverOriginalCost: current.solverOriginalCost,
        });

        markerDragRef.current = null;
      });

      return marker;
    },
    [handleRemovePoint]
  );

  const [sidebarWidth, setSidebarWidth] = useState(500); // default width

  const [isResizing, setIsResizing] = useState(false);

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (!isResizing) return;

    const newWidth = e.clientX; // ← Changed: now uses left position (clientX)

    if (newWidth >= 320 && newWidth <= 600) {
      setSidebarWidth(newWidth);
    }
  };

  const handleMouseUp = () => {
    setIsResizing(false);
    document.body.style.cursor = 'default';
    document.body.style.userSelect = '';
  };

  const getNextNameForType = (type: 'source' | 'terminal' | 'pole'): string => {
    const allPoints = [...miniGridNodes];

    const existingNumbers = allPoints
      .filter((p) => p.type === type)
      .map((p) => {
        const match = p.name.match(/(\d+)$/);
        return match ? parseInt(match[1], 10) : 0;
      })
      .filter((n) => !isNaN(n));

    const maxNumber =
      existingNumbers.length > 0 ? Math.max(...existingNumbers) : 0;
    const nextNumber = maxNumber + 1;

    const typeLabel = type.charAt(0).toUpperCase() + type.slice(1);
    return `${typeLabel} ${String(nextNumber).padStart(2, '0')}`;
  };

  // Inside MiniGridToolPage component, near your other useEffects
  // Replace the old useEffect with this one
  useEffect(() => {
    if (!isAddPointDialogOpen) return;
    const nextName = getNextNameForType(newPointDetails.type);
    setNewPointDetails((prev) => ({ ...prev, name: nextName }));
  }, [isAddPointDialogOpen, newPointDetails.type, miniGridNodes]);

  // 1. Wrap initMap in useCallback to stabilize it
  const initMap = useCallback(() => {
    // Only initialize if the global object exists, the ref is ready, and we haven't already set a map state
    if (!window.google?.maps || !mapRef.current || map) return;

    const googleMap = new window.google.maps.Map(mapRef.current, {
      center: { lat: 39.8283, lng: -98.5795 },
      zoom: 4,
      mapTypeId: 'satellite' as google.maps.MapTypeId,
      fullscreenControl: false,
      streetViewControl: false,
      mapId: 'DEMO_MAP_ID',
      mapTypeControl: true, // ensure it's visible
      mapTypeControlOptions: {
        style: google.maps.MapTypeControlStyle.DEFAULT, // or HORIZONTAL_BAR, DROPDOWN_MENU
        position: google.maps.ControlPosition.TOP_RIGHT,
      },
    });

    setMap(googleMap);
  }, [map]);

  // 2. Add this effect to catch cases where the script is already loaded (navigation back)
  useEffect(() => {
    if (window.google?.maps && mapRef.current && !map) {
      initMap();
    }
  }, [initMap, map]);

  useEffect(() => {
    if (isResizing) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  });
  // ==================== SOLVERS & PARAMETERS ====================
  useEffect(() => {
    fetch(
      process.env.NEXT_PUBLIC_GET_SOLVERS || 'http://localhost:8000/solvers'
    )
      .then((res) => res.json())
      .then((data) => setSolvers(data.solvers || []));
  }, []);

  useEffect(() => {
    if (!selectedSolver) {
      setParamValues({});
      return;
    }

    // Changed from Record<string, number> to Record<string, any>
    const initial: Record<string, any> = {};
    selectedSolver.params.forEach((p) => {
      initial[p.name] = p.default;
    });

    setParamValues(initial);
  }, [selectedSolverName, selectedSolver]);

  const updateParam = (paramName: string, value: any) => {
    const paramDef = selectedSolver?.params.find((p) => p.name === paramName);
    if (!paramDef) return;

    let parsedValue = value;

    if (paramDef.type === 'bool') {
      parsedValue = Boolean(value); // safely convert to boolean
    } else if (paramDef.type === 'int' || paramDef.type === 'float') {
      parsedValue = Number(value);
      if (isNaN(parsedValue)) return;
    } else {
      parsedValue = String(value);
    }

    setParamValues((prev) => ({ ...prev, [paramName]: parsedValue }));
  };

  // ==================== MAP EFFECTS (Markers + Lines) ====================
  useEffect(() => {
    if (!map) return;

    // Clear old polylines
    polylinesRef.current.forEach((line) => line.setMap(null));
    polylinesRef.current = [];

    // Clear old length labels
    lengthLabelsRef.current.forEach((label) => {
      label.map = null;
    });
    lengthLabelsRef.current = [];

    miniGridEdges.forEach((edge) => {
      if (!edge.start || !edge.end) return;

      const color =
        edge.voltage === 'high' ? highVoltageColor : lowVoltageColor;
      const weight = edge.voltage === 'high' ? 6 : 4;

      const polyline = new google.maps.Polyline({
        path: [edge.start, edge.end],
        geodesic: true,
        strokeColor: color,
        strokeOpacity: 0.9,
        strokeWeight: weight,
        map,
      });

      polyline.set('edgeData', { ...edge });
      polyline.addListener('click', () => {
        const edgeData = polyline.get('edgeData') as MiniGridEdge;
        if (edgeData) handleDeleteEdge(edgeData);
      });

      polylinesRef.current.push(polyline);

      // === NEW: Add length label at midpoint ===
      const midLat = (edge.start.lat + edge.end.lat) / 2;
      const midLng = (edge.start.lng + edge.end.lng) / 2;

      const labelContent = document.createElement('div');
      labelContent.className = 'edge-length-label';
      labelContent.style.cssText = `
      background: rgba(0, 0, 0, 0.75);
      color: white;
      font-size: 11px;
      font-weight: 600;
      padding: 2px 6px;
      border-radius: 9999px;
      white-space: nowrap;
      pointer-events: none;
      user-select: none;
      box-shadow: 0 1px 3px rgba(0,0,0,0.4);
      border: 1px solid rgba(255,255,255,0.2);
    `;
      labelContent.textContent = `${formatMeters(edge.lengthMeters)} m`;

      const lengthLabel = new google.maps.marker.AdvancedMarkerElement({
        position: { lat: midLat, lng: midLng },
        map,
        content: labelContent,
        zIndex: 10, // above polylines
      });

      lengthLabelsRef.current.push(lengthLabel);
    });
  }, [map, miniGridEdges]);

  useEffect(() => {
    return () => {
      lengthLabelsRef.current.forEach((label) => {
        label.map = null;
      });
    };
  }, []);

  // ==================== FILE HANDLING, SOLVER, etc. ====================
  const getSolversURL =
    process.env.NEXT_PUBLIC_GET_SOLVERS || 'http://localhost:8000/solvers';

  useEffect(() => {
    if (!session?.user?.id) return;

    const fetchSaved = async () => {
      setLoadingSaved(true);
      try {
        const res = await fetch('/api/minigrids');
        if (res.ok) {
          const data = await res.json();
          setSavedRuns(data);
        }
      } catch (err) {
        console.error('Failed to load saved runs', err);
      } finally {
        setLoadingSaved(false);
      }
    };

    fetchSaved();
  }, [session?.user?.id]);

  // ==================== MARKER RENDERING ====================
  const shouldAutoFit = useRef(true);

  useEffect(() => {
    if (!map) return;

    // Clear old markers safely
    markersRef.current.forEach((marker) => {
      google.maps.event.clearInstanceListeners(marker);
      marker.map = null;
    });
    markersRef.current = [];

    // Combine points - miniGridNodes has priority
    const allPointsMap = new Map<string, MiniGridNode>();

    miniGridNodes.forEach((node) => {
      if (node?.name) allPointsMap.set(node.name, node);
    });

    const pointsToShow = Array.from(allPointsMap.values());

    if (pointsToShow.length === 0) return;

    const bounds = new google.maps.LatLngBounds();
    let hasValidPoints = false;

    pointsToShow.forEach((point) => {
      if (isNaN(point.lat) || isNaN(point.lng)) return;

      hasValidPoints = true;

      const marker = createMarker(
        {
          lat: point.lat,
          lng: point.lng,
          name: point.name,
          type: point.type,
        },
        map
      );

      markersRef.current.push(marker);
      bounds.extend({ lat: point.lat, lng: point.lng });
    });

    // Auto-fit when appropriate
    if (hasValidPoints && shouldAutoFit.current) {
      // ← add a ref
      setTimeout(() => {
        map.fitBounds(bounds, { bottom: 80, left: 250, right: 20, top: 80 });
      }, 50);
    }

    shouldAutoFit.current = false;
  }, [map, miniGridNodes, createMarker]);

  // ==================== FETCH SOLVERS ====================
  useEffect(() => {
    const fetchSolvers = async () => {
      try {
        // 1. ADD A CACHE BUSTER TO THE URL
        const cacheBusterUrl = `${getSolversURL}?t=${Date.now()}`;

        const res = await fetch(cacheBusterUrl, {
          method: 'GET',
          cache: 'no-store', // Force fresh response
          headers: {
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            Pragma: 'no-cache',
            Expires: '0',
          },
        });

        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }

        const rawData = await res.json();

        let solversList: any[] = [];

        if (Array.isArray(rawData)) {
          solversList = rawData;
        } else if (rawData.solvers && Array.isArray(rawData.solvers)) {
          solversList = rawData.solvers;
        } else if (rawData.data) {
          solversList = Array.isArray(rawData.data) ? rawData.data : [];
        }

        // Final cleaning
        const cleanedSolvers = solversList.map((s: any) => ({
          name: s.name || String(s),
          params: Array.isArray(s.params) ? s.params : [],
        }));

        setSolvers(cleanedSolvers);
      } catch (err) {
        console.error('❌ Failed to fetch solvers:', err);

        // Emergency fallback
        setSolvers([
          {
            name: 'SimpleMSTSolver',
            params: [
              {
                name: 'steinerize',
                type: 'bool',
                default: false,
                description: 'Whether to steinerize the MST Edges',
              },
            ],
          },
          { name: 'DiskBasedSteinerSolver', params: [] },
          { name: 'GreedyIterSteinerSolver', params: [] },
        ]);
      }
    };

    fetchSolvers();
  }, [getSolversURL]);

  // ==================== INITIALIZE PARAM VALUES ====================
  useEffect(() => {
    if (!selectedSolver) {
      setParamValues({});
      return;
    }

    const initial: Record<string, any> = {};

    selectedSolver.params.forEach((param) => {
      // Use the default value as-is (boolean, number, string, etc.)
      initial[param.name] = param.default;
    });

    setParamValues(initial);
  }, [selectedSolver, selectedSolverName]);

  const handleConfirmNewPoint = () => {
    if (!pendingPoint) return;

    const newLocation: MiniGridNode = {
      index: miniGridNodes.length + 1,
      name: newPointDetails.name,
      type: newPointDetails.type,
      lat: pendingPoint.lat,
      lng: pendingPoint.lng,
    };

    const updatedNodes: MiniGridNode[] = [...miniGridNodes, newLocation];

    // Update React State
    setMiniGridNodes(updatedNodes);

    // --- START COST RECALCULATION ---
    let updatedCostBreakdown = { ...costBreakdown };

    if (newPointDetails.type === 'pole') {
      const newPoleCount = updatedCostBreakdown.poleCount + 1;
      const newPoleCostTotal = newPoleCount * poleCost;

      updatedCostBreakdown = {
        ...updatedCostBreakdown,
        poleCount: newPoleCount,
        poleCost: newPoleCostTotal,
        // Update grand total by adding a single pole's cost
        grandTotal: updatedCostBreakdown.grandTotal + poleCost,
      };

      // Update state so the UI reflects the change immediately
      setCostBreakdown(updatedCostBreakdown);
    }

    // Save to History (Pass the updated arrays directly)
    saveState(
      captureState({
        miniGridNodes: updatedNodes,
        miniGridEdges: [...miniGridEdges],
        costBreakdown: { ...costBreakdown },
      })
    );

    setIsAddPointDialogOpen(false);
    setPendingPoint(null);
  };

  const handleAddCoordinatesManually = (e: React.FormEvent) => {
    e.preventDefault();
    const lat = parseFloat(manualPoint.lat);
    const lng = parseFloat(manualPoint.lng);

    if (isNaN(lat) || isNaN(lng)) {
      alert('Please enter valid latitude and longitude numbers.');
      return;
    }

    const newPoint: MiniGridNode = {
      index: miniGridNodes.length + 1,
      name: manualPoint.name || `Manual Point ${miniGridNodes.length + 1}`,
      type: manualPoint.type,
      lat: lat,
      lng: lng,
    };

    setMiniGridNodes((prev) => [...prev, newPoint]);

    // Reset form
    setManualPoint({ name: '', lat: '', lng: '', type: 'terminal' });

    setAllowDragTerminals(true);

    saveState(captureState({}));
  };

  // Enhanced parseKml to handle solved KMLs
  // ====================== FIXED parseKml FUNCTION ======================
  // Replace your entire existing parseKml function (around lines 520-650) with this version:

  const parseKml = (
    text: string
  ): {
    nodes: MiniGridNode[];
    edges: MiniGridEdge[];
    costBreakdown: CostBreakdown;
  } => {
    const parser = new DOMParser();
    const xml = parser.parseFromString(text, 'application/xml');

    if (xml.getElementsByTagName('parsererror').length > 0) {
      console.error('KML parsing error');
      return {
        nodes: [],
        edges: [],
        costBreakdown: {
          lowVoltageMeters: 0,
          highVoltageMeters: 0,
          totalMeters: 0,
          lowWireCost: 0,
          highWireCost: 0,
          wireCost: 0,
          poleCount: 0,
          poleCost: 0,
          pointCount: 0,
          grandTotal: 0,
        },
      };
    }

    const placemarks = Array.from(xml.getElementsByTagName('Placemark'));
    const nodes: MiniGridNode[] = [];
    const edges: MiniGridEdge[] = [];

    // ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
    // CRITICAL FIX: Declare costBreakdown BEFORE the loop
    // ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
    const costBreakdown: CostBreakdown = {
      lowVoltageMeters: 0,
      highVoltageMeters: 0,
      totalMeters: 0,
      lowWireCost: 0,
      highWireCost: 0,
      wireCost: 0,
      poleCount: 0,
      poleCost: 0,
      pointCount: 0,
      grandTotal: 0,
      // Optional fields we'll populate from the summary
      usedPoleCost: undefined,
      usedLowCostPerMeter: undefined,
      usedHighCostPerMeter: undefined,
    };

    placemarks.forEach((pm) => {
      const nameEl = pm.getElementsByTagName('name')[0];
      const name = nameEl?.textContent?.trim() || '';

      const descEl = pm.getElementsByTagName('description')[0];
      let descText = descEl?.textContent?.trim() || '';

      // Clean description text
      descText = descText
        .replace(/<[^>]+>/g, '')
        .replace(/\xa0/g, ' ')
        .replace(/• /g, '')
        .trim();

      const pointEl = pm.getElementsByTagName('Point')[0];
      const lineEl = pm.getElementsByTagName('LineString')[0];

      if (pointEl) {
        const coordsText =
          pointEl.getElementsByTagName('coordinates')[0]?.textContent?.trim() ||
          '';
        if (!coordsText) return;

        const [lngStr, latStr] = coordsText.split(',');
        const lng = parseFloat(lngStr);
        const lat = parseFloat(latStr);
        if (isNaN(lat) || isNaN(lng)) return;

        // ==================== SUMMARY PLACEMARK (COST DATA) ====================
        if (lat === 0 && lng === 0 && name === 'Mini-Grid Cost Summary') {
          const lines = descText
            .split(/\n+/)
            .map((l) => l.trim())
            .filter((l) => l);

          lines.forEach((line) => {
            if (line.startsWith('Grand Total:')) {
              costBreakdown.grandTotal =
                parseFloat(line.split(':')[1].replace(/[^0-9.]/g, '')) || 0;
            } else if (line.startsWith('Wire:')) {
              costBreakdown.wireCost =
                parseFloat(line.split(':')[1].replace(/[^0-9.]/g, '')) || 0;
            } else if (line.startsWith('Low:')) {
              const parts = line.split('→');
              if (parts[0]) {
                costBreakdown.lowVoltageMeters =
                  parseFloat(parts[0].replace(/[^0-9.]/g, '')) || 0;
              }
              if (parts[1]) {
                costBreakdown.lowWireCost =
                  parseFloat(parts[1].replace(/[^0-9.]/g, '')) || 0;
              }
            } else if (line.startsWith('High:')) {
              const parts = line.split('→');
              if (parts[0]) {
                costBreakdown.highVoltageMeters =
                  parseFloat(parts[0].replace(/[^0-9.]/g, '')) || 0;
              }
              if (parts[1]) {
                costBreakdown.highWireCost =
                  parseFloat(parts[1].replace(/[^0-9.]/g, '')) || 0;
              }
            } else if (line.startsWith('Poles:')) {
              const parts = line.split(':')[1].split('×');
              if (parts[0]) {
                costBreakdown.poleCount = parseInt(parts[0].trim()) || 0;
              }
              if (parts[1]) {
                costBreakdown.usedPoleCost =
                  parseFloat(parts[1].replace(/[^0-9.]/g, '')) || 0;
              }
              costBreakdown.poleCost =
                costBreakdown.poleCount * (costBreakdown.usedPoleCost || 0);
            } else if (line.startsWith('Nodes:')) {
              costBreakdown.pointCount =
                parseInt(line.split(':')[1].split('•')[0].trim()) || 0;
            }
          });

          // Calculate and store original per-unit costs (this is what you asked for)
          if (costBreakdown.lowVoltageMeters > 0) {
            costBreakdown.usedLowCostPerMeter =
              costBreakdown.lowWireCost / costBreakdown.lowVoltageMeters;
          }
          if (costBreakdown.highVoltageMeters > 0) {
            costBreakdown.usedHighCostPerMeter =
              costBreakdown.highWireCost / costBreakdown.highVoltageMeters;
          }

          return; // done with summary
        }

        // Regular node (source/terminal/pole)
        const descLines = descText.split(/\n+/).map((l) => l.trim());
        let type: 'source' | 'terminal' | 'pole' = 'terminal';
        let index = -1;

        descLines.forEach((l) => {
          if (l.startsWith('Type:')) {
            type = l.split(':')[1].trim() as 'source' | 'terminal' | 'pole';
          }
          if (l.startsWith('Index:')) {
            index = parseInt(l.split(':')[1].trim());
          }
        });

        nodes.push({ index, lat, lng, name, type });
      } else if (lineEl) {
        // Edge parsing (unchanged – your existing code)
        const coordsText =
          lineEl.getElementsByTagName('coordinates')[0]?.textContent?.trim() ||
          '';
        const coords = coordsText.split(/\s+/).filter((c) => c);
        if (coords.length < 2) return;

        const [startLngStr, startLatStr] = coords[0].split(',');
        const [endLngStr, endLatStr] = coords[1].split(',');

        const findNode = (lat: number, lng: number) =>
          nodes.find(
            (n) => Math.abs(n.lat - lat) < 1e-9 && Math.abs(n.lng - lng) < 1e-9
          );

        const start = findNode(
          parseFloat(startLatStr),
          parseFloat(startLngStr)
        );
        const end = findNode(parseFloat(endLatStr), parseFloat(endLngStr));

        if (!start || !end) return;

        let voltage: 'low' | 'high' = 'low';
        if (name.toLowerCase().includes('(high)')) voltage = 'high';

        let lengthMeters = 0;
        const descLines = descText.split(/\n+/).map((l) => l.trim());
        descLines.forEach((l) => {
          if (l.startsWith('Length:')) {
            lengthMeters =
              parseFloat(l.split(':')[1].replace(/[^0-9.]/g, '')) || 0;
          }
        });

        edges.push({ start, end, lengthMeters, voltage });
      }
    });

    // Final safety net
    costBreakdown.totalMeters =
      costBreakdown.lowVoltageMeters + costBreakdown.highVoltageMeters;

    return { nodes, edges, costBreakdown };
  };

  const handleFileUpload = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow uploading the same file name again
    if (!file) return;

    processFile(file);
    setAllowDragTerminals(true);
    setExpandedSections({
      markers: false,
      solver: true,
      export: false,
      savedGrids: false,
    });
  };

  const processFile = (file: File) => {
    // Clear old visuals immediately (no saveState yet)
    setMiniGridEdges([]);
    setMiniGridNodes([]);
    setCostBreakdown({
      lowVoltageMeters: 0,
      highVoltageMeters: 0,
      totalMeters: 0,
      lowWireCost: 0,
      highWireCost: 0,
      wireCost: 0,
      poleCount: 0,
      poleCost: 0,
      pointCount: 0,
      grandTotal: 0,
    });
    setCalcError(null);
    setError(null);
    setFileName(file.name);
    setOriginalFileName(file.name);
    setLoading(true);

    setSolverOriginalCost(0);

    const lowerName = file.name.toLowerCase();

    if (lowerName.endsWith('.kml')) {
      // ── KML branch ─────────────────────────────────────
      const reader = new FileReader();
      reader.onload = () => {
        const text = reader.result as string;
        try {
          const parsed = parseKml(text);

          if (parsed.nodes.length === 0 && parsed.edges.length === 0) {
            setError('No valid data found in the KML file.');
            setLoading(false);
            return;
          }

          // Filter and prepare the exact state we will save
          const validNodes = parsed.nodes
            .filter((n) => !isNaN(n.lat) && !isNaN(n.lng))
            .map((n, idx) => ({
              ...n,
              index: n.index >= 0 ? n.index : idx,
            }));

          const originalPoints: MiniGridNode[] = validNodes
            .filter((n) => n.type !== 'pole')
            .map((n) => ({
              index: n.index,
              name: n.name,
              type: n.type,
              lat: n.lat,
              lng: n.lng,
            }));

          const newCostBreakdown = parsed.costBreakdown || {
            lowVoltageMeters: 0,
            highVoltageMeters: 0,
            totalMeters: 0,
            lowWireCost: 0,
            highWireCost: 0,
            wireCost: 0,
            poleCount: 0,
            poleCost: 0,
            pointCount: 0,
            grandTotal: 0,
          };

          // ─────────────────────────────────────────────────────
          // UPDATE UI STATE
          // ─────────────────────────────────────────────────────
          setMiniGridNodes(validNodes);
          setMiniGridEdges(parsed.edges);
          setOriginalMiniGridNodes(originalPoints);
          setCostBreakdown(newCostBreakdown);

          // Restore per-unit costs if they were saved in the KML
          if (parsed.costBreakdown) {
            const cb = parsed.costBreakdown;

            // Prefer the explicitly stored unit costs (most accurate)
            if (cb.usedPoleCost !== undefined && cb.usedPoleCost > 0) {
              setPoleCost(cb.usedPoleCost);
            } else if (cb.poleCount > 0 && cb.poleCost > 0) {
              setPoleCost(Math.round(cb.poleCost / cb.poleCount));
            }

            const lowM = cb.lowVoltageMeters || 0;
            if (lowM > 0) {
              const restoredLow =
                cb.usedLowCostPerMeter ?? cb.lowWireCost / lowM;
              setLowVoltageCost(Number(restoredLow.toFixed(2)));
            }

            const highM = cb.highVoltageMeters || 0;
            if (highM > 0) {
              const restoredHigh =
                cb.usedHighCostPerMeter ?? cb.highWireCost / highM;
              setHighVoltageCost(Number(restoredHigh.toFixed(2)));
            }
          }

          shouldAutoFit.current = true;
          // ─────────────────────────────────────────────────────
          // SAVE THE CORRECT NEW STATE TO HISTORY (this fixes redo)
          // ─────────────────────────────────────────────────────
          saveState({
            miniGridNodes: validNodes,
            miniGridEdges: parsed.edges,
            costBreakdown: newCostBreakdown,
            solverOriginalCost: newCostBreakdown.grandTotal,
          });
        } catch (err) {
          setError('Error parsing KML file.');
          console.error(err);
        } finally {
          setLoading(false);
        }
      };

      reader.onerror = () => {
        setError('Failed to read KML file.');
        setLoading(false);
      };
      reader.readAsText(file);
    } else {
      // ── CSV branch ─────────────────────────────────────
      Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        transformHeader: (h) => h.trim().toLowerCase(),
        complete: (result) => {
          try {
            const rows = result.data as Record<string, string>[];

            let counter = 0; // overall index counter (if needed)
            const nameCounter = new Map<string, number>(); // tracks how many times each name appeared

            const parsedPoints: MiniGridNode[] = rows
              .map((row) => {
                // Parse basic fields
                const rawName = (
                  row.name?.trim() ||
                  row['name'] ||
                  'Unnamed'
                ).trim();
                const typeStr = row.type?.trim() || row['type'] || 'terminal';
                const latStr = row.latitude || row.lat || '';
                const lngStr = row.longitude || row.lng || '';

                const lat = parseFloat(latStr);
                const lng = parseFloat(lngStr);

                if (isNaN(lat) || isNaN(lng)) return null;

                const type = typeStr.toLowerCase();

                // === Name with intelligent counter logic ===
                let displayName = rawName;

                if (nameCounter.has(rawName)) {
                  // Name has been seen before → increment counter
                  const count = nameCounter.get(rawName)! + 1;
                  nameCounter.set(rawName, count);
                  displayName = `${rawName} ${count}`;
                } else {
                  // First time seeing this name
                  nameCounter.set(rawName, 1);
                  // Keep original name (no number)
                }

                // Optional: still keep an overall index if you need it
                const index: number = Number(row.index?.trim()) || counter++;

                return {
                  index,
                  name: displayName,
                  lat,
                  lng,
                  type,
                };
              })
              .filter((p): p is MiniGridNode => p !== null);

            if (parsedPoints.length === 0) {
              setError(
                'No valid rows found. Expected columns: Name, Type (source/terminal), Latitude, Longitude.'
              );
            } else {
              // ─────────────────────────────────────────────────────
              // UPDATE UI STATE
              // ─────────────────────────────────────────────────────
              setOriginalMiniGridNodes(parsedPoints);
              setMiniGridNodes(parsedPoints);
              shouldAutoFit.current = true;

              // ─────────────────────────────────────────────────────
              // SAVE THE CORRECT NEW STATE TO HISTORY (this fixes redo)
              // ─────────────────────────────────────────────────────
              saveState({
                miniGridNodes: [], // CSV has no poles/edges yet
                miniGridEdges: [],
                costBreakdown: {
                  lowVoltageMeters: 0,
                  highVoltageMeters: 0,
                  totalMeters: 0,
                  lowWireCost: 0,
                  highWireCost: 0,
                  wireCost: 0,
                  poleCount: 0,
                  poleCost: 0,
                  pointCount: 0,
                  grandTotal: 0,
                },
                solverOriginalCost: 0,
              });
            }
          } catch (err) {
            setError('Error parsing CSV file.');
            console.error(err);
          } finally {
            setLoading(false);
          }
        },
        error: (err) => {
          setError('Failed to read file.');
          console.error(err);
          setLoading(false);
        },
      });
    }
  };

  const handleGenerateTestData = async () => {
    setLoading(true);
    setError(null);

    try {
      // Use selectedCount from state instead of a parameter
      await generateTestData(selectedCount);
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : 'Failed to generate test data';
      setError(msg);
      console.error('Test data generation failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const generateTestData = (count: number) => {
    // First, clear old derived state (but do NOT save yet)
    setMiniGridEdges([]);
    setSolverOriginalCost(0);
    setCostBreakdown({
      lowVoltageMeters: 0,
      highVoltageMeters: 0,
      totalMeters: 0,
      lowWireCost: 0,
      highWireCost: 0,
      wireCost: 0,
      poleCount: 0,
      poleCost: 0,
      pointCount: 0,
      grandTotal: 0,
    });
    setCalcError(null);
    setError(null);
    setFileName(null);

    // Generate the new points
    const centerLat = 33.77728650419152;
    const centerLng = -84.39617097270636;
    const latRange = 0.001;
    const lngRange = 0.001 / Math.cos((centerLat * Math.PI) / 180);

    const newMiniGridNodes: MiniGridNode[] = [];
    const maxAttempts = count * 10;
    let attempts = 0;

    while (newMiniGridNodes.length < count && attempts < maxAttempts) {
      const latOffset = (Math.random() - 0.5) * latRange * 2;
      const lngOffset = (Math.random() - 0.5) * lngRange * 2;

      const lat = parseFloat((centerLat + latOffset).toFixed(8));
      const lng = parseFloat((centerLng + lngOffset).toFixed(8));

      const isDuplicate = newMiniGridNodes.some(
        (point) =>
          Math.abs(point.lat - lat) < 0.0001 &&
          Math.abs(point.lng - lng) < 0.0001
      );

      if (!isDuplicate) {
        const type = newMiniGridNodes.length === 0 ? 'source' : 'terminal';
        const name =
          newMiniGridNodes.length === 0
            ? 'Source 01'
            : `Terminal ${String(newMiniGridNodes.length).padStart(2, '0')}`;

        const index = newMiniGridNodes.length;

        newMiniGridNodes.push({ index, name, lat, lng, type });
      }
      attempts++;
    }

    if (newMiniGridNodes.length < count) {
      throw new Error(`Could not generate ${count} unique markers.`);
    }

    const newOriginalDataPoints = newMiniGridNodes;

    const newState = {
      miniGridNodes: newMiniGridNodes,
      miniGridEdges: [],
      costBreakdown: {
        lowVoltageMeters: 0,
        highVoltageMeters: 0,
        totalMeters: 0,
        lowWireCost: 0,
        highWireCost: 0,
        wireCost: 0,
        poleCount: 0,
        poleCost: 0,
        pointCount: 0,
        grandTotal: 0,
      },
      solverOriginalCost: 0,
    };

    // Now update the UI
    setOriginalMiniGridNodes(newOriginalDataPoints);
    setMiniGridNodes(newMiniGridNodes);
    setMiniGridEdges([]);
    setCostBreakdown(newState.costBreakdown);
    setFileName(null);

    setExpandedSections({
      markers: false,
      solver: true,
      export: false,
      savedGrids: false,
    });
    setAllowDragTerminals(true);
    shouldAutoFit.current = true;

    // Save the CORRECT new state
    saveState(newState);
  };

  const handleResetMap = () => {
    // Clear map visuals
    markersRef.current.forEach((marker) => {
      marker.map = null;
    });
    markersRef.current = [];

    polylinesRef.current.forEach((line) => {
      line.setMap(null);
    });
    polylinesRef.current = [];

    // Reset state
    setSolverOriginalCost(0);
    setMiniGridNodes(originalMiniGridNodes);
    setMiniGridEdges([]);
    setCostBreakdown({
      lowVoltageMeters: 0,
      highVoltageMeters: 0,
      totalMeters: 0,
      lowWireCost: 0,
      highWireCost: 0,
      wireCost: 0,
      poleCount: 0,
      poleCost: 0,
      pointCount: 0,
      grandTotal: 0,
    });
    setCalcError(null);
    setError(null);
    setFileName(originalFileName);
    setComputingMiniGrid(false);

    shouldAutoFit.current = true;
  };

  const handleReconnectGraph = async () => {
    if (miniGridNodes.length < 2) {
      alert('Need at least 2 points to reconnect the graph.');
      return;
    }

    setComputingMiniGrid(true);
    setCalcError(null);

    const backendUrl =
      process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000/solve';

    try {
      const res = await fetch(backendUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          solver: 'SimpleMSTSolver',
          params: { steinerize: true },
          nodes: miniGridNodes,
          edges: [],
          voltageLevel: 'low',
          lengthConstraints: {
            low: {
              poleToPoleLengthConstraint: lowVoltagePoleToPoleLengthConstraint,
              poleToTerminalLengthConstraint:
                lowVoltagePoleToTerminalLengthConstraint,
            },
            high: {
              poleToPoleLengthConstraint: highVoltagePoleToPoleLengthConstraint,
              poleToTerminalLengthConstraint:
                highVoltagePoleToTerminalLengthConstraint,
            },
          },
          costs: {
            poleCost: poleCost || 0,
            lowVoltageCostPerMeter: lowVoltageCost || 0,
            highVoltageCostPerMeter: highVoltageCost || 0,
          },
          debug: 0,
          usePoles: true,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Reconnect failed');
      }

      const data = await res.json();

      // Same parsing logic as handleRunSolver
      const newMiniGridNodes = data.nodes || [];
      const newMiniGridEdges = (data.edges || []).map((e: MiniGridEdge) => ({
        start: e.start as MiniGridNode,
        end: e.end as MiniGridNode,
        lengthMeters: e.lengthMeters ?? 0,
        voltage: e.voltage ?? 'low',
      }));

      const newCostBreakdown = {
        lowVoltageMeters: data.totalLowVoltageMeters || 0,
        highVoltageMeters: data.totalHighVoltageMeters || 0,
        totalMeters:
          (data.totalLowVoltageMeters || 0) +
          (data.totalHighVoltageMeters || 0),
        lowWireCost: data.lowWireCostEstimate || 0,
        highWireCost: data.highWireCostEstimate || 0,
        wireCost: data.totalWireCostEstimate || 0,
        poleCount: data.numPolesUsed || 0,
        poleCost: data.poleCostEstimate || 0,
        pointCount: newMiniGridNodes.length,
        grandTotal: data.totalCostEstimate || 0,
      };

      setMiniGridNodes(newMiniGridNodes);
      setMiniGridEdges(newMiniGridEdges);
      setCostBreakdown(newCostBreakdown);
      // Save to history
      saveState({
        miniGridNodes: newMiniGridNodes,
        miniGridEdges: newMiniGridEdges,
        costBreakdown: newCostBreakdown,
        solverOriginalCost: solverOriginalCost,
      });
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Reconnect graph failed';
      setCalcError(message);
      console.error('Reconnect error:', err);
      alert(message);
    } finally {
      setComputingMiniGrid(false);
    }
  };

  const handleLocalOptimization = async () => {
    if (miniGridNodes.length < 2) {
      alert('Need at least 2 points to run local optimization.');
      return;
    }

    setComputingMiniGrid(true);
    setCalcError(null);

    const backendUrl =
      process.env.NEXT_PUBLIC_BACKEND_LOCAL_OPT_URL ||
      'http://localhost:8000/local_optimization';

    try {
      const res = await fetch(backendUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          solver: 'SimpleMSTSolver', // or whatever base you want
          params: paramValues,
          nodes: miniGridNodes,
          edges: miniGridEdges,
          voltageLevel: 'low',
          lengthConstraints: {
            low: {
              poleToPoleLengthConstraint: lowVoltagePoleToPoleLengthConstraint,
              poleToTerminalLengthConstraint:
                lowVoltagePoleToTerminalLengthConstraint,
              poleToTerminalMinimumLength:
                lowVoltagePoleToTerminalMinimumLength,
            },
            high: {
              poleToPoleLengthConstraint: highVoltagePoleToPoleLengthConstraint,
              poleToTerminalLengthConstraint:
                highVoltagePoleToTerminalLengthConstraint,
              poleToTerminalMinimumLength:
                highVoltagePoleToTerminalMinimumLength,
            },
          },
          costs: {
            poleCost: poleCost || 0,
            lowVoltageCostPerMeter: lowVoltageCost || 0,
            highVoltageCostPerMeter: highVoltageCost || 0,
          },
          debug: 0,
          usePoles: true,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Local optimization failed');
      }

      const data = await res.json();

      // Update state with optimized result
      const newMiniGridNodes = data.nodes || [];
      const newMiniGridEdges = (data.edges || []).map((e: any) => ({
        start: e.start as MiniGridNode,
        end: e.end as MiniGridNode,
        lengthMeters: e.lengthMeters ?? 0,
        voltage: e.voltage ?? 'low',
      }));

      const newCostBreakdown = {
        lowVoltageMeters: data.totalLowVoltageMeters || 0,
        highVoltageMeters: data.totalHighVoltageMeters || 0,
        totalMeters:
          (data.totalLowVoltageMeters || 0) +
          (data.totalHighVoltageMeters || 0),
        lowWireCost: data.lowWireCostEstimate || 0,
        highWireCost: data.highWireCostEstimate || 0,
        wireCost: data.totalWireCostEstimate || 0,
        poleCount: data.numPolesUsed || 0,
        poleCost: data.poleCostEstimate || 0,
        pointCount: newMiniGridNodes.length,
        grandTotal: data.totalCostEstimate || 0,
      };

      setMiniGridNodes(newMiniGridNodes);
      setMiniGridEdges(newMiniGridEdges);
      setCostBreakdown(newCostBreakdown);

      // Save to history
      saveState({
        miniGridNodes: newMiniGridNodes,
        miniGridEdges: newMiniGridEdges,
        costBreakdown: newCostBreakdown,
        solverOriginalCost: captureState().solverOriginalCost, // keep original cost for comparison
      });
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Local optimization failed';
      setCalcError(message);
      console.error('Local optimization error:', err);
      alert(message);
    } finally {
      setComputingMiniGrid(false);
    }
  };

  const handleRunSolver = async () => {
    console.log(
      `[handleRunSolver] Sending ${miniGridNodes.length} points to backend`
    );
    console.log(
      `[handleRunSolver] Using existing poles? ${useExistingPoles && hasPoles ? 'YES' : 'NO'} (${miniGridNodes.filter((p) => p.type === 'pole').length} poles)`
    );

    if (miniGridNodes.length < 2) {
      alert('Need at least 2 points to run solver.');
      return;
    }

    setComputingMiniGrid(true);
    setSolverOriginalCost(0);
    setMiniGridEdges([]);
    setCostBreakdown({
      lowVoltageMeters: 0,
      highVoltageMeters: 0,
      totalMeters: 0,
      lowWireCost: 0,
      highWireCost: 0,
      wireCost: 0,
      poleCount: 0,
      poleCost: 0,
      pointCount: 0,
      grandTotal: 0,
    }); // ← clear previous breakdown
    setCalcError(null);

    const backendUrl =
      process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000/solve';

    const startTime = performance.now();
    const debug = 0;

    // console.log("nodes", miniGridNodes);
    // console.log("edges", miniGridEdges);

    try {
      const res = await fetch(backendUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          solver: selectedSolverName,
          params: paramValues,
          nodes: miniGridNodes,
          edges: [], // always send edges as empty for the main solve (only use nodes); the backend will decide how to use existing poles if applicable
          voltageLevel: 'low',
          lengthConstraints: {
            low: {
              poleToPoleLengthConstraint: lowVoltagePoleToPoleLengthConstraint,
              poleToTerminalLengthConstraint:
                lowVoltagePoleToTerminalLengthConstraint,
            },
            high: {
              poleToPoleLengthConstraint: highVoltagePoleToPoleLengthConstraint,
              poleToTerminalLengthConstraint:
                highVoltagePoleToTerminalLengthConstraint,
            },
          },
          costs: {
            poleCost: poleCost || 0,
            lowVoltageCostPerMeter: lowVoltageCost || 0,
            highVoltageCostPerMeter: highVoltageCost || 0,
          },
          debug: debug,
          usePoles: useExistingPoles,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || errData.error || 'Solve failed');
      }

      const endTime = performance.now();
      const durationMs = endTime - startTime;
      const durationSec = (durationMs / 1000).toFixed(2);

      console.log(
        `%c[API Request] Solve took ${durationMs.toFixed(0)} ms (${durationSec} sec)`,
        'background: #1e293b; color: #60a5fa; padding: 4px 8px; border-radius: 4px;'
      );

      const data = await res.json();

      if (debug) {
        console.log('Solver result:', data);
      }

      if (data.error) throw new Error(data.error);

      // Use pre-computed values from backend
      const {
        totalLowVoltageMeters = 0,
        totalHighVoltageMeters = 0,
        numPolesUsed = 0,
        poleCostEstimate = 0,
        lowWireCostEstimate = 0,
        highWireCostEstimate = 0,
        totalWireCostEstimate = 0,
        totalCostEstimate = 0,
        pointCount = 0,
        usedCosts, // optional – for display/debug
      } = data;

      // ─────────────────────────────────────────────────────────────
      //  BUILD THE NEW STATE SNAPSHOT FIRST (before any setState)
      // ─────────────────────────────────────────────────────────────
      const newMiniGridNodes = data.nodes || [];
      const newMiniGridEdges = (data.edges || []).map((e: MiniGridEdge) => ({
        start: e.start as MiniGridNode,
        end: e.end as MiniGridNode,
        lengthMeters: e.lengthMeters ?? 0,
        voltage: e.voltage ?? 'low',
      }));

      const newCostBreakdown = {
        lowVoltageMeters: totalLowVoltageMeters,
        highVoltageMeters: totalHighVoltageMeters,
        totalMeters: totalLowVoltageMeters + totalHighVoltageMeters,
        lowWireCost: lowWireCostEstimate,
        highWireCost: highWireCostEstimate,
        wireCost: totalWireCostEstimate,
        poleCount: numPolesUsed,
        poleCost: poleCostEstimate,
        pointCount: pointCount,
        grandTotal: totalCostEstimate,
        usedPoleCost: usedCosts?.poleCost,
        usedLowCostPerMeter: usedCosts?.lowVoltageCostPerMeter,
        usedHighCostPerMeter: usedCosts?.highVoltageCostPerMeter,
      };

      // Now update React state
      setMiniGridNodes(newMiniGridNodes);
      setMiniGridEdges(newMiniGridEdges);
      setCostBreakdown(newCostBreakdown);
      setSolverOriginalCost(totalCostEstimate);

      // Save the CORRECT solved state to history
      saveState({
        miniGridNodes: newMiniGridNodes,
        miniGridEdges: newMiniGridEdges,
        costBreakdown: newCostBreakdown,
        solverOriginalCost: totalCostEstimate,
      });

      shouldAutoFit.current = true;
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to run solver';
      setCalcError(message);
      console.error('Solver error:', err);
    } finally {
      setComputingMiniGrid(false);
    }
    setAllowDragTerminals(false);
    setExpandedSections({
      markers: false,
      solver: false,
      export: true,
      savedGrids: false,
    });
  };

  const generateRandomCosts = () => {
    // Generate realistic cost ranges for mini-grid components
    const poleCost = Math.round((100 + Math.random() * 200) * 100) / 100; // $100-300
    const lowVoltageCost = Math.round((1.5 + Math.random() * 3) * 100) / 100; // $1.50-4.50/m
    const highVoltageCost = Math.round((3 + Math.random() * 4) * 100) / 100; // $3-7/m

    setPoleCost(poleCost);
    setLowVoltageCost(lowVoltageCost);
    setHighVoltageCost(highVoltageCost);
  };

  const downloadKml = () => {
    const escapeXml = (str: string) =>
      str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&apos;');

    const formatCost = (v: number) =>
      v.toLocaleString(undefined, {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      });

    const kmlStyles = `
    <Style id="source">
      <IconStyle><color>ff00cc00</color><scale>1.5</scale></IconStyle>
      <LabelStyle><color>ff00ff00</color><scale>1.1</scale></LabelStyle>
    </Style>
    <Style id="terminal">
      <IconStyle><color>ff3366ff</color><scale>1.3</scale></IconStyle>
      <LabelStyle><scale>1.0</scale></LabelStyle>
    </Style>
    <Style id="pole">
      <IconStyle><color>ffffff66</color><scale>1.1</scale></IconStyle>
      <LabelStyle><color>ffffffff</color><scale>0.85</scale></LabelStyle>
    </Style>
    <Style id="lowVoltage">
      <LineStyle><color>aa3b82f6</color><width>5</width></LineStyle>
    </Style>
    <Style id="highVoltage">
      <LineStyle><color>aa8b5cf6</color><width>7</width></LineStyle>
    </Style>
    <Style id="summary">
      <BalloonStyle>
        <text><![CDATA[<h3>$[name]</h3><p>$[description]</p>]]></text>
      </BalloonStyle>
    </Style>
  `;

    // Nodes
    let nodesKml = '';
    miniGridNodes.forEach((node) => {
      const styleId =
        node.type === 'source'
          ? 'source'
          : node.type === 'terminal'
            ? 'terminal'
            : 'pole';
      const displayName =
        node.type === 'pole'
          ? `Pole ${String(node.index).padStart(3, '0')}`
          : escapeXml(node.name);

      nodesKml += `
      <Placemark>
        <name>${displayName}</name>
        <styleUrl>#${styleId}</styleUrl>
        <description><![CDATA[
          <b>${escapeXml(node.name)}</b><br/>
          Type: ${node.type}<br/>
          Index: ${node.index}<br/>
          Lat,Lng: ${node.lat.toFixed(7)}, ${node.lng.toFixed(7)}
        ]]></description>
        <Point>
          <coordinates>${node.lng.toFixed(8)},${node.lat.toFixed(8)},0</coordinates>
        </Point>
      </Placemark>`;
    });

    // Edges
    let linesKml = '';
    miniGridEdges.forEach((edge, i) => {
      const styleId = edge.voltage === 'high' ? 'highVoltage' : 'lowVoltage';
      const lengthM = Math.round(edge.lengthMeters);
      const costPerM =
        edge.voltage === 'high' ? highVoltageCost : lowVoltageCost;
      const edgeCost = Math.round(lengthM * costPerM);

      linesKml += `
      <Placemark>
        <name>Line ${i + 1} (${edge.voltage})</name>
        <styleUrl>#${styleId}</styleUrl>
        <description><![CDATA[
          <b>Segment ${i + 1}</b><br/>
          Voltage: ${edge.voltage}<br/>
          Length: ${lengthM.toLocaleString()} m<br/>
          Est. cost: ${formatCost(edgeCost)}
        ]]></description>
        <LineString>
          <tessellate>1</tessellate>
          <coordinates>
            ${edge.start.lng.toFixed(8)},${edge.start.lat.toFixed(8)},0
            ${edge.end.lng.toFixed(8)},${edge.end.lat.toFixed(8)},0
          </coordinates>
        </LineString>
      </Placemark>`;
    });

    // Summary
    const summaryDescription = costBreakdown
      ? `
    <b>Grand Total:</b> ${formatCost(costBreakdown.grandTotal)}<br/>
    <b>Wire:</b> ${formatCost(costBreakdown.wireCost)}<br/>
      • Low: ${formatMeters(costBreakdown.lowVoltageMeters)} m → ${formatCost(costBreakdown.lowWireCost)}<br/>
      • High: ${formatMeters(costBreakdown.highVoltageMeters)} m → ${formatCost(costBreakdown.highWireCost)}<br/>
    <b>Poles:</b> ${costBreakdown.poleCount} × ${formatCost(costBreakdown.usedPoleCost ?? poleCost)}<br/>
    <br/>Nodes: ${miniGridNodes.length} • Segments: ${miniGridEdges.length}
  `
      : 'No cost data available';

    let summaryLat = 0;
    let summaryLng = 0;

    // Find the source node
    const sourceNode = miniGridNodes.find((node) => node.type === 'source');
    if (sourceNode) {
      summaryLat = sourceNode.lat;
      summaryLng = sourceNode.lng;
    } else {
      // Fallback: use the first node if no explicit source (rare)
      if (miniGridNodes.length > 0) {
        summaryLat = miniGridNodes[0].lat;
        summaryLng = miniGridNodes[0].lng;
      }
      console.warn(
        'No source node found — using first node for summary position'
      );
    }

    const offsetMeters = 3; // ~15 meters north-east
    const offsetLat = summaryLat + offsetMeters / 111111; // rough 1° lat ≈ 111 km
    const offsetLng =
      summaryLng +
      offsetMeters / (111111 * Math.cos((summaryLat * Math.PI) / 180));

    const summaryPlacemark = `
    <Placemark>
      <name>Mini-Grid Cost Summary</name>
      <styleUrl>#summary</styleUrl>
      <description><![CDATA[${summaryDescription}]]></description>
      <coordinates>${offsetLng.toFixed(8)},${offsetLat.toFixed(8)},0</coordinates>;
    </Placemark>
  `;

    // Assemble final KML
    const kml = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Mini-Grid • ${miniGridEdges.length > 0 ? 'Solved' : ''}</name>
    <open>1</open>

    ${kmlStyles}

    <Folder>
      <name>Nodes and Poles</name>
      <open>1</open>
      ${nodesKml}
    </Folder>

    <Folder>
      <name>Power Lines</name>
      <open>1</open>
      ${linesKml}
    </Folder>

    <Folder>
      <name>Summary</name>
      ${summaryPlacemark}
    </Folder>

  </Document>
</kml>`;

    // Download
    const blob = new Blob([kml], {
      type: 'application/vnd.google-earth.kml+xml',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `minigrid_${new Date().toISOString().slice(0, 10)}.kml`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const loadSavedRun = (run: MiniGridRun) => {
    console.log('Loading saved mini-grid:', run.id, run.name || '(no name)');

    // Log what we actually received (for debugging)
    console.log('Saved solver:', {
      poleCost: run.poleCost,
      lowVoltageCost: run.lowVoltageCost,
      highVoltageCost: run.highVoltageCost,
    });

    // Reset and load core data
    setMiniGridNodes(run.miniGridNodes || []);
    setMiniGridEdges(
      (run.miniGridEdges || []).map((e: MiniGridEdge) => ({
        start: e.start, // already a full node after type change
        end: e.end,
        lengthMeters: Number(e.lengthMeters) || 0,
        voltage: e.voltage || 'low',
      }))
    );

    setPoleCost(Number(run.poleCost) || 100);
    setLowVoltageCost(Number(run.lowVoltageCost) || 10);
    setHighVoltageCost(Number(run.highVoltageCost) || 20);

    // Load cost breakdown if it exists
    setCostBreakdown(run.costBreakdown);

    setSolverOriginalCost(run.costBreakdown?.grandTotal || 0);

    // Restore file name / metadata
    setFileName(run.fileName || null);

    setExpandedSections({
      markers: false,
      solver: false,
      export: true,
      savedGrids: false,
    });

    shouldAutoFit.current = true;

    const newState = {
      miniGridNodes: run.miniGridNodes || [],
      miniGridEdges: run.miniGridEdges || [],
      costBreakdown: run.costBreakdown,
      solverOriginalCost: run.costBreakdown?.grandTotal || 0,
    };

    // 1. Update React State
    setMiniGridNodes(newState.miniGridNodes);
    setMiniGridEdges(newState.miniGridEdges);
    setCostBreakdown(newState.costBreakdown);
    setSolverOriginalCost(run.costBreakdown?.grandTotal || 0);

    // 2. IMPORTANT: If your useMiniGridHistory hook has a 'reset' or 'clear' method,
    // use it here. Otherwise, pushing a new state via saveState()
    // will ALWAYS clear the Redo stack by design.
    saveState(newState);

    alert(`Loaded: ${run.name || 'Mini-grid run'}`);
  };

  const handleDeleteRun = async (runId: string, runName?: string) => {
    if (
      !confirm(
        `Are you sure you want to delete "${runName || 'this mini-grid'}"?`
      )
    ) {
      return;
    }

    try {
      const res = await fetch(`/api/minigrids/${runId}`, {
        method: 'DELETE',
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || 'Failed to delete');
      }

      // Remove from local state (optimistic update)
      setSavedRuns((prev) => prev.filter((r) => r.id !== runId));

      alert('Mini-grid deleted successfully');
    } catch (err) {
      console.error('Delete error:', err);
      alert(
        'Failed to delete mini-grid: ' +
          (err instanceof Error ? err.message : 'Unknown error')
      );
    }
  };

  const handleSaveToDatabase = async () => {
    if (!session?.user?.id) {
      alert('Please sign in to save your mini-grid.');
      return;
    }

    if (miniGridNodes.length === 0) {
      alert('No solver results to save yet.');
      return;
    }

    // Quick client-side check (optimistic)
    if (savedRuns.length >= 10) {
      alert(
        'You have reached the maximum of 10 saved mini-grids.\n\n' +
          'Please delete one of your existing runs before saving a new one.'
      );
      return;
    }

    const name =
      prompt('Name for this mini-grid run (optional):') ||
      `MiniGrid ${new Date().toLocaleDateString()}`;

    const payload = {
      name,
      fileName: fileName || null,
      miniGridNodes,
      miniGridEdges,
      costBreakdown,
      poleCost,
      lowVoltageCost,
      highVoltageCost,
    };

    try {
      const res = await fetch('/api/minigrids', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || 'Failed to save mini-grid');
      }

      setExpandedSections({
        markers: false,
        solver: false,
        export: false,
        savedGrids: true,
      });

      alert('Mini-grid saved successfully!');

      // ────────────────────────────────────────────────
      // Automatically refresh the saved runs list
      // ────────────────────────────────────────────────
      const refreshRes = await fetch('/api/minigrids');
      if (refreshRes.ok) {
        const updatedRuns = await refreshRes.json();
        setSavedRuns(updatedRuns);
        console.log('Saved runs refreshed:', updatedRuns.length, 'items');
      } else {
        console.warn(
          'Could not refresh saved runs after save',
          refreshRes.status
        );
      }
    } catch (err) {
      console.error('Save error:', err);
      alert(
        'Failed to save mini-grid: ' +
          (err instanceof Error ? err.message : 'Unknown error')
      );
    }
  };

  // For space, I'll note: Paste all remaining functions from your original file here
  // (handleAddManualPoint, handleDragOver, handleDrop, handleResetMap, generateRandomCosts, etc.)

  // ==================== RENDER ====================
  return (
    <div className='fixed inset-0 z-50 overflow-hidden bg-white text-zinc-900 dark:bg-zinc-950 dark:text-white'>
      {/* 1. Sidebar Toggle Button (Hamburger) */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className='fixed top-4 left-4 z-50 flex h-11 w-11 items-center justify-center rounded-full bg-emerald-600 text-white shadow-2xl transition-all hover:scale-110 hover:bg-emerald-500 active:scale-95'
        aria-label='Toggle Sidebar'
      >
        {sidebarOpen ? (
          // Close (X) icon
          <svg
            className='h-6 w-6'
            fill='none'
            stroke='currentColor'
            viewBox='0 0 24 24'
            strokeWidth={2.5}
          >
            <path strokeLinecap='round' strokeLinejoin='round' d='M6 18L18 6' />
          </svg>
        ) : (
          // Hamburger icon
          <svg
            className='h-6 w-6'
            fill='none'
            stroke='currentColor'
            viewBox='0 0 24 24'
            strokeWidth={2.5}
          >
            <path
              strokeLinecap='round'
              strokeLinejoin='round'
              d='M4 6h16M4 12h16M4 18h16'
            />
          </svg>
        )}
      </button>

      {/* MAIN CONTAINER - Full Screen Map */}
      <div className='relative h-full overflow-hidden pt-16'>
        {/* FULL-BLEED MAP - Now fills the entire screen */}
        <div
          ref={mapRef}
          className='absolute inset-0 bg-zinc-50 dark:bg-zinc-950'
        />

        {/* Sidebar Drawer - Extended to Top with Sign In Button */}
        <div
          className={`md:w-autoborder-r fixed top-0 left-0 z-40 h-full w-full max-w-[100vw] border-zinc-200 bg-white text-zinc-900 shadow-2xl transition-transform duration-300 ease-in-out md:max-w-none dark:border-zinc-700 dark:bg-zinc-950 dark:text-white ${
            sidebarOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
          style={{ width: `${sidebarWidth}px` }}
        >
          {/* Resize Handle */}
          <div
            className='absolute top-0 right-0 bottom-0 z-50 w-1.5 cursor-col-resize bg-zinc-300 transition-colors hover:bg-purple-500 active:bg-purple-600 dark:bg-zinc-700'
            onMouseDown={handleMouseDown}
          />

          {/* Header Bar - Contains Hamburger (outside) + Sign In Button */}
          <div className='flex h-20 items-center justify-between border-b border-zinc-200 bg-white px-6 dark:border-zinc-700 dark:bg-zinc-950'>
            <div className='text-lg font-semibold text-emerald-700 dark:text-emerald-300'></div>

            {/* User Menu */}
            <div className='flex-shrink-0'>
              <SidebarUserMenu />
            </div>
          </div>

          {/* Scrollable Content */}
          <div className='h-[calc(100%-4rem)] overflow-y-auto p-6'>
            <div className='space-y-12'>
              {/* 1. Define Marker Section */}
              <DefineMarkersSection
                isExpanded={expandedSections.markers}
                onToggle={() => toggleSection('markers')}
                map={map}
                // TestDataGenerator
                selectedCount={selectedCount}
                onCountChange={setSelectedCount}
                onGenerate={handleGenerateTestData}
                loading={loading}
                error={error}
                // FileUploadArea
                isDragOver={isDragOver}
                fileName={fileName}
                dataPointsLength={miniGridNodes.length}
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragOver(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  setIsDragOver(false);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragOver(false);
                  const files = e.dataTransfer.files;
                  if (files.length === 0) return;
                  const file = files[0];
                  const name = file.name.toLowerCase();
                  if (
                    file.type === 'text/csv' ||
                    name.endsWith('.csv') ||
                    name.endsWith('.kml') ||
                    file.type === 'application/vnd.google-earth.kml+xml'
                  ) {
                    processFile(file);
                    setExpandedSections({
                      markers: false,
                      solver: true,
                      export: false,
                      savedGrids: false,
                    });
                  } else {
                    setError('Please drop a CSV or KML file.');
                  }
                }}
                onFileSelect={handleFileUpload}
                // MapSearchBar
                onPlaceSelected={(lat, lng, name) => {
                  setPendingPoint({ lat, lng });
                  setNewPointDetails({
                    name: name,
                    type: 'terminal' as const,
                  });
                  setIsAddPointDialogOpen(true);
                }}
                // ManualPointInput
                manualPoint={manualPoint}
                onManualPointChange={setManualPoint}
                onAddManualPoint={handleAddCoordinatesManually}
              />

              {/* 2. Costs & Solver Section - (your existing code) */}
              {/* ==================== COSTS & SOLVER SECTION ==================== */}
              {/* 2. Costs Section */}
              <CostsSection
                isExpanded={expandedSections.costs}
                onToggle={() => toggleSection('costs')}
                poleCost={poleCost}
                lowVoltageCost={lowVoltageCost}
                highVoltageCost={highVoltageCost}
                onPoleCostChange={setPoleCost}
                onLowVoltageCostChange={setLowVoltageCost}
                onHighVoltageCostChange={setHighVoltageCost}
                onRandomCosts={generateRandomCosts}
                lowVoltagePoleToPoleLengthConstraint={
                  lowVoltagePoleToPoleLengthConstraint
                }
                lowVoltagePoleToTerminalLengthConstraint={
                  lowVoltagePoleToTerminalLengthConstraint
                }
                lowVoltagePoleToTerminalMinimumLength={
                  lowVoltagePoleToTerminalMinimumLength
                }
                highVoltagePoleToPoleLengthConstraint={
                  highVoltagePoleToPoleLengthConstraint
                }
                highVoltagePoleToTerminalLengthConstraint={
                  highVoltagePoleToTerminalLengthConstraint
                }
                highVoltagePoleToTerminalMinimumLength={
                  highVoltagePoleToTerminalMinimumLength
                }
                onLowVoltagePoleToPoleChange={
                  setLowVoltagePoleToPoleLengthConstraint
                }
                onLowVoltagePoleToTerminalChange={
                  setLowVoltagePoleToTerminalLengthConstraint
                }
                onLowVoltagePoleToTerminalMinimumChange={
                  setLowVoltagePoleToTerminalMinimumLength
                }
                onHighVoltagePoleToPoleChange={
                  setHighVoltagePoleToPoleLengthConstraint
                }
                onHighVoltagePoleToTerminalChange={
                  setHighVoltagePoleToTerminalLengthConstraint
                }
                onHighVoltagePoleToTerminalMinimumChange={
                  setHighVoltagePoleToTerminalMinimumLength
                }
              />

              {/* 3. Solver Section */}
              <SolverSection
                isExpanded={expandedSections.solver}
                onToggle={() => toggleSection('solver')}
                solvers={solvers}
                selectedSolverName={selectedSolverName}
                onSolverChange={setSelectedSolverName}
                paramValues={paramValues}
                onParamChange={updateParam}
                useExistingPoles={useExistingPoles}
                onUseExistingPolesChange={setUseExistingPoles}
                poleCount={
                  miniGridNodes.filter((n) => n.type === 'pole').length
                }
                onRunSolver={handleRunSolver}
                computing={computingMiniGrid}
                calcError={calcError}
                miniGridNodes={miniGridNodes}
              />

              {/* 3. Export & Summary Section */}
              <ExportAndSummarySection
                isExpanded={expandedSections.export}
                onToggle={() => toggleSection('export')}
                // ExportSummary props
                costBreakdown={costBreakdown}
                solverOriginalCost={solverOriginalCost}
                poleCost={poleCost}
                lowVoltageCost={lowVoltageCost}
                highVoltageCost={highVoltageCost}
                miniGridNodes={miniGridNodes}
                allowDragTerminals={allowDragTerminals}
                onAllowDragTerminalsChange={setAllowDragTerminals}
                showEdgeLengths={showEdgeLengths}
                onShowEdgeLengthsChange={setShowEdgeLengths}
                onDownloadKml={downloadKml}
                onSaveToDatabase={handleSaveToDatabase}
                isAuthenticated={!!session?.user}
                savedRunsCount={savedRuns.length}
                computingMiniGrid={computingMiniGrid}
              />

              {/* 4. Saved Mini-grids Section */}
              <SavedGridsSection
                savedRuns={savedRuns}
                loadingSaved={loadingSaved}
                expanded={expandedSections.savedGrids}
                onToggle={() => toggleSection('savedGrids')}
                onLoadRun={loadSavedRun}
                onDeleteRun={handleDeleteRun}
              />
            </div>
            <br />
            <hr className='border-zinc-200 dark:border-zinc-700' />
            <br />
            <p className='text-center text-xs text-zinc-500 dark:text-zinc-400'>
              <a
                href={
                  'https://drive.google.com/file/d/1m5vtUijPxrbMqG0B-hNIa4mG5RXADIH5/view?usp=sharing'
                }
                target='_blank'
              >
                User Manual |
              </a>
              <a href={'https://forms.gle/Az6j5cjtzJJDEQAEA'} target='_blank'>
                {' '}
                Give Feedback{' '}
              </a>
            </p>
          </div>
        </div>

        {/* Floating Action Buttons - Map Controls */}
        <MapControls
          canUndo={canUndo}
          canRedo={canRedo}
          onUndo={() => {
            const s = undo();
            if (s) {
              setMiniGridNodes(s.miniGridNodes);
              setMiniGridEdges(s.miniGridEdges);
              setCostBreakdown(s.costBreakdown);
            }
          }}
          onRedo={() => {
            const s = redo();
            if (s) {
              setMiniGridNodes(s.miniGridNodes);
              setMiniGridEdges(s.miniGridEdges);
              setCostBreakdown(s.costBreakdown);
            }
          }}
          onLocalOptimize={handleLocalOptimization}
          onReconnectGraph={handleReconnectGraph}
          onReset={handleResetMap}
          hasData={miniGridNodes.length > 0}
          isOptimizing={computingMiniGrid}
        />

        {/* FOOTER - Minimal */}
        <footer className='border-t border-zinc-200 bg-white py-4 text-center text-xs text-zinc-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-400'>
          © 2026 • CS 6150 Computing For Good • Mini-Grid Solver Tool
        </footer>

        <Script
          src={`https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_API_KEY}&libraries=marker,places`}
          strategy='afterInteractive'
          onLoad={initMap}
        />
      </div>
      {/* Dialog for adding a point via map click */}
      <AddPointDialog
        isOpen={isAddPointDialogOpen}
        onOpenChange={setIsAddPointDialogOpen}
        newPointDetails={newPointDetails}
        onNewPointDetailsChange={setNewPointDetails}
        onConfirm={handleConfirmNewPoint}
      />
    </div>
  );
}
