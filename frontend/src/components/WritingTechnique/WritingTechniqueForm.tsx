import { Button, Card, Divider, Form } from "antd";
import { useEffect } from "react";
import type { WritingTechniquePayload } from "../../services/writingTechniques";
import WritingTechniqueGuidanceSection from "./WritingTechniqueGuidanceSection";
import WritingTechniqueMetaSection from "./WritingTechniqueMetaSection";

interface WritingTechniqueFormProps {
  value: WritingTechniquePayload;
  loading?: boolean;
  readOnly?: boolean;
  showSave?: boolean;
  saveText?: string;
  onChange: (next: WritingTechniquePayload) => void;
  onSave: () => void;
}

function normalizePayload(value: Partial<WritingTechniquePayload>): WritingTechniquePayload {
  return {
    title: value.title ?? "",
    applicable_scene: value.applicable_scene ?? null,
    writing_summary: value.writing_summary ?? null,
    applicable_sections: value.applicable_sections ?? [],
    tags: value.tags ?? [],
    usage_mode: value.usage_mode ?? "REFERENCE",
    recommended_outline: value.recommended_outline ?? null,
    writing_strategy: value.writing_strategy ?? null,
    must_include: value.must_include ?? null,
    notes: value.notes ?? null,
    output_requirement: value.output_requirement ?? null,
    checklist: value.checklist ?? null,
    confidence: value.confidence ?? 0,
    source_chunk_id: value.source_chunk_id ?? null,
  };
}

export default function WritingTechniqueForm({
  value,
  loading = false,
  readOnly = false,
  showSave = true,
  saveText = "保存",
  onChange,
  onSave,
}: WritingTechniqueFormProps) {
  const [form] = Form.useForm<WritingTechniquePayload>();

  useEffect(() => {
    form.setFieldsValue(normalizePayload(value));
  }, [form, value]);

  return (
    <Card
      title="技巧内容"
      extra={
        showSave ? (
          <Button type="primary" loading={loading} disabled={readOnly} onClick={onSave}>
            {saveText}
          </Button>
        ) : null
      }
    >
      <Form<WritingTechniquePayload>
        form={form}
        layout="vertical"
        onValuesChange={(_, allValues) => {
          onChange(normalizePayload(allValues));
        }}
      >
        <WritingTechniqueMetaSection readOnly={readOnly} />
        <Divider style={{ marginBlock: 8 }} />
        <WritingTechniqueGuidanceSection readOnly={readOnly} />
      </Form>
    </Card>
  );
}
