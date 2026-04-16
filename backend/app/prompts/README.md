# Prompt Assets

本目录保存 2.0 后端的 Prompt 资产。

- 按 Agent 分目录管理
- 版本号写入文件名
- 模板变量统一使用 `[[variable_name]]`
- 节点代码只负责装配变量、加载版本、渲染模板
- 不允许在业务逻辑代码中硬编码长 Prompt
