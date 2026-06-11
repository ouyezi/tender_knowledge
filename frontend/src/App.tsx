import { Route, Routes } from "react-router-dom";
import AppShell from "./layout/AppShell";
import ChapterTaxonomyCenterPage from "./pages/ChapterTaxonomyCenter";
import KnowledgeBaseListPage from "./pages/KnowledgeBaseList";
import ProductCategoryCenterPage from "./pages/ProductCategoryCenter";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<KnowledgeBaseListPage />} />
        <Route path="/product-categories" element={<ProductCategoryCenterPage />} />
        <Route path="/chapter-taxonomies" element={<ChapterTaxonomyCenterPage />} />
      </Route>
    </Routes>
  );
}
