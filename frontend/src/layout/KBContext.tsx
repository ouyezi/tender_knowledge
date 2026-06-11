import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  getKnowledgeBase,
  listKnowledgeBases,
  type KnowledgeBase,
} from "../services/kbApi";

const KB_STORAGE_KEY = "tender_kb_id";

interface KBContextValue {
  activeKbs: KnowledgeBase[];
  selectedKbId?: string;
  selectedKb?: KnowledgeBase;
  readOnly: boolean;
  loading: boolean;
  setSelectedKbId: (id: string) => void;
  refreshActiveKbs: () => Promise<void>;
}

const KBContext = createContext<KBContextValue | undefined>(undefined);

export function KBProvider({ children }: { children: React.ReactNode }) {
  const [activeKbs, setActiveKbs] = useState<KnowledgeBase[]>([]);
  const [selectedKbId, setSelectedKbIdState] = useState<string | undefined>();
  const [selectedKb, setSelectedKb] = useState<KnowledgeBase | undefined>();
  const [loading, setLoading] = useState(true);

  const setSelectedKbId = useCallback((id: string) => {
    setSelectedKbIdState(id);
    localStorage.setItem(KB_STORAGE_KEY, id);
  }, []);

  const refreshActiveKbs = useCallback(async () => {
    const list = await listKnowledgeBases("active");
    setActiveKbs(list);
    if (selectedKbId) {
      const latestSelected = await getKnowledgeBase(selectedKbId);
      setSelectedKb(latestSelected);
    }
  }, [selectedKbId]);

  useEffect(() => {
    const bootstrap = async () => {
      setLoading(true);
      try {
        const activeList = await listKnowledgeBases("active");
        setActiveKbs(activeList);

        const storedKbId = localStorage.getItem(KB_STORAGE_KEY) ?? undefined;
        const defaultKbId = storedKbId ?? activeList[0]?.id;
        if (defaultKbId) {
          setSelectedKbIdState(defaultKbId);
          if (!storedKbId) {
            localStorage.setItem(KB_STORAGE_KEY, defaultKbId);
          }
        }
      } finally {
        setLoading(false);
      }
    };
    void bootstrap();
  }, []);

  useEffect(() => {
    const loadSelectedKb = async () => {
      if (!selectedKbId) {
        setSelectedKb(undefined);
        return;
      }
      const kb = await getKnowledgeBase(selectedKbId);
      setSelectedKb(kb);
    };

    void loadSelectedKb();
  }, [selectedKbId]);

  const value = useMemo<KBContextValue>(
    () => ({
      activeKbs,
      selectedKbId,
      selectedKb,
      readOnly: selectedKb?.status === "inactive",
      loading,
      setSelectedKbId,
      refreshActiveKbs,
    }),
    [activeKbs, loading, refreshActiveKbs, selectedKb, selectedKbId, setSelectedKbId],
  );

  return <KBContext.Provider value={value}>{children}</KBContext.Provider>;
}

export function useKBContext() {
  const context = useContext(KBContext);
  if (!context) {
    throw new Error("useKBContext must be used within KBProvider");
  }
  return context;
}
