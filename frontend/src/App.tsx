import { Route, Routes } from "react-router-dom";
import AppShell from "./layout/AppShell";
import FileImportCenterPage from "./pages/FileImportCenter";
import KnowledgeBaseListPage from "./pages/KnowledgeBaseList";
import BlueprintDetailPage from "./pages/Knowledge/BlueprintDetailPage";
import BlueprintListPage from "./pages/Knowledge/BlueprintListPage";
import KnowledgeEntryPage from "./pages/Knowledge/KnowledgeEntryPage";
import KnowledgeBrowsePage from "./pages/Knowledge/KnowledgeBrowsePage";
import WritingTechniqueDetailPage from "./pages/Knowledge/WritingTechniqueDetailPage";
import WritingTechniqueListPage from "./pages/Knowledge/WritingTechniqueListPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<KnowledgeBaseListPage />} />
        <Route path="/file-imports" element={<FileImportCenterPage />} />
        <Route path="/knowledge/entry" element={<KnowledgeEntryPage />} />
        <Route path="/knowledge/browse" element={<KnowledgeBrowsePage />} />
        <Route path="/knowledge/blueprints" element={<BlueprintListPage />} />
        <Route path="/knowledge/blueprints/:id" element={<BlueprintDetailPage />} />
        <Route path="/knowledge/writing-techniques" element={<WritingTechniqueListPage />} />
        <Route
          path="/knowledge/writing-techniques/:id"
          element={<WritingTechniqueDetailPage />}
        />
      </Route>
    </Routes>
  );
}
