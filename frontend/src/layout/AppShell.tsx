import { Alert, Layout, Menu, Select, Space, Typography } from "antd";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useMemo } from "react";
import { useKBContext } from "./KBContext";

const { Header, Content } = Layout;
const { Text } = Typography;

const NAV_ITEMS = [
  { key: "/", label: <Link to="/">知识库</Link> },
  { key: "/product-categories", label: <Link to="/product-categories">产品分类</Link> },
  { key: "/chapter-taxonomies", label: <Link to="/chapter-taxonomies">章节分类</Link> },
  { key: "/file-imports", label: <Link to="/file-imports">来源导入</Link> },
];

export default function AppShell() {
  const location = useLocation();
  const { activeKbs, selectedKbId, selectedKb, setSelectedKbId, readOnly, loading } =
    useKBContext();

  const kbOptions = useMemo(() => {
    const options = activeKbs.map((kb) => ({
      label: kb.name,
      value: kb.id,
    }));
    if (
      selectedKb &&
      selectedKb.status === "inactive" &&
      !options.some((option) => option.value === selectedKb.id)
    ) {
      options.push({
        label: `${selectedKb.name} (inactive)`,
        value: selectedKb.id,
      });
    }
    return options;
  }, [activeKbs, selectedKb]);

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Header
        style={{
          background: "#fff",
          paddingInline: 24,
          borderBottom: "1px solid #f0f0f0",
        }}
      >
        <Space size={24} style={{ width: "100%", justifyContent: "space-between" }}>
          <Menu
            mode="horizontal"
            selectedKeys={[location.pathname]}
            items={NAV_ITEMS}
            style={{ flex: 1, minWidth: 0 }}
          />
          <Space>
            <Text type="secondary">当前知识库</Text>
            <Select
              loading={loading}
              style={{ width: 300 }}
              placeholder="选择知识库"
              value={selectedKbId}
              options={kbOptions}
              onChange={setSelectedKbId}
            />
          </Space>
        </Space>
      </Header>
      <Content style={{ padding: 24 }}>
        {readOnly && (
          <Alert
            type="warning"
            showIcon
            message="当前知识库已停用，页面处于只读模式，写操作按钮已禁用。"
            style={{ marginBottom: 16 }}
          />
        )}
        <Outlet />
      </Content>
    </Layout>
  );
}
