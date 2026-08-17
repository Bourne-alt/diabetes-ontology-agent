-- 008 · 给演示队列的诊断补 caveat
--
-- SHACL 的 dqs:DiagnosisShape 要求：verificationStatus='Provisional' 必须带 caveat。
-- 「单次异常不等于确诊」这句话必须写出来，不能指望读的人自己想到。
--
-- 由阈值推出的 Provisional 诊断由 30-diagnosis-from-assessment.rq 自动生成 caveat；
-- 但**人工录入**的 Provisional（P90004 的 GDM）之前没地方写，形状抓了个正着。
--
-- 新开一个迁移文件而不是改 004：migrate.py 对已应用文件做内容哈希校验，
-- 改历史文件会被拒 —— 线上 schema 与仓库 SQL 静默不一致是最难查的一类问题。

ALTER TABLE diabetes.sim_diagnosis ADD COLUMN IF NOT EXISTS caveat text;

COMMENT ON COLUMN diabetes.sim_diagnosis.caveat IS
    'verification_status=Provisional 时**必填**。说明为什么还没确诊、要补什么才能确诊。';
