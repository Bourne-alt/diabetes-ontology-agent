export const TOOL_LABELS = {
  write_todos: '安排查询步骤', report_plan: '说明查询计划', ontology_status: '确认知识库可用范围',
  search_concepts: '找到对应的医学概念', explore_concept: '查看概念之间的联系',
  find_graph_path: '寻找证据之间的路径', search_rules: '核对判断规则', search_passages: '查找指南原文',
  explain_term: '解释术语', find_patients: '查找患者记录', patient_evidence: '查看检查与判断依据',
  inspect_fact_schema: '确认可查询的资料', query_patient_facts: '读取患者记录',
  simulate_patient_course: '核对假设成立后的变化',
  run_prediction_demo: '运行预测演示',
  assess_patient_treatment: '评估当前治疗措施',
};
export function toolLabel(name) { return TOOL_LABELS[name] ?? '查询相关资料'; }
