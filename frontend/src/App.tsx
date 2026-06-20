import { Route, Routes } from "react-router-dom";
import AppShell from "./layout/AppShell";
import FileImportCenterPage from "./pages/FileImportCenter";
import KnowledgeBaseListPage from "./pages/KnowledgeBaseList";
import KnowledgeEntryPage from "./pages/KnowledgeV2/KnowledgeEntryPage";
import KnowledgeBrowsePage from "./pages/KnowledgeV2/KnowledgeBrowsePage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<KnowledgeBaseListPage />} />
        <Route path="/file-imports" element={<FileImportCenterPage />} />
        <Route path="/knowledge-v2/entry" element={<KnowledgeEntryPage />} />
        <Route path="/knowledge-v2/browse" element={<KnowledgeBrowsePage />} />
      </Route>
    </Routes>
  );
}
