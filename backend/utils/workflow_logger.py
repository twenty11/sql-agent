"""
工作流日志管理模块
提供结构化的日志记录功能,支持正常调用和评估调用分离记录
"""

import json
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional
from uuid import uuid4


class LogContext:
    """
    日志上下文类
    用于收集单次工作流执行的完整信息
    """

    def __init__(self, log_type: str, question: str):
        """
        初始化日志上下文

        Args:
            log_type: 日志类型 ("normal" 或 "evaluation")
            question: 用户问题
        """
        self.session_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        self.log_type = log_type
        self.question = question
        self.start_time = datetime.now()
        self.end_time = None

        # 工作流执行信息
        self.nodes_executed: List[str] = []
        self.node_start_times: Dict[str, datetime] = {}
        self.success = False

        # 节点数据
        self.node_data: Dict[str, Dict[str, Any]] = {}

        # 最终结果
        self.final_sql: Optional[str] = None
        self.retry_count: int = 0

    def start_node(self, node_name: str):
        """记录节点开始执行"""
        if node_name not in self.nodes_executed:
            self.nodes_executed.append(node_name)
        self.node_start_times[node_name] = datetime.now()

    def record_node_data(self, node_name: str, data: Dict[str, Any]):
        """
        记录节点数据

        Args:
            node_name: 节点名称
            data: 节点数据字典
        """
        if node_name not in self.node_data:
            self.node_data[node_name] = {}
        self.node_data[node_name].update(data)

    def finalize(self, state: Dict[str, Any]):
        """
        完成日志收集

        Args:
            state: 工作流最终状态
        """
        self.end_time = datetime.now()
        self.final_sql = state.get("generated_sql", "")
        self.retry_count = state.get("retry_count", 0)

        # 判断是否成功
        if self.log_type == "normal":
            self.success = state.get("execution_success", False)
        else:  # evaluation
            self.success = state.get("sql_valid", False)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        total_duration_ms = 0
        if self.end_time:
            total_duration_ms = int((self.end_time - self.start_time).total_seconds() * 1000)

        log_dict = {
            "session_id": self.session_id,
            "log_type": self.log_type,
            "timestamp": self.start_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "question": self.question,
            "workflow_execution": {
                "nodes_executed": self.nodes_executed,
                "total_duration_ms": total_duration_ms,
                "retry_count": self.retry_count,
                "success": self.success
            },
            "final_sql": self.final_sql
        }

        # 添加各节点数据
        for node_name, data in self.node_data.items():
            log_dict[f"{node_name}_node"] = data

        return log_dict


class NodeLogger:
    """
    节点日志记录辅助类
    简化节点中的日志记录代码
    """

    def __init__(self, log_context: Optional[LogContext], node_name: str):
        """
        初始化节点日志记录器

        Args:
            log_context: 日志上下文对象
            node_name: 节点名称
        """
        self.log_context = log_context
        self.node_name = node_name

        if self.log_context:
            self.log_context.start_node(node_name)

    def record(self, **kwargs):
        """
        记录节点数据

        Args:
            **kwargs: 要记录的键值对
        """
        if self.log_context:
            self.log_context.record_node_data(self.node_name, kwargs)


