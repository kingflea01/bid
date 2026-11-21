import { create } from 'zustand';

export type InspectorTab = 'candidates' | 'requirements' | 'issues' | 'activity';

interface WorkspaceState {
  activeSectionId?: string;
  inspectorTab: InspectorTab;
  treeSearch: string;
  statusFilter: string;
  collapsedTree: Record<string, boolean>;
  collapsedCards: Record<string, boolean>;
  impactedSectionIds: string[];
  treeOpen: boolean;
  inspectorOpen: boolean;
  setActiveSection: (id: string) => void;
  setInspectorTab: (tab: InspectorTab) => void;
  setTreeSearch: (value: string) => void;
  setStatusFilter: (value: string) => void;
  toggleTree: (id: string) => void;
  toggleCard: (id: string) => void;
  expandAllCards: () => void;
  setImpactedSections: (ids: string[]) => void;
  clearImpactedSections: () => void;
  setTreeOpen: (open: boolean) => void;
  setInspectorOpen: (open: boolean) => void;
  reset: () => void;
}

const initialState = {
  activeSectionId: undefined,
  inspectorTab: 'candidates' as InspectorTab,
  treeSearch: '',
  statusFilter: 'all',
  collapsedTree: {},
  collapsedCards: {},
  impactedSectionIds: [],
  treeOpen: false,
  inspectorOpen: false,
};

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  ...initialState,
  setActiveSection: (id) =>
    set((state) => ({
      activeSectionId: id,
      collapsedCards: { ...state.collapsedCards, [id]: false },
    })),
  setInspectorTab: (inspectorTab) => set({ inspectorTab }),
  setTreeSearch: (treeSearch) => set({ treeSearch }),
  setStatusFilter: (statusFilter) => set({ statusFilter }),
  toggleTree: (id) =>
    set((state) => ({
      collapsedTree: { ...state.collapsedTree, [id]: !state.collapsedTree[id] },
    })),
  toggleCard: (id) =>
    set((state) => ({
      collapsedCards: { ...state.collapsedCards, [id]: !state.collapsedCards[id] },
    })),
  expandAllCards: () => set({ collapsedCards: {} }),
  setImpactedSections: (impactedSectionIds) => set({ impactedSectionIds }),
  clearImpactedSections: () => set({ impactedSectionIds: [] }),
  setTreeOpen: (treeOpen) => set({ treeOpen }),
  setInspectorOpen: (inspectorOpen) => set({ inspectorOpen }),
  reset: () => set(initialState),
}));
