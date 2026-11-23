# 初始 schema

`src.models.Base.metadata.create_all()` 按外键顺序建表，由 `src.main` 在 API 首次启动时执行。已有开发卷不执行自动字段迁移。项目 README 记录了模型与首次建库入口。