class WorkflowLogger:
    """
    工作流日志管理器
    负责日志的初始化、格式化和写入
    """

    _loggers: Dict[str, logging.Logger] = {}
    _initialized = False

    @classmethod
    def initialize(cls, config):
        """
        初始化日志系统

        Args:
            config: 配置对象 (Settings实例)
        """
        if cls._initialized:
            return

        # 创建日志目录
        normal_log_dir = os.path.join(config.log_dir, "normal")
        evaluation_log_dir = os.path.join(config.log_dir, "evaluation")
        os.makedirs(normal_log_dir, exist_ok=True)
        os.makedirs(evaluation_log_dir, exist_ok=True)

        # 创建正常调用日志记录器
        cls._loggers["normal"] = cls._create_logger(
            name="workflow_normal",
            log_file=os.path.join(normal_log_dir, "workflow.log"),
            max_bytes=config.log_max_bytes,
            backup_count=config.log_backup_count
        )

        # 创建评估调用日志记录器
        cls._loggers["evaluation"] = cls._create_logger(
            name="workflow_evaluation",
            log_file=os.path.join(evaluation_log_dir, "evaluation.log"),
            max_bytes=config.log_max_bytes,
            backup_count=config.log_backup_count
        )

        cls._initialized = True

    @classmethod
    def _create_logger(cls, name: str, log_file: str, max_bytes: int, backup_count: int) -> logging.Logger:
        """
        创建日志记录器

        Args:
            name: 日志记录器名称
            log_file: 日志文件路径
            max_bytes: 单个日志文件最大字节数
            backup_count: 备份文件数量

        Returns:
            配置好的日志记录器
        """
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.propagate = False  # 不传播到根日志记录器

        # 清除已有的处理器
        logger.handlers.clear()

        # 创建轮转文件处理器
        handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )

        # 设置格式器 (只输出消息内容,不添加额外格式)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)

        logger.addHandler(handler)

        return logger

    @classmethod
    def write_log(cls, log_context: LogContext, log_format: str = "json"):
        """
        写入日志

        Args:
            log_context: 日志上下文对象
            log_format: 日志格式 ("json" 或 "readable")
        """
        if not cls._initialized:
            return

        logger = cls._loggers.get(log_context.log_type)
        if not logger:
            return

        if log_format == "json":
            log_content = cls._format_json(log_context)
        else:  # readable
            log_content = cls._format_readable(log_context)

        logger.info(log_content)

    @classmethod
    def _format_json(cls, log_context: LogContext) -> str:
        """
        格式化为JSON Lines格式

        Args:
            log_context: 日志上下文对象

        Returns:
            JSON字符串
        """
        log_dict = log_context.to_dict()
        return json.dumps(log_dict, ensure_ascii=False)

    @classmethod
    def _format_readable(cls, log_context: LogContext) -> str:
        """
        格式化为可读文本格式

        Args:
            log_context: 日志上下文对象

        Returns:
            格式化的文本字符串
        """
        log_dict = log_context.to_dict()
        lines = []

        # 分隔符
        lines.append("=" * 80)

        # 基本信息
        lines.append(f"[会话ID] {log_dict['session_id']}")
        lines.append(f"[类型] {'正常调用' if log_dict['log_type'] == 'normal' else '评估调用'}")
        lines.append(f"[时间] {log_dict['timestamp']}")
        lines.append(f"[问题] {log_dict['question']}")
        lines.append("")

        # 工作流执行信息
        workflow_exec = log_dict["workflow_execution"]
        lines.append("[工作流执行]")
        lines.append(f"  执行节点: {' → '.join(workflow_exec['nodes_executed'])}")
        lines.append(f"  总耗时: {workflow_exec['total_duration_ms']}ms")
        lines.append(f"  重试次数: {workflow_exec['retry_count']}")
        lines.append(f"  执行状态: {'成功' if workflow_exec['success'] else '失败'}")
        lines.append("")

        # 最终SQL
        if log_dict.get("final_sql"):
            lines.append("[最终SQL]")
            for sql_line in log_dict["final_sql"].strip().split("\n"):
                lines.append(f"  {sql_line}")
            lines.append("")

        # 各节点信息
        for key, value in log_dict.items():
            if key.endswith("_node") and isinstance(value, dict):
                node_name = key.replace("_node", "")
                lines.append(f"[{node_name}节点]")
                for k, v in value.items():
                    if isinstance(v, list):
                        lines.append(f"  {k}: {', '.join(str(item) for item in v)}")
                    else:
                        lines.append(f"  {k}: {v}")
                lines.append("")

        lines.append("=" * 80)
        lines.append("")  # 空行分隔不同的日志条目

        return "\n".join(lines)
