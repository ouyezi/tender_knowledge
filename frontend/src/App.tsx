import { Route, Routes } from "react-router-dom";
import AppShell from "./layout/AppShell";
import ChapterTaxonomyCenterPage from "./pages/ChapterTaxonomyCenter";
import FileImportCenterPage from "./pages/FileImportCenter";
import KnowledgeBaseListPage from "./pages/KnowledgeBaseList";
import ProductCategoryCenterPage from "./pages/ProductCategoryCenter";
import ParseConfirmWizard from "./pages/TemplateLibraryCenter/ParseConfirmWizard";
import TemplateDetailPage from "./pages/TemplateLibraryCenter/TemplateDetailPage";
import CandidateCenterPage from "./pages/CandidateCenter";
import CandidateAuditPanel from "./pages/CandidateCenter/CandidateAuditPanel";
import CandidateConfirmPage from "./pages/CandidateCenter/CandidateConfirmPage";
import OutlineCenterPage from "./pages/OutlineCenter";
import ActualBidParseConfirmWizard from "./pages/OutlineCenter/ActualBidParseConfirmWizard";
import OutlineDetailPage from "./pages/OutlineCenter/OutlineDetailPage";
import RetrievalOptimizationCenterPage from "./pages/RetrievalOptimizationCenter";
import TemplateLibraryCenterPage from "./pages/TemplateLibraryCenter";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<KnowledgeBaseListPage />} />
        <Route path="/product-categories" element={<ProductCategoryCenterPage />} />
        <Route path="/chapter-taxonomies" element={<ChapterTaxonomyCenterPage />} />
        <Route path="/file-imports" element={<FileImportCenterPage />} />
        <Route path="/template-libraries" element={<TemplateLibraryCenterPage />} />
        <Route path="/outlines" element={<OutlineCenterPage />} />
        <Route
          path="/retrieval-optimization"
          element={<RetrievalOptimizationCenterPage />}
        />
        <Route path="/outlines/:bidOutlineId" element={<OutlineDetailPage />} />
        <Route
          path="/outlines/parse-confirm/:parseTaskId"
          element={<ActualBidParseConfirmWizard />}
        />
        <Route path="/candidates" element={<CandidateCenterPage />} />
        <Route path="/candidates/audit" element={<CandidateAuditPanel />} />
        <Route path="/candidates/confirm/:candidateId" element={<CandidateConfirmPage />} />
        <Route
          path="/template-libraries/parse-confirm/:parseTaskId"
          element={<ParseConfirmWizard />}
        />
        <Route
          path="/template-libraries/templates/:templateId"
          element={<TemplateDetailPage />}
        />
      </Route>
    </Routes>
  );
}
