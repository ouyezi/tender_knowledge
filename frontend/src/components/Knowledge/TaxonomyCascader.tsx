import { Cascader, type CascaderProps } from "antd";
import { useMemo } from "react";
import { useKnowledgeTaxonomy } from "../../hooks/useKnowledgeTaxonomy";

interface TaxonomyCascaderProps {
  value?: string;
  onChange?: (next?: string) => void;
  allowClear?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

export default function TaxonomyCascader({
  value,
  onChange,
  allowClear = true,
  disabled = false,
  placeholder = "请选择分类块类型",
}: TaxonomyCascaderProps) {
  const { items, loading } = useKnowledgeTaxonomy("block_type");

  const treeOptions = useMemo<CascaderProps<string>["options"]>(() => {
    const topLevel = items
      .filter((item) => !item.parent_code)
      .sort((a, b) => a.sort_order - b.sort_order);
    const childMap = new Map<string, typeof items>();
    for (const item of items) {
      if (!item.parent_code) continue;
      const current = childMap.get(item.parent_code) ?? [];
      current.push(item);
      childMap.set(item.parent_code, current);
    }

    return topLevel.map((parent) => {
      const children = (childMap.get(parent.code) ?? [])
        .sort((a, b) => a.sort_order - b.sort_order)
        .map((child) => ({
          label: child.label,
          value: child.code,
        }));
      return {
        label: parent.label,
        value: parent.code,
        children: children.length ? children : undefined,
      };
    });
  }, [items]);

  const valuePath = useMemo(() => {
    if (!value) return undefined;
    const current = items.find((item) => item.code === value);
    if (!current) return undefined;
    return current.parent_code ? [current.parent_code, current.code] : [current.code];
  }, [items, value]);

  return (
    <Cascader
      allowClear={allowClear}
      disabled={disabled}
      placeholder={placeholder}
      loading={loading}
      options={treeOptions}
      value={valuePath}
      changeOnSelect
      showSearch
      onChange={(path) => onChange?.(path?.length ? path[path.length - 1] : undefined)}
    />
  );
}
