import { Card, Input, Typography } from "antd";
import type { BlueprintDraft } from "../../services/blueprints";

const { Text } = Typography;

interface BlueprintSuggestedStructureProps {
  value: BlueprintDraft;
  readOnly?: boolean;
  onChange: (next: BlueprintDraft) => void;
}

export default function BlueprintSuggestedStructure({
  value,
  readOnly,
  onChange,
}: BlueprintSuggestedStructureProps) {
  return (
    <Card title="建议目录结构" size="small">
      <Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
        按逻辑模块描述建议的目录组织方式，可引用源章节标题。
      </Text>
      <Input.TextArea
        rows={6}
        value={value.suggested_structure_md ?? ""}
        readOnly={readOnly}
        placeholder={"例如：\n## 技术方案模块\n- 总体架构（对应 1.1）\n- 实施方案（对应 1.2）"}
        onChange={(event) =>
          onChange({ ...value, suggested_structure_md: event.target.value || null })
        }
      />
    </Card>
  );
}
